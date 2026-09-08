from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:  # REST-only images can adopt MCP one service at a time.
    MCPServer = None  # type: ignore[assignment,misc]
    TransportSecuritySettings = None  # type: ignore[assignment,misc]


API_VERSION = "1.0"
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
SAFE_CLIENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    try:
        temporary.replace(path)
    except OSError:
        # S3-backed mounts do not necessarily implement POSIX rename. Fall back
        # to a sequential overwrite; terminal artifacts remain immutable and
        # status.json is the only mutable object in each run directory.
        path.write_text(encoded, encoding="utf-8")
        try:
            temporary.unlink()
        except OSError:
            pass


class EngineAdapter(Protocol):
    service_id: str

    def load(self) -> None: ...

    def health(self) -> dict[str, Any]: ...

    def capabilities(self) -> dict[str, Any]: ...

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]: ...


class RunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    client_request_id: str | None = Field(default=None, max_length=128)
    research_use_acknowledgement: Literal[True]

    @field_validator("client_request_id")
    @classmethod
    def validate_client_request_id(cls, value: str | None) -> str | None:
        if value is not None and not SAFE_CLIENT_ID.fullmatch(value):
            raise ValueError("client_request_id contains unsupported characters")
        return value


class RunManager:
    def __init__(self, adapter: EngineAdapter, root: Path, scratch_root: Path, queue_limit: int) -> None:
        self.adapter = adapter
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.scratch_root = scratch_root.resolve()
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self.queue_limit = queue_limit
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=adapter.service_id)
        self.lock = threading.RLock()
        self.records: dict[str, dict[str, Any]] = {}
        self.futures: dict[str, Future[None]] = {}
        self.idempotency: dict[str, str] = {}
        self._restore()

    def _restore(self) -> None:
        status_paths: list[Path] = []
        seen: set[Path] = set()
        index_path = self.root.parent / "runs-index.json"
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            indexed_run_ids = index.get("run_ids", []) if isinstance(index, dict) else []
        except (OSError, json.JSONDecodeError):
            indexed_run_ids = []
        for run_id in indexed_run_ids:
            if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
                continue
            status_path = self.root / run_id / "status.json"
            status_paths.append(status_path)
            seen.add(status_path)
        # POSIX filesystems can be discovered by directory traversal. The fixed
        # index above is primary because some S3-backed mounts can open an object
        # by key while omitting implicit directories from glob results.
        for status_path in sorted(self.root.glob("*/status.json")):
            if status_path not in seen:
                status_paths.append(status_path)
        for status_path in status_paths:
            run_id = status_path.parent.name
            if not re.fullmatch(r"[0-9a-f]{32}", run_id):
                continue
            try:
                record = json.loads(status_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                not isinstance(record, dict)
                or record.get("run_id") != run_id
                or record.get("service") != self.adapter.service_id
            ):
                continue
            if record.get("status") not in TERMINAL_STATES:
                record.update(
                    status="failed",
                    finished_at=utc_now(),
                    error={
                        "type": "InterruptedRun",
                        "message": "worker restarted before the run reached a terminal state",
                    },
                    artifacts=self._artifacts(status_path.parent),
                )
                write_json(status_path, record)
            self.records[run_id] = record
            client_request_id = record.get("client_request_id")
            if isinstance(client_request_id, str) and SAFE_CLIENT_ID.fullmatch(client_request_id):
                self.idempotency[client_request_id] = run_id
        if self.records:
            self._persist_index()

    def submit(self, request: RunRequest) -> dict[str, Any]:
        with self.lock:
            if request.client_request_id and request.client_request_id in self.idempotency:
                return self.snapshot(self.idempotency[request.client_request_id])
            active = sum(1 for record in self.records.values() if record["status"] not in TERMINAL_STATES)
            if active >= self.queue_limit + 1:
                raise HTTPException(status_code=429, detail="run queue is full")
            run_id = uuid.uuid4().hex
            now = utc_now()
            record = {
                "api_version": API_VERSION,
                "run_id": run_id,
                "service": self.adapter.service_id,
                "status": "queued",
                "created_at": now,
                "started_at": None,
                "finished_at": None,
                "client_request_id": request.client_request_id,
                "result": None,
                "error": None,
                "artifacts": [],
            }
            self.records[run_id] = record
            if request.client_request_id:
                self.idempotency[request.client_request_id] = run_id
            self._persist(run_id)
            self.futures[run_id] = self.executor.submit(self._execute, run_id, request.input)
            return dict(record)

    def _execute(self, run_id: str, payload: dict[str, Any]) -> None:
        work_dir = self.scratch_root / run_id
        work_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            if self.records[run_id]["status"] == "cancelled":
                return
            self.records[run_id]["status"] = "running"
            self.records[run_id]["started_at"] = utc_now()
            self._persist(run_id)
        started = time.perf_counter()
        try:
            result = self.adapter.run(payload, work_dir)
            result = {
                **result,
                "wall_clock_seconds": round(time.perf_counter() - started, 6),
                "image_revision": os.environ.get("HCLS_IMAGE_REVISION", "unknown"),
            }
            write_json(work_dir / "result.json", result)
            persistent_dir = self._publish(work_dir, run_id)
            artifacts = self._artifacts(persistent_dir)
            with self.lock:
                self.records[run_id].update(
                    status="succeeded",
                    finished_at=utc_now(),
                    result=result,
                    artifacts=artifacts,
                )
                self._persist(run_id)
        except Exception as exc:  # noqa: BLE001 - engine failures become run state
            (work_dir / ".internal-error.log").write_text(
                traceback.format_exc(limit=30)[-16000:], encoding="utf-8"
            )
            publish_error: Exception | None = None
            try:
                persistent_dir = self._publish(work_dir, run_id)
                artifacts = self._artifacts(persistent_dir)
            except Exception as storage_exc:  # noqa: BLE001 - captured in run state
                publish_error = storage_exc
                artifacts = []
            message = str(exc)[:1000]
            if publish_error is not None:
                message = f"{message}; artifact persistence failed: {publish_error}"[:1000]
            with self.lock:
                self.records[run_id].update(
                    status="failed",
                    finished_at=utc_now(),
                    error={
                        "type": type(exc).__name__,
                        "message": message,
                    },
                    artifacts=artifacts,
                )
                self._persist(run_id)
        finally:
            if work_dir != self.root / run_id:
                shutil.rmtree(work_dir, ignore_errors=True)

    def _publish(self, work_dir: Path, run_id: str) -> Path:
        persistent_dir = self.root / run_id
        if work_dir == persistent_dir:
            return persistent_dir
        persistent_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(work_dir.rglob("*")):
            if not source.is_file() or source.name in {"status.json", ".internal-error.log"}:
                continue
            target = persistent_dir / source.relative_to(work_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as input_handle, target.open("wb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
        return persistent_dir

    def _artifacts(self, work_dir: Path) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for path in sorted(work_dir.rglob("*")):
            if not path.is_file() or path.name in {"status.json", ".internal-error.log"}:
                continue
            relative = path.relative_to(work_dir).as_posix()
            artifacts.append(
                {
                    "name": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "download_path": f"/v1/runs/{work_dir.name}/artifacts/{relative}",
                }
            )
        return artifacts

    def _persist(self, run_id: str) -> None:
        write_json(self.root / run_id / "status.json", self.records[run_id])
        self._persist_index()

    def _persist_index(self) -> None:
        write_json(
            self.root.parent / "runs-index.json",
            {
                "api_version": API_VERSION,
                "service": self.adapter.service_id,
                "updated_at": utc_now(),
                "run_ids": sorted(self.records),
            },
        )

    def snapshot(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            record = self.records.get(run_id)
            if record is None:
                raise HTTPException(status_code=404, detail="run not found")
            return json.loads(json.dumps(record))

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            ordered = sorted(self.records.values(), key=lambda item: item["created_at"], reverse=True)
            return [json.loads(json.dumps(record)) for record in ordered[:50]]

    def cancel(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            record = self.records.get(run_id)
            if record is None:
                raise HTTPException(status_code=404, detail="run not found")
            if record["status"] in TERMINAL_STATES:
                return self.snapshot(run_id)
            future = self.futures.get(run_id)
            if record["status"] != "queued" or future is None or not future.cancel():
                raise HTTPException(status_code=409, detail="running engine process cannot be cancelled safely")
            record.update(status="cancelled", finished_at=utc_now())
            self._persist(run_id)
            return self.snapshot(run_id)

    def artifact(self, run_id: str, name: str) -> Path:
        self.snapshot(run_id)
        run_root = (self.root / run_id).resolve()
        candidate = (run_root / name).resolve()
        if candidate == run_root or run_root not in candidate.parents:
            raise HTTPException(status_code=400, detail="invalid artifact path")
        if not candidate.is_file() or candidate.name in {"status.json", ".internal-error.log"}:
            raise HTTPException(status_code=404, detail="artifact not found")
        return candidate


def create_app(adapter: EngineAdapter) -> FastAPI:
    storage_root = os.environ.get("HCLS_STORAGE_ROOT")
    if storage_root:
        root = Path(storage_root) / adapter.service_id / "runs"
        scratch_root = Path(os.environ.get("HCLS_SCRATCH_ROOT", "/tmp/hcls-scratch")) / adapter.service_id
    else:
        # HCLS_RUN_ROOT preserves the v1 layout for existing images and tests.
        root = Path(os.environ.get("HCLS_RUN_ROOT", "/data/runs"))
        scratch_root = Path(os.environ.get("HCLS_SCRATCH_ROOT", str(root)))
    queue_limit = max(0, min(int(os.environ.get("HCLS_QUEUE_LIMIT", "8")), 100))
    manager = RunManager(adapter, root, scratch_root, queue_limit)
    mcp_enabled = os.environ.get("HCLS_ENABLE_MCP", "0").strip().lower() in {"1", "true", "yes"}
    mcp = None
    mcp_app = None
    if mcp_enabled:
        if MCPServer is None or TransportSecuritySettings is None:
            raise RuntimeError("HCLS_ENABLE_MCP is set but the MCP SDK is not installed")
        mcp = MCPServer(
            name=f"Nebius HCLS {adapter.service_id}",
            version=API_VERSION,
            instructions=(
                "Submit and inspect bounded research-only scientific runs. "
                "REST and MCP share the same queue, run IDs, state, and artifacts."
            ),
        )

        @mcp.tool(description="Return engine, input, accelerator, and limit metadata.")
        def get_capabilities() -> dict[str, Any]:
            return {
                "api_version": API_VERSION,
                "service": adapter.service_id,
                "queue_limit": queue_limit,
                "max_concurrent_runs": 1,
                "research_only": True,
                **adapter.capabilities(),
            }

        @mcp.tool(description="Submit a bounded research-only run to the shared execution queue.")
        def submit_run(
            input: dict[str, Any],
            research_use_acknowledgement: bool,
            client_request_id: str | None = None,
        ) -> dict[str, Any]:
            if research_use_acknowledgement is not True:
                raise ValueError("research_use_acknowledgement must be true")
            request = RunRequest(
                input=input,
                client_request_id=client_request_id,
                research_use_acknowledgement=True,
            )
            return manager.submit(request)

        @mcp.tool(description="Get the current state and result metadata for one run ID.")
        def get_run(run_id: str) -> dict[str, Any]:
            return manager.snapshot(run_id)

        @mcp.tool(description="List the newest runs visible to this endpoint instance.")
        def list_runs() -> dict[str, Any]:
            return {"runs": manager.list()}

        @mcp.tool(description="Cancel a queued run. An active engine process cannot be interrupted safely.")
        def cancel_run(run_id: str) -> dict[str, Any]:
            return manager.cancel(run_id)

        @mcp.tool(description="List artifact metadata and authenticated REST download paths for a run.")
        def list_run_artifacts(run_id: str) -> dict[str, Any]:
            record = manager.snapshot(run_id)
            return {"run_id": run_id, "status": record["status"], "artifacts": record["artifacts"]}

        # Nebius terminates managed HTTPS and enforces the bearer token before
        # this process. TrustedHostMiddleware below provides suffix-aware Host
        # validation; the SDK validator only supports exact hosts, which are
        # unknown until an endpoint is created.
        mcp_app = mcp.streamable_http_app(
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
            max_request_body_size=4 * 1024 * 1024,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
            host="0.0.0.0",
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        adapter.load()
        if mcp is None:
            yield
        else:
            async with mcp.session_manager.run():
                yield
        manager.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(
        title=f"Nebius HCLS — {adapter.service_id}",
        version=API_VERSION,
        lifespan=lifespan,
    )
    allowed_hosts = [
        item.strip()
        for item in os.environ.get(
            "HCLS_ALLOWED_HOSTS",
            "*.nebius.cloud,localhost,127.0.0.1,testserver",
        ).split(",")
        if item.strip()
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.get("/")
    def root_route() -> dict[str, Any]:
        return {
            "service": adapter.service_id,
            "api_version": API_VERSION,
            "capabilities_path": "/v1/capabilities",
            "submit_path": "/v1/runs",
            "mcp_path": "/mcp" if mcp_enabled else None,
            "storage_root": str(root),
            "research_only": True,
        }

    @app.get("/healthz")
    @app.get("/v1/health/ready")
    def health() -> dict[str, Any]:
        payload = adapter.health()
        if not payload.get("ready"):
            raise HTTPException(status_code=503, detail=payload)
        return payload

    @app.get("/v1/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "api_version": API_VERSION,
            "service": adapter.service_id,
            "queue_limit": queue_limit,
            "max_concurrent_runs": 1,
            "research_only": True,
            **adapter.capabilities(),
        }

    @app.post("/v1/runs", status_code=202)
    def submit(request: RunRequest) -> dict[str, Any]:
        return manager.submit(request)

    @app.get("/v1/runs")
    def list_runs() -> dict[str, Any]:
        return {"runs": manager.list()}

    @app.get("/v1/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        return manager.snapshot(run_id)

    @app.post("/v1/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, Any]:
        return manager.cancel(run_id)

    @app.get("/v1/runs/{run_id}/artifacts/{name:path}")
    def get_artifact(run_id: str, name: str) -> FileResponse:
        path = manager.artifact(run_id, name)
        return FileResponse(path, filename=path.name)

    if mcp_app is not None:
        app.mount("/", mcp_app)
    return app
