"""OpenAI-shaped text-to-image server for Sana (Diffusers SanaPipeline).

The defaults below are the contract: a Deploy URL cannot carry env vars, so a
one-click deploy runs this with nothing set. Keep them in sync with
config.json's configuration.env.
"""

from __future__ import annotations

import base64
import io
import os
import threading
import time
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import torch
import uvicorn
from diffusers import SanaPipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_ID = os.environ.get("MODEL_ID", "Efficient-Large-Model/Sana_1600M_1024px_diffusers")
MODEL_VARIANT = os.environ.get("MODEL_VARIANT", "fp16")
IMAGE_SIZE = int(os.environ.get("IMAGE_SIZE", "1024"))
INFERENCE_STEPS = int(os.environ.get("INFERENCE_STEPS", "20"))
GUIDANCE_SCALE = float(os.environ.get("GUIDANCE_SCALE", "4.5"))
MAX_IMAGES = int(os.environ.get("MAX_IMAGES", "4"))
MAX_STEPS = int(os.environ.get("MAX_STEPS", "100"))
MAX_SIDE = int(os.environ.get("MAX_SIDE", "2048"))
PORT = int(os.environ.get("PORT", "8000"))

_pipe: SanaPipeline | None = None
# One GPU, one diffusion pass at a time: FastAPI runs sync handlers in a
# threadpool, so without this two requests would interleave on the same device.
_gpu_lock = threading.Lock()


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = None
    n: int = 1
    size: str | None = None
    response_format: str = "b64_json"
    # Sana's encode_prompt always preprocesses this when guidance is on, and it
    # cannot take None: keep the pipeline's own "" default.
    negative_prompt: str = ""
    num_inference_steps: int | None = None
    guidance_scale: float | None = None
    seed: int | None = None


def load_pipeline() -> SanaPipeline:
    if not torch.cuda.is_available():
        raise RuntimeError("no CUDA device: deploy on a GPU platform/preset")
    pipe = SanaPipeline.from_pretrained(
        MODEL_ID,
        variant=MODEL_VARIANT or None,
        torch_dtype=torch.float16,
    )
    pipe.to("cuda")
    # Sana's published recipe: fp16 transformer, but the text encoder and VAE
    # must stay bf16/fp32 or generations come back black.
    pipe.text_encoder.to(torch.bfloat16)
    pipe.vae.to(torch.bfloat16)
    pipe.set_progress_bar_config(disable=True)
    return pipe


def parse_size(size: str | None) -> tuple[int, int]:
    if not size:
        return IMAGE_SIZE, IMAGE_SIZE
    try:
        width, height = (int(part) for part in size.lower().split("x", 1))
    except ValueError:
        raise HTTPException(400, f"size must look like 1024x1024, got {size!r}") from None
    for side in (width, height):
        if not 256 <= side <= MAX_SIDE:
            raise HTTPException(400, f"size sides must be 256..{MAX_SIDE}, got {size!r}")
        if side % 32:
            raise HTTPException(400, f"size sides must be multiples of 32, got {size!r}")
    return width, height


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _pipe
    started = time.monotonic()
    print(f"loading {MODEL_ID} variant={MODEL_VARIANT!r}", flush=True)
    _pipe = load_pipeline()
    print(f"ready in {time.monotonic() - started:.1f}s", flush=True)
    yield


app = FastAPI(title="Sana text-to-image", version="1", lifespan=lifespan)


@app.get("/v1/models")
def list_models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "owned_by": "nebius-serverless-cookbook"}],
    }


@app.post("/v1/images/generations")
def generate(req: GenerationRequest) -> dict[str, object]:
    if _pipe is None:
        raise HTTPException(503, "model still loading")
    if req.response_format != "b64_json":
        raise HTTPException(400, "only response_format=b64_json is supported (no object storage)")
    if not 1 <= req.n <= MAX_IMAGES:
        raise HTTPException(400, f"n must be 1..{MAX_IMAGES}")
    if req.model and req.model != MODEL_ID:
        raise HTTPException(400, f"this endpoint serves {MODEL_ID!r}, not {req.model!r}")

    steps = INFERENCE_STEPS if req.num_inference_steps is None else req.num_inference_steps
    if not 1 <= steps <= MAX_STEPS:
        raise HTTPException(400, f"num_inference_steps must be 1..{MAX_STEPS}")
    guidance = GUIDANCE_SCALE if req.guidance_scale is None else req.guidance_scale

    width, height = parse_size(req.size)
    generator = None
    if req.seed is not None:
        generator = torch.Generator(device="cuda").manual_seed(req.seed)

    try:
        with _gpu_lock:
            images = _pipe(
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                width=width,
                height=height,
                num_images_per_prompt=req.n,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=generator,
            ).images
    except Exception as exc:
        # Without this the client sees a bare 500 and the reason lives only in the logs.
        traceback.print_exc()
        raise HTTPException(500, f"generation failed: {type(exc).__name__}: {exc}") from exc

    data = []
    for image in images:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data.append({"b64_json": base64.b64encode(buffer.getvalue()).decode("ascii")})
    return {"created": int(time.time()), "model": MODEL_ID, "data": data}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
