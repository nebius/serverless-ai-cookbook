"""Authenticated standalone file adapter over the pinned shared speech runtime."""
import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import tempfile
import wave
from pathlib import Path

MAX_UPLOAD = 16 * 1024 * 1024
MAX_REQUEST_SECONDS = 600
BASE_SHA256 = "283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd"


def credentials(raw):
    keys = json.loads(raw)
    if not isinstance(keys, dict) or not 1 <= len(keys) <= 100:
        raise ValueError("ASR_API_KEYS must map 1–100 customer names to private tokens")
    if any(not isinstance(k, str) or not k or len(k) > 100 or not isinstance(v, str)
           or not 32 <= len(v) <= 256 or not v.isascii() or any(c.isspace() for c in v)
           for k, v in keys.items()) or len(set(keys.values())) != len(keys):
        raise ValueError("invalid or duplicate customer credentials")
    return {hashlib.sha256(k.encode()).hexdigest(): v for k, v in keys.items()}


def identify(keys, supplied):
    if not isinstance(supplied, str) or not supplied.isascii() or len(supplied) > 256:
        return None
    for group, secret in keys.items():
        if hmac.compare_digest(supplied, secret):
            return group
    return None


class LiveBoundary:
    """Authenticate native WS without accepting caller-supplied tenant headers."""
    def __init__(self, app, *, keys, private_token):
        self.app, self.keys, self.private_token = app, keys, private_token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"x-api-key", b"").decode("ascii", errors="replace")
            group = identify(self.keys, supplied)
            if scope["path"] != "/v1/audio/stream" or group is None:
                await send({"type": "websocket.close", "code": 1008})
                return
            scope = {**scope, "headers": trusted_headers(scope["headers"], self.private_token, group)}
        await self.app(scope, receive, send)


def trusted_headers(headers, private_token, group):
    # Never forward an external claim as trusted scheduler metadata.
    retained = [(k, v) for k, v in headers if k.lower() not in {b"authorization", b"x-fs2-scheduling-group", b"x-api-key"}]
    return retained + [(b"authorization", ("Bearer " + private_token).encode()),
                       (b"x-fs2-scheduling-group", group.encode())]


def checkpoint(path, sha256):
    if path is None:
        if sha256 is not None:
            raise ValueError("checkpoint path and SHA256 required together")
        return None
    path = Path(path)
    if path.is_dir():
        checksum = path / "model.sha256"
        if sha256 is not None or checksum.is_symlink() or not checksum.is_file() or checksum.stat().st_size > 100:
            raise ValueError("expected training output folder with model.sha256")
        match = re.fullmatch(r"([0-9a-f]{64})  model\.nemo\n?", checksum.read_text())
        if match is None:
            raise ValueError("invalid model.sha256")
        sha256, path = match[1], path / "model.nemo"
    if not sha256 or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise ValueError("exact checkpoint SHA256 required")
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("checkpoint must be an operator-selected regular absolute file")
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != sha256:
            raise ValueError("checkpoint hash mismatch")
    return path, sha256


