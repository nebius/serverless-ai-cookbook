"""Bounded download, decoding and complete-file transcription through streaming ASR."""

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator
from contextlib import aclosing
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import Field

from .contracts import SpeechOptions, StrictContract
from .events import assemble_transcript
from .stream import RuntimePort, run_stream

MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_AUDIO_SECONDS = 7200
MEDIA_TYPES = ("audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/ogg",
               "audio/webm", "audio/flac", "audio/aac", "video/mp4", "video/webm")


class AudioInputError(ValueError):
    pass


class DownloadAudio(StrictContract):
    """Internal only: the gateway mints this from a tenant-owned artifact reference."""

    url: str = Field(min_length=8, max_length=8192)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(gt=0, le=MAX_FILE_BYTES)
    media_type: str = Field(min_length=3, max_length=128)


async def download_audio(source: DownloadAudio, destination: Path, allowed_hosts: frozenset[str]) -> None:
    url = urlsplit(source.url)
    if (url.scheme != "https" or url.hostname not in allowed_hosts or url.username or url.password
            or url.port not in (None, 443) or url.fragment or source.media_type not in MEDIA_TYPES):
        raise AudioInputError("invalid_audio_artifact")
    digest, size = hashlib.sha256(), 0
    async with httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False) as client:
        async with client.stream("GET", source.url) as response:
            if response.status_code != 200:
                raise AudioInputError("audio_artifact_unavailable")
            with destination.open("wb") as handle:
                async for chunk in response.aiter_bytes(65536):
                    size += len(chunk)
                    if size > source.size_bytes:
                        raise AudioInputError("audio_artifact_size_mismatch")
                    digest.update(chunk)
                    handle.write(chunk)
    if size != source.size_bytes or digest.hexdigest() != source.sha256:
        raise AudioInputError("audio_artifact_checksum_mismatch")


async def decoded_pcm(path: Path, *, max_seconds: float = MAX_AUDIO_SECONDS) -> AsyncIterator[bytes]:
    """Decode incrementally; never buffer a recording or truncate it at the limit."""
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
        "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=65536,
    )
    size = 0
    tail = b""
    try:
        assert process.stdout is not None
        while chunk := await process.stdout.read(32768):
            size += len(chunk)
            if size > max_seconds * 32000:
                raise AudioInputError("audio_duration_exceeded")
            chunk = tail + chunk
            boundary = len(chunk) - len(chunk) % 2
            tail = chunk[boundary:]
            if boundary:
                yield chunk[:boundary]
        if await process.wait() != 0 or size == 0 or tail:
            raise AudioInputError("audio_decode_failed")
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except TimeoutError:
                process.kill()
                await process.wait()


async def transcribe_file(runtime: RuntimePort, path: Path, options: SpeechOptions) -> dict:
    """Feed the entire file and return finals only; no concatenation of partials."""
    started = time.monotonic()
    finals, state = [], {}

    async def messages():
        yield json.dumps({"type": "session.start", "options": options.model_dump()})
        try:
            async for chunk in decoded_pcm(path):
                yield chunk
        except AudioInputError as exc:
            state["decode_error"] = str(exc)
            raise
        yield '{"type":"input.finish"}'

    async def receive(event):
        kind = event["type"]
        if kind == "transcript.final":
            finals.append(event)
        elif kind == "session.completed":
            state["completed"] = event
        elif kind == "session.error":
            state["error"] = event["code"]

    async with aclosing(messages()) as source:
        await run_stream(runtime, source, receive, max_session_seconds=MAX_AUDIO_SECONDS + 300)
    if "completed" not in state:
        raise AudioInputError(state.get("decode_error", state.get("error", "transcription_incomplete")))
    return {
        "text": assemble_transcript(finals),
        "segments": finals,
        "audio_seconds": state["completed"]["audio_seconds"],
        "processing_seconds": time.monotonic() - started,
        "model": options.model,
        "language": options.resolved_language,
    }
