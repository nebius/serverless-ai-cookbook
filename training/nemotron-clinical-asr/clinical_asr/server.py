"""Single-tenant isolated demo endpoint; HTTP batch, native WS and typed MCP.

Deployment MUST use one replica and a persistent DATA_DIR until a transactional
multi-replica store is implemented. No arbitrary URL fetching, transcript logging,
or PHI suitability claim. Runtime credentials are never sent to browsers.
"""
import asyncio
import contextlib
import hashlib
import json
import os
import re
import secrets
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import JSONResponse, PlainTextResponse
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .common import write_json
from .contracts import SpeechOptions, TranscriptionRequest
from .evaluate import transcribe_wav
from .runtime import NeMoRuntime
from .object_store import ObjectStore, stage_model_from_env
from .stream import _gpu_call, run_stream

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
TERMINAL = {"succeeded", "failed", "cancelled"}


class APIError(Exception):
    def __init__(self, code, status=400, *, retryable=False, admitted=False, operation_id=None):
        self.status = status
        self.detail = {"code": code, "retryable": retryable, "durable_admission": admitted,
                       "operation_id": operation_id}


class Service:
    def __init__(self, directory, runtime, object_store=None):
        self.directory = Path(directory)
        self.artifacts = self.directory / "artifacts"
        self.operations_dir = self.directory / "operations"
        for path in (self.artifacts, self.operations_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.object_store = object_store
        if self.object_store:
            self.object_store.restore_operations(self.operations_dir)
        self.runtime = runtime
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue(maxsize=4)
        self.operations = {}
        self.keys = {}
        self.worker_task = None
        self.ready = False
        self.requests = 0
        self.errors = 0
        for path in self.operations_dir.glob("*.json"):
            operation = json.loads(path.read_text())
            if operation["status"] not in TERMINAL:
                operation.update(status="failed", error={"code": "worker_interrupted", "retryable": True,
                                 "durable_admission": True, "operation_id": operation["id"]})
                write_json(path, operation)
                if self.object_store:
                    self.object_store.upload(path, "operations/" + path.name)
            self.operations[operation["id"]] = operation
            self.keys[operation["idempotency_key"]] = operation["id"]

    def save(self, operation):
        operation["updated_at_unix"] = time.time()
        path = self.operations_dir / (operation["id"] + ".json")
        write_json(path, operation)
        if self.object_store:
            self.object_store.upload(path, "operations/" + path.name)

    def describe(self):
        return {"model": self.runtime.identity, "protocols": ["HTTP", "WebSocket", "MCP Streamable HTTP"],
                "batch_route": "/v1/transcriptions", "stream_route": "/v1/audio/stream", "mcp_route": "/mcp",
                "max_audio_seconds": 1800, "max_upload_bytes": MAX_UPLOAD_BYTES, "max_queue": 4,
                "concurrency": 1, "replicas_supported": 1, "tenant_scope": "isolated_demo",
                "clinical_validation": "NOT_PERFORMED", "phi_approved": False,
                "audio": {"encoding": "pcm_s16le", "sample_rate_hz": 16000, "channels": 1},
                "artifact_transport": "authenticated_POST_/v1/artifacts",
                "source": "https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b",
                "persistence": "S3_objects" if self.object_store else "mounted_DATA_DIR",
                "retention": "Persistent data; operator must configure lifecycle before PHI use."}

    def poll(self, operation_id):
        operation = self.operations.get(operation_id)
        if operation is None:
            raise APIError("operation_not_found", 404)
        # Never disclose internal paths or idempotency material.
        return {k: v for k, v in operation.items() if k not in {"request", "request_hash", "idempotency_key"}}

    def submit(self, request):
        body = request.model_dump()
        request_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        previous = self.keys.get(request.idempotency_key)
        if previous:
            if self.operations[previous]["request_hash"] != request_hash:
                raise APIError("idempotency_conflict", 409, admitted=True, operation_id=previous)
            return self.poll(previous)
        if not self.ready:
            raise APIError("model_not_ready", 503, retryable=True)
        if request.options.model != self.runtime.model_id or request.options.chunk_size_ms != self.runtime.chunk_ms:
            raise APIError("runtime_profile_mismatch", 422)
        artifact_name = request.audio_artifact.rsplit(":", 1)[1] + ".wav"
        if not (self.artifacts / artifact_name).is_file() and not (self.object_store and self.object_store.exists("artifacts/" + artifact_name)):
            raise APIError("artifact_not_found", 404)
        if self.queue.full():
            raise APIError("queue_full", 429, retryable=True)
        operation_id = str(uuid4())
        operation = {"id": operation_id, "status": "queued", "durable_admission": True,
                     "idempotency_key": request.idempotency_key, "request_hash": request_hash,
                     "request": body, "created_at_unix": time.time(), "cancel_requested": False,
                     "model_id": self.runtime.model_id, "result": None, "error": None}
        self.operations[operation_id] = operation
        self.keys[request.idempotency_key] = operation_id
        try:
            self.save(operation)  # durable acceptance precedes response or work scheduling
        except Exception:
            operation.update(status="admission_unknown", durable_admission="unknown",
                             error={"code": "persistence_unconfirmed", "retryable": True,
                                    "durable_admission": "unknown", "operation_id": operation_id})
            # Keep the SAME identity on replay; never execute work whose admission is unknown.
            raise APIError("persistence_unconfirmed", 503, retryable=True, admitted="unknown", operation_id=operation_id) from None
        self.queue.put_nowait(operation_id)
        self.requests += 1
        return self.poll(operation_id)

    def cancel(self, operation_id):
        self.poll(operation_id)
        operation = self.operations[operation_id]
        if operation["status"] not in TERMINAL:
            operation["cancel_requested"] = True
            if operation["status"] == "queued":
                operation["status"] = "cancelled"
            self.save(operation)
        return self.poll(operation_id)

    async def worker(self):
        while True:
            operation_id = await self.queue.get()
            operation = self.operations[operation_id]
            try:
                if operation["cancel_requested"]:
                    continue
                async with self.lock:
                    if operation["cancel_requested"]:
                        continue
                    operation["status"] = "running"
                    self.save(operation)
                    request = TranscriptionRequest.model_validate(operation["request"])
                    artifact = self.artifacts / (request.audio_artifact.rsplit(":", 1)[1] + ".wav")
                    if not artifact.exists() and self.object_store:
                        await _gpu_call(self.object_store.download, "artifacts/" + artifact.name,
                                        artifact, request.audio_artifact.rsplit(":", 1)[1])
                    result = await _gpu_call(
                        lambda: transcribe_wav(self.runtime, artifact, request.options,
                                               cancelled=lambda: operation["cancel_requested"]))
                    operation.update(status="succeeded", result=result)
            except InterruptedError:
                operation["status"] = "cancelled"
            except asyncio.CancelledError:
                operation.update(status="failed", error={"code": "worker_shutdown", "retryable": True,
                                 "durable_admission": True, "operation_id": operation_id})
                raise
            except Exception:
                self.errors += 1
                operation.update(status="failed", error={"code": "inference_failed", "retryable": False,
                                 "durable_admission": True, "operation_id": operation_id})
            finally:
                self.save(operation)
                self.queue.task_done()

    async def upload(self, file):
        temp = self.artifacts / (str(uuid4()) + ".upload")
        digest = hashlib.sha256()
        length = 0
        try:
            with temp.open("xb") as target:
                while chunk := await file.read(1024 * 1024):
                    length += len(chunk)
                    if length > MAX_UPLOAD_BYTES:
                        raise APIError("audio_too_large", 413)
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            try:
                with wave.open(str(temp), "rb") as audio:
                    if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
                        raise ValueError("format")
                    seconds = audio.getnframes() / 16000
                    if not 0 < seconds <= 1800:
                        raise ValueError("duration")
            except (wave.Error, EOFError, ValueError):
                raise APIError("requires_mono_16khz_pcm16_wav_max1800s", 422) from None
            checksum = digest.hexdigest()
            target = self.artifacts / (checksum + ".wav")
            if target.exists():
                temp.unlink()
            else:
                temp.replace(target)
            if self.object_store:
                await _gpu_call(self.object_store.upload, target, "artifacts/" + target.name)
            return {"artifact": "artifact:sha256:" + checksum, "sha256": checksum,
                    "bytes": length, "audio_seconds": seconds}
        finally:
            if temp.exists():
                temp.unlink()


service = None
mcp = FastMCP("Clinical Nemotron ASR", host="0.0.0.0", stateless_http=True, json_response=True,
              instructions="Research demo only. Upload WAV by HTTP first; use immutable artifact reference. Poll the SAME operation; never resubmit to poll. Transcripts and SOAP drafts require clinician review.")


@mcp.tool()
def describe_clinical_asr() -> dict:
    """Discover exact checkpoint, serving contract, limits, privacy and readiness caveats."""
    return service.describe()


@mcp.tool()
def transcribe_clinical_audio(
    audio_artifact: Annotated[str, Field(pattern=r"^artifact:sha256:[0-9a-f]{64}$", description="Immutable WAV reference returned by authenticated POST /v1/artifacts; never a local path or URL.")],
    idempotency_key: Annotated[str, Field(min_length=8, max_length=128, description="Stable caller-chosen key for this intended submission; reuse only for the identical request.")],
    model: Annotated[str, Field(description="Exact App identity returned by describe_clinical_asr, e.g. nemotron-clinical-en.")],
) -> dict:
    """Durably submit English clinical ASR. Returns operation ID, not a completed transcript. No diagnosis or diarization."""
    try:
        return service.submit(TranscriptionRequest(audio_artifact=audio_artifact, idempotency_key=idempotency_key,
                                                   options=SpeechOptions(model=model, output_granularity="word")))
    except APIError as exc:
        return {"error": exc.detail}
    except ValueError:
        return {"error": {"code": "invalid_request", "retryable": False, "durable_admission": False}}


@mcp.tool()
def get_clinical_transcription(operation_id: Annotated[str, Field(description="Durable operation ID from submission.")]) -> dict:
    """Poll or retrieve the same accepted operation, without executing it again."""
    try:
        return service.poll(operation_id)
    except APIError as exc:
        return {"error": exc.detail}


@mcp.tool()
def cancel_clinical_transcription(operation_id: str) -> dict:
    """Cancel queued work or request cancellation after the current GPU chunk completes."""
    try:
        return service.cancel(operation_id)
    except APIError as exc:
        return {"error": exc.detail}


@asynccontextmanager
async def lifespan(app):
    global service
    token = os.getenv("API_BEARER_TOKEN", "")
    if len(token) < 24:
        raise RuntimeError("API_BEARER_TOKEN_secret_required_min24")
    model_path = await _gpu_call(stage_model_from_env)
    runtime = NeMoRuntime(checkpoint=model_path, checkpoint_sha=os.getenv("MODEL_SHA256"),
                          model_id=os.getenv("MODEL_ID", "nemotron35-base-en"),
                          chunk_ms=int(os.getenv("CHUNK_SIZE_MS", "560")))
    store = ObjectStore(os.environ["STATE_BUCKET"], os.environ["STATE_PREFIX"]) if os.getenv("STATE_BUCKET") else None
    service = await _gpu_call(lambda: Service(os.getenv("DATA_DIR", "/output/service"), runtime, store))
    await _gpu_call(runtime.load)
    service.ready = True
    service.worker_task = asyncio.create_task(service.worker())
    async with mcp.session_manager.run():
        try:
            yield
        finally:
            service.ready = False
            for operation in service.operations.values():
                if operation["status"] not in TERMINAL:
                    operation["cancel_requested"] = True
            service.worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await service.worker_task


class BearerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or scope.get("path") in {"/healthz", "/readyz"}:
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        supplied = headers.get(b"authorization", b"")
        expected = ("Bearer " + os.getenv("API_BEARER_TOKEN", "")).encode()
        if not os.getenv("API_BEARER_TOKEN") or not secrets.compare_digest(supplied, expected):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            return await JSONResponse({"error": {"code": "unauthorized", "retryable": False,
                                      "durable_admission": False}}, status_code=401)(scope, receive, send)
        if scope["type"] == "http":
            request_id = str(uuid4())
            original_send = send
            async def correlated_send(message):
                if message["type"] == "http.response.start":
                    message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
                await original_send(message)
            send = correlated_send
            raw_length = headers.get(b"content-length", b"0")
            try:
                too_large = int(raw_length) > MAX_UPLOAD_BYTES + 1024 * 1024
            except ValueError:
                too_large = True
            if too_large:
                return await JSONResponse({"error": {"code": "request_too_large"}}, status_code=413)(scope, receive, send)
            original_receive = receive
            received = 0
            async def bounded_receive():
                nonlocal received
                message = await original_receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > MAX_UPLOAD_BYTES + 1024 * 1024:
                        raise HTTPException(status_code=413, detail={"code": "request_too_large"})
                return message
            receive = bounded_receive
        return await self.app(scope, receive, send)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(BearerMiddleware)


@app.exception_handler(APIError)
async def api_error(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status)


@app.get("/healthz")
def health():
    return {"status": "alive"}


@app.get("/readyz")
def ready():
    return JSONResponse({"ready": bool(service and service.ready)}, status_code=200 if service and service.ready else 503)


@app.get("/v1/models")
def models():
    return {"data": [service.describe()]}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return (f"clinical_asr_ready {int(service.ready)}\nclinical_asr_queue_depth {service.queue.qsize()}\n"
            f"clinical_asr_requests_total {service.requests}\nclinical_asr_errors_total {service.errors}\n"
            f"clinical_asr_gpu_busy {int(service.lock.locked())}\n")


@app.post("/v1/artifacts")
async def upload(file: UploadFile = File(...)):
    return await service.upload(file)


@app.post("/v1/transcriptions", status_code=202)
async def submit(request: TranscriptionRequest):
    return service.submit(request)


@app.get("/v1/operations/{operation_id}")
async def poll(operation_id: str):
    return service.poll(operation_id)


@app.post("/v1/operations/{operation_id}/cancel")
async def cancel(operation_id: str):
    return service.cancel(operation_id)


@app.post("/v1/audio/transcriptions")
async def compatibility_transcribe(
    file: UploadFile = File(...), model: str = Form(...), language: str = Form("en"),
    response_format: str = Form("json"),
    timestamp_granularities: list[str] | None = Form(None, alias="timestamp_granularities[]"),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    if response_format not in {"json", "verbose_json"} or language not in {"en", "en-US"}:
        raise APIError("unsupported_response_format_or_language", 422)
    if timestamp_granularities and timestamp_granularities != ["word"]:
        raise APIError("only_word_timestamps_supported", 422)
    artifact = await service.upload(file)
    try:
        request = TranscriptionRequest(audio_artifact=artifact["artifact"],
            idempotency_key=idempotency_key or str(uuid4()),
            options=SpeechOptions(model=model, language=language,
                                  output_granularity="word" if response_format == "verbose_json" or timestamp_granularities else "segment"))
    except ValueError:
        raise APIError("invalid_options", 422) from None
    operation = service.submit(request)
    deadline = time.monotonic() + 600
    while operation["status"] not in TERMINAL and time.monotonic() < deadline:
        await asyncio.sleep(0.1)
        operation = service.poll(operation["id"])
    headers = {"X-Operation-Id": operation["id"]}
    if operation["status"] not in TERMINAL:
        return JSONResponse(operation, status_code=202, headers=headers)
    if operation["status"] != "succeeded":
        return JSONResponse(operation, status_code=422, headers=headers)
    result = operation["result"]
    return JSONResponse(result if response_format == "verbose_json" else {"text": result["text"]}, headers=headers)


@app.websocket("/v1/audio/stream")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    if not service.ready or service.lock.locked() or not service.queue.empty():
        await websocket.send_json({"type": "session.error", "code": "runtime_busy", "retryable": True})
        await websocket.close(code=1013)
        return
    async with service.lock:
        async def messages():
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                yield message.get("bytes") if message.get("bytes") is not None else message["text"]
        try:
            await run_stream(service.runtime, messages(), websocket.send_json)
        finally:
            with contextlib.suppress(Exception):
                await websocket.close()


# Last route: FastMCP provides /mcp and shares the authenticated ASGI stack.
app.mount("/", mcp.streamable_http_app())
