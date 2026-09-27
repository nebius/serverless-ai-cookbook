"""Private persistent ASR worker. Customer authentication/admission lives in the gateway."""

import asyncio
import json
import logging
import os
import socket
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from .audio import AudioInputError, DownloadAudio, download_audio, transcribe_file
from .capacity_observation import WorkerObservation
from .contracts import MODELS, RuntimeProfile, SpeechOptions, StrictContract
from .nemo_runtime import NeMoRuntime
from .probe import FIXTURE
from .scheduler import ScheduledRuntime, scheduling_group
from .stream import run_stream
from .worker_auth import authorized_group, gateway_token

LOG = logging.getLogger(__name__)


class FileRequest(StrictContract):
    audio: DownloadAudio
    options: SpeechOptions


def create_app(runtime, profile: RuntimeProfile, *, allowed_hosts: frozenset[str], load: bool = True,
               max_sessions: int = 1, max_batch_size: int = 1, batch_wait_seconds: float = 0.005) -> FastAPI:
    """One immutable worker/profile with bounded chunk scheduling and drain.

    This service must remain cluster-private. The public gateway authorizes
    model/tenant access, issues artifact handles and owns durable Operations.
    """
    if (getattr(runtime, "max_sessions", max_sessions) != max_sessions
            or getattr(runtime, "max_batch_size", max_batch_size) != max_batch_size):
        raise ValueError("scheduler_and_native_limits_must_match")
    registry = CollectorRegistry()
    private_token = gateway_token()
    active = Gauge("fs2_speech_active_sessions", "Admitted sessions on this worker", registry=registry)
    total = Counter("fs2_speech_sessions_total", "Worker session outcomes", ["mode", "outcome"], registry=registry)
    audio = Counter("fs2_speech_audio_seconds_total", "Successfully transcribed audio seconds", registry=registry)
    processed = Counter("fs2_speech_processed_audio_seconds_total",
                        "Unpadded PCM completed by native inference, not merely received", registry=registry)
    duration = Histogram("fs2_speech_processing_seconds", "File processing duration", registry=registry)
    queue = Gauge("fs2_speech_queued_actions", "Pending bounded GPU actions", registry=registry)
    inflight = Gauge("fs2_speech_inflight_actions", "Actions in the one GPU execution lane", registry=registry)
    buffered = Gauge("fs2_speech_buffered_pcm_bytes", "PCM held by worker framers and pending actions",
                     registry=registry)
    oldest = Gauge("fs2_speech_oldest_action_wait_seconds", "Age of oldest pending GPU action", registry=registry)
    events = Counter("fs2_speech_scheduler_events_total", "Bounded scheduler lifecycle", ["event"], registry=registry)
    waiting = Histogram("fs2_speech_chunk_queue_seconds", "Chunk/control wait before execution", registry=registry)
    execution = Histogram("fs2_speech_gpu_lane_seconds", "Wall time per batch, not CUDA kernel time", registry=registry)
    batches = Histogram("fs2_speech_batch_size", "Actions per serialized execution",
                        buckets=(1, 2, 4, 8, 16, 32, 64, 128),
                        registry=registry)

    def observe(kind, value):
        if kind == "queue_seconds":
            waiting.observe(value)
        elif kind == "execution_seconds":
            execution.observe(value)
        elif kind == "batch_size":
            batches.observe(value)
        elif kind == "processed_audio_seconds":
            processed.inc(value)
            observation.processed(value)
        else:
            events.labels(kind).inc(value)

    scheduled = ScheduledRuntime(runtime, max_sessions=max_sessions, max_batch_size=max_batch_size,
                                 batch_wait_seconds=batch_wait_seconds, observe=observe)
    state = {"ready": not load, "active": 0, "draining": False, "error": None, "rejected": 0}

    @asynccontextmanager
    async def lifespan(app):
        async def initialize():
            try:
                await asyncio.to_thread(runtime.load)
                # Warm a public synthetic phrase, not a customer session. Keep
                # readiness false through lazy kernel/decoder initialization.
                with tempfile.TemporaryDirectory(prefix="fs2-speech-warm-") as directory:
                    path = Path(directory) / "warm.wav"
                    process = await asyncio.create_subprocess_exec(
                        "espeak-ng", "-v", "en-us", "-s", "145", "-w", str(path), FIXTURE,
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    )
                    if await process.wait() != 0:
                        raise RuntimeError("warmup_fixture_failed")
                    options = SpeechOptions(model=profile.model, language="en-US", chunk_size_ms=profile.chunk_size_ms,
                                            strip_language_tags=profile.strip_language_tags)
                    result = await transcribe_file(scheduled, path, options)
                    if not result["text"].strip():
                        raise RuntimeError("warmup_transcription_empty")
                state["ready"] = True
                LOG.info("speech runtime ready model=%s timings=%s", profile.model, runtime.timings)
            except Exception:
                state["error"] = "initialization_failed"
                LOG.exception("speech runtime initialization failed")
        initialization = asyncio.create_task(initialize()) if load else None
        yield
        state["draining"] = True
        scheduled.scheduler.draining = True
        if initialization and not initialization.done():
            # Initial model load uses a background thread: never exit midway
            # through a load while pretending a clean snapshot can be taken.
            await initialization
        await scheduled.scheduler.shutdown()
        observation.hardware.close()

    app = FastAPI(lifespan=lifespan)
    app.state.runtime_state = state
    app.state.scheduled_runtime = scheduled

    def runtime_identity():
        return getattr(runtime, "identity", lambda: {"capacity_status": "configured_not_measured"})()

    def observation_state():
        scheduler = scheduled.scheduler.snapshot()
        return {"ready": bool(state["ready"] and not scheduler["poisoned"]),
                "admitting": bool(state["ready"] and not state["draining"] and not scheduler["poisoned"]),
                "draining": state["draining"], "poisoned": scheduler["poisoned"],
                "active_sessions": state["active"], "pending_sessions": 0,
                "admission_policy": "bounded_reject_no_session_queue",
                "rejected_sessions_total": state["rejected"],
                "configured_max_sessions": max_sessions, "configured_max_batch_size": max_batch_size,
                "batch_wait_seconds": batch_wait_seconds,
                "queued_chunk_actions": scheduler["queued_actions"],
                "inflight_chunk_actions": scheduler["inflight_actions"],
                "queued_action_pcm_bytes": scheduler["queued_audio_bytes"],
                "framer_pcm_bytes": sum(scheduled.buffered.values()),
                "oldest_chunk_wait_seconds": scheduler["oldest_wait_seconds"]}

    observation = WorkerObservation(identity=runtime_identity, profile=profile.model_dump, state=observation_state)
    app.state.capacity_observation = observation

    def acquire():
        if not state["ready"] or state["draining"] or scheduled.scheduler.poisoned:
            state["rejected"] += 1
            events.labels("rejected").inc()
            raise HTTPException(503, "runtime_not_ready", headers={"retry-after": "2"})
        if state["active"] >= max_sessions:
            state["rejected"] += 1
            events.labels("rejected").inc()
            raise HTTPException(429, "runtime_busy", headers={"retry-after": "1"})
        state["active"] += 1
        active.set(state["active"])

    def release():
        state["active"] -= 1
        active.set(state["active"])

    @app.get("/healthz")
    async def health():
        return {"status": "alive", "backend_id": socket.gethostname()}

    @app.get("/readyz")
    async def ready():
        healthy = state["ready"] and not state["draining"] and not scheduled.scheduler.poisoned
        return JSONResponse({"ready": healthy, "active_sessions": state["active"],
                             "scheduler": scheduled.scheduler.snapshot(),
                             "runtime_identity": runtime_identity(),
                             "model": profile.model, "profile": profile.model_dump(),
                             "backend_id": socket.gethostname()},
                            status_code=200 if healthy else 503)

    @app.post("/drain")
    async def drain(request: Request):
        try:
            authorized_group(request.headers, private_token)
        except PermissionError:
            raise HTTPException(401, "private_gateway_authentication_required") from None
        state["draining"] = True
        # Already admitted files may still be downloading and must retain the
        # right to begin their decoder. Outer admission blocks new customers.
        return {"draining": True, "active_sessions": state["active"]}

    @app.get("/metrics")
    async def metrics(request: Request):
        try:
            authorized_group(request.headers, private_token)
        except PermissionError:
            raise HTTPException(401, "private_gateway_authentication_required") from None
        snapshot = scheduled.scheduler.snapshot()
        queue.set(snapshot["queued_actions"])
        inflight.set(snapshot["inflight_actions"])
        buffered.set(sum(scheduled.buffered.values()))
        oldest.set(snapshot["oldest_wait_seconds"])
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.get("/capacity-observation")
    async def capacity_observation(request: Request):
        # Unlike legacy cluster-private metrics, detailed identity observations
        # are never anonymously available, even when inference auth is optional.
        if private_token is None:
            raise HTTPException(503, "private_gateway_authentication_not_configured")
        try:
            authorized_group(request.headers, private_token)
        except PermissionError:
            raise HTTPException(401, "private_gateway_authentication_required") from None
        return await observation.sample()

    @app.post("/generate")
    async def generate(payload: FileRequest, request: Request):
        try:
            customer_group = authorized_group(request.headers, private_token)
        except PermissionError:
            raise HTTPException(401, "private_gateway_authentication_required") from None
        try:
            profile.require_match(payload.options)
        except ValueError:
            raise HTTPException(422, "runtime_profile_mismatch") from None
        acquire()
        group = scheduling_group.set(customer_group)
        try:
            with tempfile.TemporaryDirectory(prefix="fs2-speech-file-") as directory:
                path = Path(directory) / "audio"
                await download_audio(payload.audio, path, allowed_hosts)
                inference = asyncio.create_task(transcribe_file(scheduled, path, payload.options))
                try:
                    while not inference.done():
                        if await request.is_disconnected():
                            inference.cancel()
                            raise asyncio.CancelledError
                        await asyncio.wait({inference}, timeout=0.25)
                    result = await inference
                finally:
                    if not inference.done():
                        inference.cancel()
                    await asyncio.gather(inference, return_exceptions=True)
            audio.inc(result["audio_seconds"])
            duration.observe(result["processing_seconds"])
            total.labels("file", "completed").inc()
            identity = runtime_identity()
            revision = ("sha256:" + identity["checkpoint_sha256"]
                        if identity.get("checkpoint_kind") == "operator_pinned" else MODELS[profile.model].revision)
            return JSONResponse({**result, "model_revision": revision,
                                 "runtime_identity": identity},
                                headers={"x-backend-id": socket.gethostname()})
        except AudioInputError as exc:
            total.labels("file", "failed").inc()
            raise HTTPException(422, str(exc)) from None
        except asyncio.CancelledError:
            total.labels("file", "cancelled").inc()
            raise
        finally:
            scheduling_group.reset(group)
            release()

    @app.websocket("/v1/audio/stream")
    async def stream(websocket: WebSocket):
        try:
            customer_group = authorized_group(websocket.headers, private_token)
        except PermissionError:
            await websocket.close(code=1008)
            return
        try:
            acquire()
        except HTTPException as exc:
            await websocket.accept()
            await websocket.send_json({"type": "session.error", "code": exc.detail, "retryable": True})
            await websocket.close(code=1013)
            return
        group = scheduling_group.set(customer_group)
        outcome = "disconnected"

        async def messages():
            while True:
                event = await websocket.receive()
                if event["type"] == "websocket.disconnect":
                    return
                if event.get("bytes") is not None:
                    yield event["bytes"]
                elif event.get("text") is not None:
                    yield event["text"]

        async def send(event):
            nonlocal outcome
            if event["type"] == "session.completed":
                audio.inc(event["audio_seconds"])
                outcome = "completed"
            elif event["type"] in {"session.error", "session.cancelled"}:
                outcome = "failed" if event["type"] == "session.error" else "cancelled"
            elif event["type"] == "session.ready":
                event = {**event, "backend_id": socket.gethostname(), "runtime_identity": runtime_identity()}
            await asyncio.wait_for(websocket.send_json(event), timeout=30)

        try:
            await websocket.accept()
            await run_stream(scheduled, messages(), send, max_session_seconds=7200)
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass  # A disconnect cannot be acknowledged on the closed socket.
        except asyncio.CancelledError:
            # run_stream has already awaited decoder cleanup in its finally.
            # The transport task may now end without acknowledging a dead peer.
            outcome = "cancelled"
        finally:
            scheduling_group.reset(group)
            total.labels("live", outcome).inc()
            release()

    return app


