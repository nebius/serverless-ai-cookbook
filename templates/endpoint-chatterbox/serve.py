"""OpenAI-shaped text-to-speech server for Chatterbox (Resemble AI).

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
from pathlib import Path

import soundfile as sf
import torch
import uvicorn
from chatterbox.tts import ChatterboxTTS
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

MODEL_ID = os.environ.get("MODEL_ID", "ResembleAI/chatterbox")
API_MODEL = "tts-1"
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "Emily.wav")
CFG_WEIGHT = float(os.environ.get("CFG_WEIGHT", "0.5"))
EXAGGERATION = float(os.environ.get("EXAGGERATION", "0.5"))
VOICES_DIR = Path(os.environ.get("VOICES_DIR", "/app/voices"))
PORT = int(os.environ.get("PORT", "8000"))

_model: ChatterboxTTS | None = None
# One GPU, one synthesis pass at a time.
_synth_lock = threading.Lock()


class SpeechRequest(BaseModel):
    input: str = Field(min_length=1)
    model: str | None = None
    voice: str = DEFAULT_VOICE
    response_format: str = "wav"
    speed: float = 1.0


def resolve_voice_path(voice: str) -> str | None:
    if voice in {"", "default", "builtin"}:
        return None
    name = voice if voice.endswith(".wav") else f"{voice}.wav"
    path = VOICES_DIR / name
    if not path.is_file():
        bundled = sorted(p.name for p in VOICES_DIR.glob("*.wav"))
        hint = ", ".join(bundled[:8]) + ("…" if len(bundled) > 8 else "")
        raise HTTPException(
            400,
            f"unknown voice {voice!r}; bundled presets include: {hint or '(none)'}",
        )
    return str(path)


def load_model() -> ChatterboxTTS:
    if not torch.cuda.is_available():
        raise RuntimeError("no CUDA device: deploy on a GPU platform/preset")
    return ChatterboxTTS.from_pretrained(device="cuda")


def synthesize(text: str, voice: str) -> tuple[torch.Tensor, int]:
    if _model is None:
        raise HTTPException(503, "model still loading")
    prompt_path = resolve_voice_path(voice)
    kwargs: dict[str, object] = {
        "cfg_weight": CFG_WEIGHT,
        "exaggeration": EXAGGERATION,
    }
    if prompt_path is not None:
        kwargs["audio_prompt_path"] = prompt_path
    wav = _model.generate(text, **kwargs)
    return wav, int(_model.sr)


def tensor_to_wav_bytes(wav: torch.Tensor, sample_rate: int) -> bytes:
    audio = wav.detach().cpu().float().numpy()
    if audio.ndim > 1:
        audio = audio.squeeze()
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV")
    return buffer.getvalue()


def encode_audio(wav: torch.Tensor, sample_rate: int, response_format: str) -> tuple[bytes, str]:
    fmt = response_format.lower()
    if fmt not in {"mp3", "wav"}:
        raise HTTPException(400, f"response_format must be mp3 or wav, got {response_format!r}")

    wav_bytes = tensor_to_wav_bytes(wav, sample_rate)
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
    global _model
    started = time.monotonic()
    print(f"loading {MODEL_ID} default_voice={DEFAULT_VOICE!r}", flush=True)
    _model = load_model()
    # Warm the default preset so the first client request is not a cold clone pass.
    with _synth_lock:
        synthesize("Ready.", DEFAULT_VOICE)
    print(f"ready in {time.monotonic() - started:.1f}s", flush=True)
    yield


app = FastAPI(title="Chatterbox text-to-speech", version="1", lifespan=lifespan)


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
    if req.model and req.model not in {API_MODEL, MODEL_ID, "chatterbox"}:
        raise HTTPException(400, f"this endpoint serves {API_MODEL!r}, not {req.model!r}")
    if req.speed != 1.0:
        raise HTTPException(400, "speed is not supported by Chatterbox; omit or set 1.0")

    try:
        with _synth_lock:
            wav, sample_rate = synthesize(req.input, req.voice)
            payload, media_type = encode_audio(wav, sample_rate, req.response_format)
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"synthesis failed: {type(exc).__name__}: {exc}") from exc

    if not payload:
        raise HTTPException(500, "synthesis returned empty audio")
    return Response(content=payload, media_type=media_type)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