def create_app(runtime, profile, keys, *, admin_key=None, load=True, slots=4):
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse, Response
    from fs2_speech.audio import AudioInputError, transcribe_file
    from fs2_speech.contracts import SpeechOptions
    from fs2_speech.scheduler import scheduling_group
    from fs2_speech.server import create_app as shared_app, gateway_token

    # Reuse load/warmup, single GPU lane, cancellation, metrics and draining.
    app = shared_app(runtime, profile, allowed_hosts=frozenset(), load=load,
                     max_sessions=slots, max_batch_size=slots)
    state = app.state.runtime_state
    scheduled = app.state.scheduled_runtime
    state["uploads"] = 0
    state["file_completed"] = 0
    state["file_errors"] = 0
    private_token = gateway_token()
    if private_token is None:
        raise ValueError("internal authentication required")
    app.add_middleware(LiveBoundary, keys=keys, private_token=private_token)
    shared_metrics = next(r.endpoint for r in app.router.routes if getattr(r, "path", "") == "/metrics")
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/metrics"]

    @app.get("/metrics")
    async def metrics(request: Request):
        original = await shared_metrics(request)
        body = re.sub(r"^fs2_speech_active_sessions .+$", f"fs2_speech_active_sessions {state['active']}",
                      original.body.decode(), flags=re.MULTILINE)
        snapshot = scheduled.scheduler.snapshot()
        values = {"active_sessions": state["active"], "uploading_or_transcribing": state["uploads"],
                  "completed_files_total": state["file_completed"], "file_errors_total": state["file_errors"],
                  "queued_actions": snapshot["queued_actions"], "inflight_actions": snapshot["inflight_actions"],
                  "oldest_wait_seconds": snapshot["oldest_wait_seconds"],
                  "ready": int(state["ready"] and not state["draining"] and not scheduled.scheduler.poisoned)}
        return Response(body + "".join(f"nemotron_{key} {value}\n" for key, value in values.items()), media_type="text/plain")

    @app.middleware("http")
    async def public_boundary(request, call_next):
        if request.url.path == "/healthz" and request.method == "GET":
            return await call_next(request)
        operator = {("GET", "/metrics"), ("GET", "/capacity-observation"), ("POST", "/drain")}
        if (request.method, request.url.path) in operator:
            supplied = request.headers.get("x-api-key", "")
            if admin_key is None or not supplied.isascii() or not hmac.compare_digest(supplied, admin_key):
                return JSONResponse({"error": "operator_key_required"}, status_code=403)
            request.scope["headers"] = trusted_headers(request.scope["headers"], private_token, "0" * 64)
            return await call_next(request)
        allowed = {("GET", "/readyz"), ("GET", "/v1/models"),
                   ("POST", "/v1/audio/transcriptions")}
        if (request.method, request.url.path) not in allowed:
            return JSONResponse({"error": "not_found"}, status_code=404)
        group = identify(keys, request.headers.get("x-api-key"))
        if group is None:
            return JSONResponse({"error": "invalid_api_key"}, status_code=401)
        request.state.customer_group = group
        return await call_next(request)

    @app.get("/v1/models")
    async def models():
        return {"data": [{"id": "nemotron-speech", "object": "model",
                          "runtime_identity": runtime.identity()}]}

    @app.post("/v1/audio/transcriptions")
    async def transcribe(request: Request):
        if not state["ready"] or state["draining"] or scheduled.scheduler.poisoned:
            state["rejected"] += 1
            raise HTTPException(503, "runtime_not_ready", headers={"Retry-After": "2"})
        if state["active"] >= slots:
            state["rejected"] += 1
            raise HTTPException(429, "busy", headers={"Retry-After": "1"})
        state["uploads"] += 1
        state["active"] += 1
        task = None
        directory = None
        completed = False
        group = scheduling_group.set(request.state.customer_group)
        try:
            async with asyncio.timeout(MAX_REQUEST_SECONDS):
                if request.headers.get("content-type", "").split(";")[0] != "audio/wav":
                    raise HTTPException(415, "send a WAV body with Content-Type: audio/wav")
                directory = tempfile.TemporaryDirectory(prefix="asr-upload-")
                path = Path(directory.name) / "audio"
                with path.open("xb") as output:
                    size = 0
                    async with asyncio.timeout(60):
                        async for chunk in request.stream():
                            size += len(chunk)
                            if size > MAX_UPLOAD:
                                raise HTTPException(413, "upload_exceeds_16_MiB")
                            output.write(chunk)
                try:
                    with wave.open(str(path)) as wav:
                        if (wav.getnchannels(), wav.getframerate(), wav.getsampwidth(), wav.getcomptype()) != (1, 16000, 2, "NONE"):
                            raise ValueError("wrong audio format")
                        if not 0 < wav.getnframes() <= 300 * 16000:
                            raise ValueError("expected at most 5 minutes")
                        if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                            raise ValueError("truncated WAV")
                except (ValueError, wave.Error, EOFError):
                    raise HTTPException(422, "expected complete mono 16 kHz PCM16 WAV, max 5 minutes") from None
                options = SpeechOptions(model=profile.model, language="en-US", chunk_size_ms=profile.chunk_size_ms)
                task = asyncio.create_task(transcribe_file(scheduled, path, options))
                while not task.done():
                    if await request.is_disconnected():
                        raise asyncio.CancelledError
                    await asyncio.wait({task}, timeout=0.1)
                result = await task
                completed = True
                return {**result, "runtime_identity": runtime.identity()}
        except TimeoutError:
            raise HTTPException(504, "request_timeout") from None
        except AudioInputError:
            raise HTTPException(422, "invalid_audio") from None
        finally:
            interrupted = False
            try:
                if task is not None:
                    if not task.done() and not task.cancelling():
                        task.cancel()
                    joined = asyncio.gather(task, return_exceptions=True)
                    # Do not let repeated disconnect/cancellation free a live GPU lane.
                    while not joined.done():
                        try:
                            await asyncio.shield(joined)
                        except asyncio.CancelledError:
                            interrupted = True
                            continue
                    joined.result()
            finally:
                try:
                    if directory is not None:
                        directory.cleanup()
                finally:
                    scheduling_group.reset(group)
                    state["uploads"] -= 1
                    state["active"] -= 1
                    state["file_completed" if completed else "file_errors"] += 1
            if interrupted:
                raise asyncio.CancelledError

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", help="training output folder containing model.nemo and model.sha256")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    keys = credentials(os.environ.pop("ASR_API_KEYS", "{}"))
    admin = os.environ.pop("ASR_ADMIN_KEY", "")
    credentials(json.dumps({"operator": admin}))
    if admin in keys.values():
        raise ValueError("operator and customer keys must differ")
    selected = checkpoint(args.checkpoint, args.sha256)
    import uvicorn
    from fs2_speech.contracts import RuntimeProfile
    from fs2_speech.nemo_runtime import NeMoRuntime
    from fs2_speech.serverless_entrypoint import secret_file
    profile = RuntimeProfile(model="nemotron-speech-en-0.6b")
    runtime = NeMoRuntime(profile, config_path=Path("/opt/nemo/examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml"),
                          max_sessions=4, max_batch_size=4)
    if selected is None:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download("nvidia/nemotron-speech-streaming-en-0.6b",
            "nemotron-speech-streaming-en-0.6b.nemo", revision="ebe59e5a817142986528bbbee5dba8db7b38ed50")
        selected = checkpoint(str(Path(path).resolve()), BASE_SHA256)
    runtime.bind_checkpoint(*selected)
    # Internal original routes stay private and unreachable; no gateway credential is exposed.
    import secrets
    os.environ["FS2_STT_REQUIRE_GATEWAY_AUTH"] = "1"
    os.environ["FS2_STT_GATEWAY_TOKEN_MATERIAL"] = secrets.token_hex(32)
    with secret_file():
        uvicorn.run(create_app(runtime, profile, keys, admin_key=admin), host="0.0.0.0", port=8000,
                    loop="asyncio", limit_concurrency=32, ws_max_size=65536, ws_max_queue=2,
                    timeout_graceful_shutdown=7205)


if __name__ == "__main__":
    main()