def main():
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Presigned artifact URLs contain credentials.
    profile = RuntimeProfile.model_validate(json.loads(os.environ["FS2_SPEECH_PROFILE_JSON"]))
    max_sessions = int(os.environ.get("FS2_SPEECH_MAX_SESSIONS", "1"))
    max_batch_size = int(os.environ.get("FS2_SPEECH_MAX_BATCH_SIZE", "1"))
    batch_wait_seconds = float(os.environ.get("FS2_SPEECH_BATCH_WAIT_SECONDS", "0.005"))
    runtime = NeMoRuntime(profile, config_path=Path(
        "/opt/nemo/examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml"),
        max_sessions=max_sessions, max_batch_size=max_batch_size)
    checkpoint_path = os.environ.get("FS2_SPEECH_CHECKPOINT_PATH")
    checkpoint_sha = os.environ.get("FS2_SPEECH_CHECKPOINT_SHA256")
    if bool(checkpoint_path) != bool(checkpoint_sha):
        raise ValueError("checkpoint_path_and_sha_required_together")
    if checkpoint_path:
        runtime.bind_checkpoint(Path(checkpoint_path), checkpoint_sha)
    hosts = frozenset(filter(None, os.environ.get("FS2_SPEECH_ARTIFACT_HOSTS", "").split(",")))
    uvicorn.run(create_app(runtime, profile, allowed_hosts=hosts, max_sessions=max_sessions,
                           max_batch_size=max_batch_size, batch_wait_seconds=batch_wait_seconds),
                host="0.0.0.0", port=8000,
                loop="asyncio", ws_max_size=65536, ws_max_queue=2, timeout_graceful_shutdown=7205)


if __name__ == "__main__":
    main()
