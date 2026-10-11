#!/usr/bin/env python3
"""Minimal FLUX.2-dev + LoRA image-generation server for a Nebius Serverless
AI Endpoint.

- loads black-forest-labs/FLUX.2-dev (gated: HF_TOKEN required) with the
  diffusers Flux2Pipeline, applies your subject LoRA via load_lora_weights
  (PEFT-backed) in a background thread, and reports readiness on /healthz
- POST /generate renders one image; auth is fail-closed bearer-token:
  if API_TOKEN / API_TOKEN_FILE is not configured, every request is refused.
  (The platform `--auth token` proxy is the first auth layer; this is
  defense in depth inside the container.)
- response_format "base64" returns the PNG inline; "url" uploads it to
  Object Storage via boto3 and returns a presigned URL - required for
  ChatGPT Actions, whose responses are truncated at roughly 100 KB.

Environment:
  MODEL_ID        base model (default black-forest-labs/FLUX.2-dev)
  LORA_PATH       path to the adapter .safetensors (e.g. on the bucket mount)
  TRIGGER_WORD    optional; prepended as "<TRIGGER_WORD> <TRIGGER_CLASS>, "
                  when the prompt does not already contain it
  TRIGGER_CLASS   class noun used with TRIGGER_WORD (default "person")
  API_TOKEN or API_TOKEN_FILE   bearer token for /generate (fail-closed)
  S3_BUCKET, S3_ENDPOINT_URL, S3_PREFIX, URL_TTL_SECONDS,
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY   only needed for "url" mode
"""
import base64
import hmac
import io
import os
import secrets as pysecrets
import threading
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

MODEL_ID = os.environ.get("MODEL_ID", "black-forest-labs/FLUX.2-dev")
LORA_PATH = os.environ.get("LORA_PATH", "")
TRIGGER_WORD = os.environ.get("TRIGGER_WORD", "")
TRIGGER_CLASS = os.environ.get("TRIGGER_CLASS", "person")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "")
S3_PREFIX = os.environ.get("S3_PREFIX", "flux-avatar/generated/")
URL_TTL = int(os.environ.get("URL_TTL_SECONDS", "3600"))

app = FastAPI(title="flux-avatar-serving")

_pipe = None
_pipe_lock = threading.Lock()
_state = {"ready": False, "error": None}


def _load_pipeline():
    global _pipe
    try:
        import torch
        from diffusers import Flux2Pipeline

        pipe = Flux2Pipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
        if LORA_PATH:
            pipe.load_lora_weights(LORA_PATH)
        pipe.to("cuda")
        _pipe = pipe
        _state["ready"] = True
    except Exception as exc:  # surfaced via /healthz
        _state["error"] = f"{type(exc).__name__}: {exc}"


threading.Thread(target=_load_pipeline, daemon=True).start()


def _expected_token() -> str:
    token = os.environ.get("API_TOKEN", "")
    token_file = os.environ.get("API_TOKEN_FILE", "")
    if not token and token_file and os.path.exists(token_file):
        with open(token_file, encoding="utf-8") as fh:
            token = fh.read().strip()
    return token


def _check_auth(authorization: Optional[str]) -> None:
    expected = _expected_token()
    if not expected:
        # Fail closed: an unconfigured server must not serve anyone.
        raise HTTPException(503, "API_TOKEN not configured; refusing requests")
    supplied = ""
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization[len("Bearer "):].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "missing or invalid bearer token")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    width: int = 1024
    height: int = 1024
    steps: int = Field(default=28, ge=1, le=64)
    guidance_scale: float = Field(default=4.0, ge=0.0, le=10.0)
    seed: Optional[int] = Field(default=None, ge=0, lt=2**31)
    response_format: str = "base64"  # "base64" | "url"


@app.get("/healthz")
def healthz():
    return {
        "ready": _state["ready"],
        "error": _state["error"],
        "model": MODEL_ID,
        "lora_loaded": _state["ready"] and bool(LORA_PATH),
    }


@app.post("/generate")
def generate(req: GenerateRequest,
             authorization: Optional[str] = Header(default=None)):
    _check_auth(authorization)
    if not _state["ready"]:
        detail = "model is still loading"
        if _state["error"]:
            detail = f"model failed to load: {_state['error']}"
        raise HTTPException(503, detail)
    for name, value in (("width", req.width), ("height", req.height)):
        if value % 64 != 0 or not 256 <= value <= 1536:
            raise HTTPException(
                400, f"{name} must be a multiple of 64 in [256, 1536]")
    if req.response_format not in ("base64", "url"):
        raise HTTPException(400, "response_format must be 'base64' or 'url'")
    if req.response_format == "url" and not (S3_BUCKET and S3_ENDPOINT_URL):
        raise HTTPException(
            400, "url mode is not configured (S3_BUCKET / S3_ENDPOINT_URL)")

    prompt = req.prompt
    if TRIGGER_WORD and TRIGGER_WORD.lower() not in prompt.lower():
        prompt = f"{TRIGGER_WORD} {TRIGGER_CLASS}, {prompt}"

    seed = req.seed if req.seed is not None else pysecrets.randbelow(2**31)

    import torch

    generator = torch.Generator(device="cuda").manual_seed(seed)
    started = time.time()
    with _pipe_lock:  # one GPU - serialize generations
        image = _pipe(
            prompt=prompt,
            width=req.width,
            height=req.height,
            num_inference_steps=req.steps,
            guidance_scale=req.guidance_scale,
            generator=generator,
        ).images[0]
    elapsed = round(time.time() - started, 1)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    png = buf.getvalue()

    if req.response_format == "base64":
        return {
            "image_base64": base64.b64encode(png).decode(),
            "seed": seed,
            "prompt": prompt,
            "elapsed_seconds": elapsed,
        }

    import boto3

    key = f"{S3_PREFIX}{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.png"
    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT_URL)
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=png, ContentType="image/png")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=URL_TTL,
    )
    return {
        "image_url": url,
        "expires_in_seconds": URL_TTL,
        "seed": seed,
        "prompt": prompt,
        "elapsed_seconds": elapsed,
    }
