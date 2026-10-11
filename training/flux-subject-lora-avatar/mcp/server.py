#!/usr/bin/env python3
"""MCP server exposing your personal FLUX.2 LoRA endpoint to Claude (or any
MCP client): generate images of yourself, plus start/stop/status tools so the
model can manage the on-demand GPU endpoint for you.

Environment (set in your MCP client config):
  ENDPOINT_ID      Nebius endpoint id (aiendpoint-...). Enables start/stop/
                   status via the nebius CLI AND call-time URL resolution.
  AUTH_TOKEN_FILE  path to the bearer-token file written by serve.sh
                   (or AUTH_TOKEN with the literal token - file preferred)
  ENDPOINT_URL     optional static override of the endpoint URL. NOTE: the
                   HTTPS hostname changes on every endpoint stop/start, so
                   prefer ENDPOINT_ID and let this server resolve the current
                   URL at call time.
  NEBIUS_PROFILE   optional nebius CLI profile name
  TRIGGER_WORD     your trigger token (default TOK4ME)
  TRIGGER_CLASS    class noun (default person)
  OUTPUT_DIR       where generated PNGs are saved (default ~/flux-avatar-images)

Run: pip install mcp; then register with your client (see the README).
Secrets are read at call time and never logged or returned to the model.
"""
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional

from mcp.server.fastmcp import FastMCP, Image

ENDPOINT_ID = os.environ.get("ENDPOINT_ID", "")
ENDPOINT_URL = os.environ.get("ENDPOINT_URL", "")
TRIGGER_WORD = os.environ.get("TRIGGER_WORD", "TOK4ME")
TRIGGER_CLASS = os.environ.get("TRIGGER_CLASS", "person")
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR", os.path.expanduser("~/flux-avatar-images"))


def _nebius_cmd() -> list:
    cmd = ["nebius"]
    profile = os.environ.get("NEBIUS_PROFILE", "")
    if profile:
        cmd += ["--profile", profile]
    return cmd + ["ai", "endpoint"]


mcp = FastMCP(
    "flux-avatar",
    instructions=(
        "Generate photorealistic images of the owner's trained likeness via "
        "a private FLUX.2 LoRA endpoint. The endpoint is stopped when idle "
        "to save GPU cost: call avatar_endpoint_status first; if it is not "
        "running, call avatar_endpoint_start and poll status until ready "
        "(~15-30 min), then call generate_avatar_image. Stop the endpoint "
        "again when the user is done generating."
    ),
)


def _auth_token() -> str:
    token = os.environ.get("AUTH_TOKEN", "")
    token_file = os.environ.get("AUTH_TOKEN_FILE", "")
    if not token and token_file and os.path.exists(token_file):
        with open(token_file, encoding="utf-8") as fh:
            token = fh.read().strip()
    if not token:
        raise RuntimeError("set AUTH_TOKEN_FILE (or AUTH_TOKEN) in the MCP "
                           "server environment")
    return token


def _endpoint_url() -> str:
    """Resolve the CURRENT endpoint URL. The tunnel hostname changes on every
    stop/start cycle, so when ENDPOINT_ID is set we always ask the CLI."""
    if ENDPOINT_ID:
        out = subprocess.run(
            _nebius_cmd() + ["get", ENDPOINT_ID, "--format",
                             "jsonpath={.status.public_endpoints[0]}"],
            capture_output=True, text=True, timeout=60,
        )
        url = out.stdout.strip().strip('"')
        if url.startswith("http"):
            return url.rstrip("/")
    if ENDPOINT_URL:
        return ENDPOINT_URL.rstrip("/")
    raise RuntimeError("set ENDPOINT_ID (preferred) or ENDPOINT_URL in the "
                       "MCP server environment")


def _http(path: str, body=None, timeout=600):
    req = urllib.request.Request(
        _endpoint_url() + path,
        data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET",
    )
    req.add_header("Authorization", "Bearer " + _auth_token())
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except Exception:
            payload = {}
        return exc.code, payload


def _cli_state() -> str:
    if not ENDPOINT_ID:
        return "UNKNOWN (ENDPOINT_ID not set)"
    out = subprocess.run(
        _nebius_cmd() + ["get", ENDPOINT_ID, "--format",
                         "jsonpath={.status.state}"],
        capture_output=True, text=True, timeout=60,
    )
    return (out.stdout or out.stderr).strip().strip('"') or "UNKNOWN"


