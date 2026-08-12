"""OpenAI-shaped text-to-speech server for Kokoro-82M.

The defaults below are the contract: a Deploy URL cannot carry env vars, so a
one-click deploy runs this with nothing set. Keep them in sync with
config.json's configuration.env.
"""

from __future__ import annotations

import io
import os
import subprocess
import threading
import time
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from kokoro import KPipeline
from pydantic import BaseModel, Field

MODEL_ID = os.environ.get("MODEL_ID", "hexgrad/Kokoro-82M")
API_MODEL = "kokoro"
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "af_bella")
DEFAULT_LANG = os.environ.get("LANG_CODE", "a")
PORT = int(os.environ.get("PORT", "8000"))
SAMPLE_RATE = 24000
MIN_SPEED = 0.25
MAX_SPEED = 4.0

_pipelines: dict[str, KPipeline] = {}
# Kokoro loads weights once per lang_code; serialize synthesis on one GPU.
_synth_lock = threading.Lock()


def lang_code_for_voice(voice: str) -> str:
    prefix = voice.split("_", 1)[0]
    return {
        "af": "a",
        "am": "a",
        "bf": "b",
        "bm": "b",
        "jf": "j",
        "jm": "j",
        "zf": "z",
        "zm": "z",
        "ef": "e",
        "em": "e",
        "ff": "f",
        "hf": "h",
        "hm": "h",
        "if": "i",
        "im": "i",
        "pf": "p",
        "pm": "p",
    }.get(prefix, DEFAULT_LANG)


def get_pipeline(lang_code: str) -> KPipeline:
    pipeline = _pipelines.get(lang_code)
    if pipeline is None:
        pipeline = KPipeline(lang_code=lang_code)
        _pipelines[lang_code] = pipeline
    return pipeline


class SpeechRequest(BaseModel):
    input: str = Field(min_length=1)
    model: str | None = None
    voice: str = DEFAULT_VOICE
    response_format: str = "mp3"
    speed: float = 1.0


def synthesize(text: str, voice: str, speed: float) -> np.ndarray:
    lang_code = lang_code_for_voice(voice)
    pipeline = get_pipeline(lang_code)
    chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise HTTPException(500, "no audio generated")
    return np.concatenate(chunks)


def encode_audio(audio: np.ndarray, response_format: str) -> tuple[bytes, str]:
    fmt = response_format.lower()
    if fmt not in {"mp3", "wav"}:
        raise HTTPException(400, f"response_format must be mp3 or wav, got {response_format!r}")

    wav_buffer = io.BytesIO()
    sf.write(wav_buffer, audio, SAMPLE_RATE, format="WAV")
    wav_bytes = wav_buffer.getvalue()
    if fmt == "wav":
        return wav_bytes, "audio/wav"

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "mp3",
            "pipe:1",
        ],
        input=wav_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip() or "ffmpeg failed"
        raise HTTPException(500, f"mp3 encode failed: {detail}")
    if not proc.stdout:
        raise HTTPException(500, "mp3 encode returned empty output")
    return proc.stdout, "audio/mpeg"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    started = time.monotonic()
    print(f"loading Kokoro default voice={DEFAULT_VOICE!r} lang={DEFAULT_LANG!r}", flush=True)
    get_pipeline(DEFAULT_LANG)
    print(f"ready in {time.monotonic() - started:.1f}s", flush=True)
    yield


app = FastAPI(title="Kokoro text-to-speech", version="1", lifespan=lifespan)


@app.get("/v1/models")
def list_models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": API_MODEL,
                "object": "model",
                "owned_by": "nebius-serverless-cookbook",
            }
        ],
    }


@app.post("/v1/audio/speech")
def create_speech(req: SpeechRequest) -> Response:
    if req.model and req.model not in {API_MODEL, MODEL_ID}:
        raise HTTPException(400, f"this endpoint serves {API_MODEL!r}, not {req.model!r}")
    if not MIN_SPEED <= req.speed <= MAX_SPEED:
        raise HTTPException(400, f"speed must be {MIN_SPEED}..{MAX_SPEED}")

    try:
        with _synth_lock:
            audio = synthesize(req.input, req.voice, req.speed)
            payload, media_type = encode_audio(audio, req.response_format)
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"synthesis failed: {type(exc).__name__}: {exc}") from exc

    return Response(content=payload, media_type=media_type)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
