from __future__ import annotations

import hmac
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field


SESSION_COOKIE = "hcls_workbench_session"
SESSION_TTL_SECONDS = max(300, min(int(os.environ.get("HCLS_SESSION_TTL_SECONDS", "14400")), 86400))
MAX_RESPONSE_BYTES = 50 * 1024 * 1024
STATIC_ROOT = Path(__file__).parent / "static"
ALLOWED_HOST_SUFFIXES = tuple(
    suffix.strip().lower()
    for suffix in os.environ.get(
        "HCLS_ALLOWED_ENDPOINT_SUFFIXES",
        ".tunnel.applications.eu-north1.nebius.cloud",
    ).split(",")
    if suffix.strip()
)
ALLOW_LOCAL = os.environ.get("HCLS_ALLOW_LOCAL_ENDPOINTS", "0") == "1"
COOKIE_SECURE = os.environ.get("HCLS_COOKIE_SECURE", "1") != "0"
UI_ACCESS_KEY = os.environ.get("HCLS_UI_ACCESS_KEY", "")


@dataclass
class Session:
    csrf_token: str
    expires_at: float
    endpoint_url: str | None = None
    endpoint_token: str | None = None
    capabilities: dict[str, Any] | None = None


class SessionStore:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.sessions: dict[str, Session] = {}

    def create(self) -> tuple[str, Session]:
        with self.lock:
            self.purge()
            session_id = secrets.token_urlsafe(32)
            session = Session(
                csrf_token=secrets.token_urlsafe(24),
                expires_at=time.time() + SESSION_TTL_SECONDS,
            )
            self.sessions[session_id] = session
            return session_id, session

    def get(self, session_id: str | None) -> Session:
        if not session_id:
            raise HTTPException(status_code=401, detail="workbench login required")
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None or session.expires_at <= time.time():
                self.sessions.pop(session_id, None)
                raise HTTPException(status_code=401, detail="workbench session expired")
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            return session

    def remove(self, session_id: str | None) -> None:
        if session_id:
            with self.lock:
                self.sessions.pop(session_id, None)

    def purge(self) -> None:
        now = time.time()
        for session_id in [key for key, value in self.sessions.items() if value.expires_at <= now]:
            self.sessions.pop(session_id, None)


class LoginRequest(BaseModel):
    access_key: str = Field(min_length=1, max_length=512)


class ConnectRequest(BaseModel):
    endpoint_url: str = Field(min_length=8, max_length=2048)
    token: str = Field(min_length=1, max_length=8192)


class SubmitRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    client_request_id: str | None = Field(default=None, max_length=128)


sessions = SessionStore()
app = FastAPI(title="Nebius HCLS Workbench", version="1.0")


@app.on_event("startup")
def startup() -> None:
    if len(UI_ACCESS_KEY) < 16:
        raise RuntimeError("HCLS_UI_ACCESS_KEY must contain at least 16 characters")


def validate_endpoint_url(raw: str) -> str:
    parsed = urlsplit(raw.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=400, detail="endpoint URL cannot contain credentials, query, or fragment")
    hostname = (parsed.hostname or "").rstrip(".").lower()
    is_local = hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (ALLOW_LOCAL and is_local and parsed.scheme == "http"):
        raise HTTPException(status_code=400, detail="endpoint URL must use HTTPS")
    if not is_local and not any(hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        raise HTTPException(status_code=400, detail="endpoint hostname is outside the configured allowlist")
    if parsed.port not in {None, 443} and not (ALLOW_LOCAL and is_local):
        raise HTTPException(status_code=400, detail="endpoint URL must use the default HTTPS port")
    if parsed.path not in {"", "/"}:
        raise HTTPException(status_code=400, detail="enter the endpoint root URL without an API path")
    if not is_local:
        try:
            for result in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM):
                address = ipaddress.ip_address(result[4][0])
                if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
                    raise HTTPException(status_code=400, detail="endpoint hostname resolved to a non-public address")
        except socket.gaierror as exc:
            raise HTTPException(status_code=400, detail="endpoint hostname could not be resolved") from exc
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def require_session(session_id: str | None) -> Session:
    return sessions.get(session_id)


def require_csrf(session: Session, csrf_token: str | None) -> None:
    if not csrf_token or not hmac.compare_digest(csrf_token, session.csrf_token):
        raise HTTPException(status_code=403, detail="invalid CSRF token")


def connected(session: Session) -> tuple[str, dict[str, str]]:
    if not session.endpoint_url or not session.endpoint_token:
        raise HTTPException(status_code=409, detail="connect a compute endpoint first")
    return session.endpoint_url, {"Authorization": f"Bearer {session.endpoint_token}"}


