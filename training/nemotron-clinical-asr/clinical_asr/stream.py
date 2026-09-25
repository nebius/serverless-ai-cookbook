"""Bounded live-audio lifecycle, independent of the public gateway's auth.

The gateway must authorize and admit before calling this runner. Its transport
adapter supplies messages/events and must bound its own WebSocket receive queue.
This module does not expose a socket or create a separate credential system.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol
from uuid import uuid4

from pydantic import ValidationError

from .contracts import SpeechOptions, StreamStart
from .events import TranscriptEvents
from .framing import PCMFrame, PCMFramer


class RuntimePort(Protocol):
    @property
    def frame_samples(self) -> int: ...
    def begin(self, options: SpeechOptions) -> int: ...
    def step(self, stream_id: int, frame: PCMFrame, options: SpeechOptions) -> Any: ...
    def close(self, stream_id: int) -> None: ...


async def _gpu_call(function: Callable[..., Any], *args: Any) -> Any:
    """Cancellation must not release buffers while the GPU step still uses them."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


async def run_stream(
    runtime: RuntimePort,
    messages: AsyncIterator[bytes | str],
    send: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    idle_seconds: float = 30.0,
    max_session_seconds: float = 1800.0,
    max_message_bytes: int = 65536,
) -> None:
    """Run an already-admitted session, releasing all state on every exit.

    Client: session.start JSON, binary PCM messages, then input.finish or
    session.cancel JSON. There is no invisible reconnect/resume: the client must
    create a new session after an error and deliberately choose audio to replay.
    """
    if idle_seconds <= 0 or max_session_seconds <= 0:
        raise ValueError("session deadlines must be positive")
    stream_id: int | None = None
    session_id = str(uuid4())
    phase = "start"

    async def receive() -> bytes | str:
        return await asyncio.wait_for(anext(messages), timeout=idle_seconds)

    async def error(code: str, *, retryable: bool = False) -> None:
        await send({"type": "session.error", "session_id": session_id, "code": code, "retryable": retryable})

    try:
        async with asyncio.timeout(max_session_seconds):
            start_message = await receive()
            if not isinstance(start_message, str) or len(start_message.encode("utf-8")) > 4096:
                await error("expected_session_start")
                return
            start = StreamStart.model_validate_json(start_message)
            stream_id = runtime.begin(start.options)
            framer = PCMFramer(runtime.frame_samples, max_message_bytes=max_message_bytes)
            events = TranscriptEvents(session_id)
            phase = "audio"
            await send({"type": "session.ready", "session_id": session_id,
                        "audio": start.audio.model_dump(), "options": start.options.model_dump()})

            async def process(frame: PCMFrame) -> None:
                output = await _gpu_call(runtime.step, stream_id, frame, start.options)
                for event in events.update(
                    final=output.final_transcript, partial=output.partial_transcript, last=frame.last,
                ):
                    value = event.to_dict()
                    if event.type == "transcript.final":
                        # Preserve the upstream acoustic alignment. In the
                        # default profile NeMo can emit placeholder confidence;
                        # do not advertise it as a measured probability.
                        confidence = bool(getattr(getattr(runtime, "profile", None), "confidence", False))
                        value["granularity"] = start.options.output_granularity
                        value["items"] = [
                            {"text": segment.text, "start_seconds": float(segment.start),
                             "end_seconds": float(segment.end),
                             "confidence": float(segment.conf) if confidence else None}
                            for segment in (getattr(output, "final_segments", None) or [])
                        ]
                    await send(value)

            while True:
                message = await receive()
                if isinstance(message, bytes):
                    for frame in framer.push(message):
                        await process(frame)
                    continue
                if len(message.encode("utf-8")) > 4096:
                    await error("control_message_too_large")
                    return
                control = json.loads(message)
                if control == {"type": "session.cancel"}:
                    await _gpu_call(runtime.close, stream_id)
                    stream_id = None
                    await send({"type": "session.cancelled", "session_id": session_id})
                    return
                if control != {"type": "input.finish"}:
                    await error("invalid_control_message")
                    return
                await process(framer.finish())
                await _gpu_call(runtime.close, stream_id)
                stream_id = None
                await send({"type": "session.completed", "session_id": session_id,
                            "audio_seconds": framer.total_samples / 16000, "last_sequence": events.sequence})
                return
    except TimeoutError:
        await error("session_timeout", retryable=True)
    except StopAsyncIteration:
        await error("stream_disconnected", retryable=True)
    except (ValidationError, json.JSONDecodeError):
        await error("invalid_session_options" if phase == "start" else "invalid_control_message")
    except ValueError as exc:
        # These errors originate from bounded framing/profile validation, not
        # arbitrary backend stack traces. Expose a stable code, not raw text.
        code = "runtime_profile_mismatch" if str(exc).startswith("runtime_profile_mismatch") else "invalid_audio"
        await error(code)
    except RuntimeError as exc:
        code = "runtime_busy" if str(exc) == "runtime_busy" else "runtime_failure"
        await error(code, retryable=True)
    except Exception:
        await error("runtime_failure", retryable=True)
    finally:
        if stream_id is not None:
            await _gpu_call(runtime.close, stream_id)
        # A cancelled task intentionally has no success event. The transport
        # closes the connection; the gateway must account for cancellation.
