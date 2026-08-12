"""Sync OpenAI-shaped wrapper around upstream ACE-Step acestep-api.

Upstream ACE-Step exposes an async task API (`POST /release_task` +
`POST /query_result`). This process starts acestep-api on an internal port and
blocks on catalog smoke via `POST /v1/audio/generations` (raw MP3/WAV body).

Defaults below are the one-click contract — keep them aligned with config.json
configuration.env.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urljoin

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

API_MODEL = os.environ.get("API_MODEL", "ACE-Step/Ace-Step1.5")
UPSTREAM_BASE = os.environ.get("UPSTREAM_BASE", "http://127.0.0.1:8001").rstrip("/")
PORT = int(os.environ.get("PORT", "8000"))
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "2.0"))
POLL_TIMEOUT_S = float(os.environ.get("POLL_TIMEOUT_S", "900"))
READY_TIMEOUT_S = float(os.environ.get("READY_TIMEOUT_S", "3600"))

_upstream_proc: subprocess.Popen[str] | None = None
_gen_lock = threading.Lock()


class AudioGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str = Field(min_length=1)
    model: str | None = None
    task_type: str = "text2music"
    thinking: bool = False
    audio_duration: float | None = None
    inference_steps: int | None = None
    audio_format: str = "mp3"
    lyrics: str = ""


def upstream_payload(req: AudioGenerationRequest) -> dict[str, Any]:
    body = req.model_dump(exclude_none=True)
    catalog_model = body.pop("model", None)
    if catalog_model and catalog_model not in {API_MODEL, "ACE-Step/Ace-Step1.5"}:
        body["model"] = catalog_model
    return body


def unwrap_upstream(payload: dict[str, Any]) -> Any:
    if payload.get("code") not in (None, 200):
        raise HTTPException(
            int(payload.get("code") or 500),
            str(payload.get("error") or "upstream error"),
        )
    return payload.get("data")


def wait_for_upstream(client: httpx.Client) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_S
    last_err = ""
    while time.monotonic() < deadline:
        if _upstream_proc is not None and _upstream_proc.poll() is not None:
            raise RuntimeError(f"acestep-api exited early with code {_upstream_proc.returncode}")
        for path in ("/health", "/v1/models"):
            try:
                resp = client.get(path, timeout=10.0)
                if resp.status_code == 200:
                    print(f"upstream ready ({path})", flush=True)
                    return
            except httpx.HTTPError as exc:
                last_err = str(exc)
        time.sleep(2.0)
    raise RuntimeError(f"upstream not ready within {READY_TIMEOUT_S:.0f}s: {last_err}")


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def start_upstream() -> subprocess.Popen[str]:
    host = os.environ.get("ACESTEP_API_HOST", "127.0.0.1")
    port = os.environ.get("ACESTEP_API_PORT", "8001")
    # DiT-only by default. H100 auto-enables the 5Hz LM unless ACESTEP_INIT_LLM=false;
    # vLLM LM bring-up has segfaulted on Nebius (exit -11), and catalog smoke uses
    # thinking=false so the LM is not required.
    cmd = [
        "acestep-api",
        "--host",
        host,
        "--port",
        port,
    ]
    if _env_truthy("ACESTEP_INIT_LLM", "false"):
        cmd.append("--init-llm")
    print(f"starting upstream: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=os.environ.copy(),
    )


def poll_task(client: httpx.Client, task_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        resp = client.post(
            "/query_result",
            json={"task_id_list": [task_id]},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = unwrap_upstream(resp.json())
        if not isinstance(data, list) or not data:
            time.sleep(POLL_INTERVAL_S)
            continue
        item = data[0]
        status = item.get("status")
        if status == 0:
            time.sleep(POLL_INTERVAL_S)
            continue
        if status == 2:
            detail = item.get("result") or item.get("error") or "generation failed"
            raise HTTPException(500, f"ACE-Step task failed: {detail}")
        if status != 1:
            time.sleep(POLL_INTERVAL_S)
            continue
        raw = item.get("result")
        if isinstance(raw, str):
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return parsed[0]
            if isinstance(parsed, dict):
                return parsed
        if isinstance(raw, list) and raw:
            return raw[0]
        if isinstance(raw, dict):
            return raw
        raise HTTPException(500, "ACE-Step returned success without audio metadata")
    raise HTTPException(504, f"generation timed out after {POLL_TIMEOUT_S:.0f}s")


def fetch_audio(client: httpx.Client, result_item: dict[str, Any], fmt: str) -> tuple[bytes, str]:
    file_ref = result_item.get("file") or result_item.get("url")
    if not isinstance(file_ref, str) or not file_ref:
        raise HTTPException(500, "ACE-Step result missing audio file reference")

    if file_ref.startswith("http://") or file_ref.startswith("https://"):
        url = file_ref
    elif file_ref.startswith("/"):
        url = urljoin(UPSTREAM_BASE + "/", file_ref.lstrip("/"))
    else:
        url = f"{UPSTREAM_BASE}/v1/audio?path={file_ref}"

    resp = client.get(url, timeout=120.0)
    resp.raise_for_status()
    if not resp.content:
        raise HTTPException(500, "downloaded audio is empty")
    media = "audio/wav" if fmt.lower() == "wav" else "audio/mpeg"
    return resp.content, media


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _upstream_proc
    started = time.monotonic()
    _upstream_proc = start_upstream()
    with httpx.Client(base_url=UPSTREAM_BASE) as client:
        wait_for_upstream(client)
    print(f"wrapper ready in {time.monotonic() - started:.1f}s", flush=True)
    try:
        yield
    finally:
        if _upstream_proc and _upstream_proc.poll() is None:
            _upstream_proc.terminate()
            try:
                _upstream_proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                _upstream_proc.kill()


app = FastAPI(title="ACE-Step sync text-to-audio", version="1", lifespan=lifespan)


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


@app.post("/v1/audio/generations")
def create_audio_generation(req: AudioGenerationRequest) -> Response:
    if req.model and req.model not in {API_MODEL, "ACE-Step/Ace-Step1.5"}:
        raise HTTPException(400, f"this endpoint serves {API_MODEL!r}, not {req.model!r}")
    if req.audio_format.lower() not in {"mp3", "wav"}:
        raise HTTPException(400, "audio_format must be mp3 or wav")

    try:
        with _gen_lock, httpx.Client(base_url=UPSTREAM_BASE, timeout=900.0) as client:
            release = client.post("/release_task", json=upstream_payload(req))
            release.raise_for_status()
            data = unwrap_upstream(release.json())
            if not isinstance(data, dict) or not data.get("task_id"):
                raise HTTPException(502, "upstream did not return task_id")
            task_id = str(data["task_id"])
            result_item = poll_task(client, task_id)
            payload, media_type = fetch_audio(client, result_item, req.audio_format)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise HTTPException(exc.response.status_code, f"upstream HTTP error: {detail}") from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"generation failed: {type(exc).__name__}: {exc}") from exc

    if not payload:
        raise HTTPException(500, "generation returned empty audio")
    return Response(content=payload, media_type=media_type)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