def endpoint_json(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = httpx.request(method, url, headers=headers, json=body, timeout=httpx.Timeout(120.0, connect=20.0))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"compute endpoint request failed: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        try:
            endpoint_detail = response.json().get("detail", response.text[:400])
        except (ValueError, AttributeError):
            endpoint_detail = response.text[:400]
        raise HTTPException(status_code=502, detail=f"compute endpoint returned {response.status_code}: {endpoint_detail}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="compute endpoint returned non-JSON data") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="compute endpoint returned an unexpected JSON shape")
    return payload


def default_endpoints() -> list[dict[str, str]]:
    raw = os.environ.get("HCLS_DEFAULT_ENDPOINTS_JSON", "[]")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [
        {"name": str(item.get("name", "Endpoint"))[:80], "url": str(item.get("url", ""))[:2048]}
        for item in value
        if isinstance(item, dict) and item.get("url")
    ]


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
def health() -> dict[str, Any]:
    return {"ready": True, "service": "hcls-workbench", "active_sessions": len(sessions.sessions)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/static/{name}")
def static(name: str) -> FileResponse:
    if name not in {"app.js", "styles.css", "favicon.svg"}:
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(STATIC_ROOT / name)


@app.post("/api/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not hmac.compare_digest(payload.access_key, UI_ACCESS_KEY):
        raise HTTPException(status_code=401, detail="invalid workbench access key")
    session_id, session = sessions.create()
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL_SECONDS,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "csrf_token": session.csrf_token, "expires_in_seconds": SESSION_TTL_SECONDS}


@app.post("/api/logout")
def logout(response: Response, session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, bool]:
    sessions.remove(session_id)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="strict")
    return {"authenticated": False}


@app.get("/api/session")
def session_state(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    try:
        session = require_session(session_id)
    except HTTPException:
        return {"authenticated": False, "default_endpoints": default_endpoints()}
    return {
        "authenticated": True,
        "csrf_token": session.csrf_token,
        "connected": bool(session.endpoint_url),
        "endpoint_url": session.endpoint_url,
        "capabilities": session.capabilities,
        "default_endpoints": default_endpoints(),
    }


@app.post("/api/connect")
def connect(
    payload: ConnectRequest,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, Any]:
    session = require_session(session_id)
    require_csrf(session, csrf_token)
    endpoint_url = validate_endpoint_url(payload.endpoint_url)
    headers = {"Authorization": f"Bearer {payload.token}"}
    capabilities = endpoint_json("GET", f"{endpoint_url}/v1/capabilities", headers)
    if capabilities.get("api_version") != "1.0" or not capabilities.get("service"):
        raise HTTPException(status_code=502, detail="endpoint does not implement the HCLS API v1 contract")
    session.endpoint_url = endpoint_url
    session.endpoint_token = payload.token
    session.capabilities = capabilities
    return {"connected": True, "endpoint_url": endpoint_url, "capabilities": capabilities}


@app.post("/api/runs", status_code=202)
def submit_run(
    payload: SubmitRequest,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, Any]:
    session = require_session(session_id)
    require_csrf(session, csrf_token)
    endpoint_url, headers = connected(session)
    return endpoint_json(
        "POST",
        f"{endpoint_url}/v1/runs",
        headers,
        {
            "input": payload.input,
            "client_request_id": payload.client_request_id or f"workbench-{secrets.token_hex(8)}",
            "research_use_acknowledgement": True,
        },
    )


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    if not re_fullmatch_identifier(run_id):
        raise HTTPException(status_code=400, detail="invalid run id")
    session = require_session(session_id)
    endpoint_url, headers = connected(session)
    return endpoint_json("GET", f"{endpoint_url}/v1/runs/{quote(run_id, safe='')}", headers)


def re_fullmatch_identifier(value: str) -> bool:
    return bool(value) and len(value) <= 128 and all(character.isalnum() or character in "._:-" for character in value)


@app.get("/api/runs/{run_id}/artifacts/{artifact_name:path}")
def get_artifact(
    run_id: str,
    artifact_name: str,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    if not re_fullmatch_identifier(run_id) or not artifact_name or artifact_name.startswith("/") or ".." in Path(artifact_name).parts:
        raise HTTPException(status_code=400, detail="invalid artifact path")
    session = require_session(session_id)
    endpoint_url, headers = connected(session)
    url = f"{endpoint_url}/v1/runs/{quote(run_id, safe='')}/artifacts/{quote(artifact_name, safe='/')}"
    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
            with client.stream("GET", url, headers=headers) as upstream:
                if upstream.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"compute endpoint returned {upstream.status_code}")
                content = bytearray()
                for chunk in upstream.iter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise HTTPException(status_code=413, detail="artifact exceeds the workbench download limit")
                media_type = upstream.headers.get("content-type", "application/octet-stream").split(";")[0]
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"artifact download failed: {type(exc).__name__}") from exc
    return Response(
        content=bytes(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={json.dumps(Path(artifact_name).name)}"},
    )