@mcp.tool()
def avatar_endpoint_status() -> str:
    """Check whether the avatar image endpoint is running and ready.

    Returns the platform state (RUNNING/STOPPED/STARTING/...) and, when
    running, whether the model finished loading. Generation only works when
    state=RUNNING and ready=true.
    """
    state = _cli_state()
    if "RUNNING" not in state:
        return (f"state={state}. Not ready. Use avatar_endpoint_start "
                f"(cold start ~15-30 min), then poll this tool.")
    code, health = _http("/healthz", timeout=30)
    ready = health.get("ready") if isinstance(health, dict) else None
    return (f"state=RUNNING, healthz http={code}, ready={ready}. "
            + ("Ready to generate." if ready else
               "Still loading the model - poll again in a few minutes."))


@mcp.tool()
def avatar_endpoint_start() -> str:
    """Start the stopped avatar endpoint. Billing note: it occupies a
    dedicated GPU until stopped. The start command itself takes a few
    minutes; full cold start to ready is ~15-30 minutes (model download +
    load). Poll avatar_endpoint_status until ready=true."""
    if not ENDPOINT_ID:
        return "ENDPOINT_ID is not set; cannot manage the endpoint."
    state = _cli_state()
    if state == "RUNNING":
        return "Already RUNNING."
    out = subprocess.run(_nebius_cmd() + ["start", ENDPOINT_ID],
                         capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        return f"start failed: {out.stderr.strip()[:400]}"
    return ("Start issued. Expect ~15-30 min until ready=true (poll "
            "avatar_endpoint_status). Remember avatar_endpoint_stop when "
            "done to stop GPU billing.")


@mcp.tool()
def avatar_endpoint_stop() -> str:
    """Stop the avatar endpoint to stop GPU billing. It keeps its identity
    and adapter and can be restarted later. Call when the user is done."""
    if not ENDPOINT_ID:
        return "ENDPOINT_ID is not set; cannot manage the endpoint."
    out = subprocess.run(_nebius_cmd() + ["stop", ENDPOINT_ID],
                         capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        return f"stop failed: {out.stderr.strip()[:400]}"
    return ("Stop issued. Note: the endpoint's HTTPS hostname will be "
            "DIFFERENT after the next start; this server re-resolves it "
            "automatically.")


@mcp.tool()
def generate_avatar_image(
    scene: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 28,
    guidance_scale: float = 4.0,
    seed: Optional[int] = None,
) -> list:
    """Generate a photorealistic image of the trained subject.

    Describe only the scene/style/clothing/lighting in `scene` (e.g. "seated
    at a cafe, natural candid photo"); the subject's identity is injected via
    the trained trigger token - do NOT describe their face. Photorealistic,
    single-person compositions are most reliable. Takes ~15-45 s when the
    endpoint is warm; fails fast when it is stopped (use
    avatar_endpoint_start first). Sizes must be multiples of 64 (256-1536).
    Same seed + prompt = same image. Returns the image plus the saved path.
    """
    state = _cli_state()
    if ENDPOINT_ID and "RUNNING" not in state:
        return [f"Endpoint is {state}, not RUNNING. Call "
                f"avatar_endpoint_start (~15-30 min), poll "
                f"avatar_endpoint_status, then retry."]
    if TRIGGER_WORD.lower() in scene.lower():
        prompt = scene
    else:
        prompt = f"{TRIGGER_WORD} {TRIGGER_CLASS}, {scene}"
    if seed is None:
        seed = int.from_bytes(os.urandom(4), "big") % 2**31
    body = {"prompt": prompt, "width": width, "height": height,
            "steps": steps, "guidance_scale": guidance_scale, "seed": seed,
            "response_format": "base64"}
    started = time.time()
    code, resp = _http("/generate", body)
    elapsed = time.time() - started
    if code != 200 or not resp.get("image_base64"):
        err = {k: v for k, v in resp.items() if k != "image_base64"}
        return [f"generation failed: http={code} after {elapsed:.0f}s: "
                f"{json.dumps(err)[:400]}"]
    png = base64.b64decode(resp["image_base64"])
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fname = f"avatar_{time.strftime('%Y%m%d-%H%M%S')}_seed{seed}.png"
    fpath = os.path.join(OUTPUT_DIR, fname)
    with open(fpath, "wb") as fh:
        fh.write(png)
    return [
        Image(data=png, format="png"),
        f"Saved to {fpath} (seed={seed}, {elapsed:.0f}s, prompt: {prompt!r})",
    ]


if __name__ == "__main__":
    mcp.run()
