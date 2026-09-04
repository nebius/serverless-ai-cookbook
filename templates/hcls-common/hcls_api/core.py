from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
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
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


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
    def __init__(self, adapter: EngineAdapter, root: Path, queue_limit: int) -> None:
        self.adapter = adapter
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.queue_limit = queue_limit
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=adapter.service_id)
        self.lock = threading.RLock()
        self.records: dict[str, dict[str, Any]] = {}
        self.futures: dict[str, Future[None]] = {}
        self.idempotency: dict[str, str] = {}
        self._restore()

    def _restore(self) -> None:
        for status_path in sorted(self.root.glob("*/status.json")):
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
        work_dir = self.root / run_id
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
            artifacts = self._artifacts(work_dir)
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
            with self.lock:
                self.records[run_id].update(
                    status="failed",
                    finished_at=utc_now(),
                    error={
                        "type": type(exc).__name__,
                        "message": str(exc)[:1000],
                    },
                    artifacts=self._artifacts(work_dir),
                )
                self._persist(run_id)

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
    root = Path(os.environ.get("HCLS_RUN_ROOT", "/data/runs"))
    queue_limit = max(0, min(int(os.environ.get("HCLS_QUEUE_LIMIT", "8")), 100))
    manager = RunManager(adapter, root, queue_limit)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        adapter.load()
        yield
        manager.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(
        title=f"Nebius HCLS — {adapter.service_id}",
        version=API_VERSION,
        lifespan=lifespan,
    )

    @app.get("/")
    def root_route() -> dict[str, Any]:
        return {
            "service": adapter.service_id,
            "api_version": API_VERSION,
            "capabilities_path": "/v1/capabilities",
            "submit_path": "/v1/runs",
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

    return app
