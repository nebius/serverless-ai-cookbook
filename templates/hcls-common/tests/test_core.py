from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hcls_api import core as core_module
from hcls_api.core import create_app


TEST_PROTOCOL_VERSION = "2025-11-25"


class FakeAdapter:
    service_id = "fake-engine"

    def load(self) -> None:
        return None

    def health(self) -> dict:
        return {"ready": True, "engine": "fake"}

    def capabilities(self) -> dict:
        return {"engine": {"name": "fake", "version": "1"}}

    def run(self, payload: dict, work_dir: Path) -> dict:
        (work_dir / "answer.txt").write_text(str(payload.get("value", "ok")))
        return {"answer": payload.get("value", "ok")}


def wait_for_terminal(client: TestClient, run_id: str) -> dict:
    for _ in range(100):
        response = client.get(f"/v1/runs/{run_id}")
        response.raise_for_status()
        body = response.json()
        if body["status"] in {"succeeded", "failed", "cancelled"}:
            return body
        time.sleep(0.01)
    raise AssertionError("run did not finish")


def test_run_lifecycle_artifact_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setenv("HCLS_RUN_ROOT", str(tmp_path))
    with TestClient(create_app(FakeAdapter())) as client:
        payload = {
            "input": {"value": "hello"},
            "client_request_id": "same-request",
            "research_use_acknowledgement": True,
        }
        first = client.post("/v1/runs", json=payload)
        assert first.status_code == 202
        run = wait_for_terminal(client, first.json()["run_id"])
        assert run["status"] == "succeeded"
        assert run["result"]["answer"] == "hello"
        assert run["artifacts"][0]["sha256"]

        artifact = client.get(run["artifacts"][0]["download_path"])
        assert artifact.status_code == 200
        assert artifact.text == "hello"

        second = client.post("/v1/runs", json=payload)
        assert second.json()["run_id"] == run["run_id"]


def test_research_acknowledgement_and_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("HCLS_RUN_ROOT", str(tmp_path))
    with TestClient(create_app(FakeAdapter())) as client:
        assert client.post("/v1/runs", json={"input": {}}).status_code == 422
        run_id = client.post(
            "/v1/runs",
            json={"input": {}, "research_use_acknowledgement": True},
        ).json()["run_id"]
        wait_for_terminal(client, run_id)
        assert client.get(f"/v1/runs/{run_id}/artifacts/../status.json").status_code in {400, 404}


def test_terminal_run_is_restored_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("HCLS_RUN_ROOT", str(tmp_path))
    payload = {
        "input": {"value": "persisted"},
        "client_request_id": "restart-idempotency",
        "research_use_acknowledgement": True,
    }
    with TestClient(create_app(FakeAdapter())) as first_client:
        run_id = first_client.post("/v1/runs", json=payload).json()["run_id"]
        assert wait_for_terminal(first_client, run_id)["status"] == "succeeded"

    with TestClient(create_app(FakeAdapter())) as second_client:
        restored = second_client.get(f"/v1/runs/{run_id}")
        assert restored.status_code == 200
        assert restored.json()["result"]["answer"] == "persisted"
        duplicate = second_client.post("/v1/runs", json=payload)
        assert duplicate.status_code == 202
        assert duplicate.json()["run_id"] == run_id


def test_storage_root_stages_locally_and_restores(tmp_path, monkeypatch):
    storage_root = tmp_path / "persistent"
    scratch_root = tmp_path / "scratch"
    monkeypatch.setenv("HCLS_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("HCLS_SCRATCH_ROOT", str(scratch_root))
    monkeypatch.delenv("HCLS_RUN_ROOT", raising=False)

    payload = {
        "input": {"value": "durable"},
        "client_request_id": "storage-neutral-run",
        "research_use_acknowledgement": True,
    }
    with TestClient(create_app(FakeAdapter())) as first_client:
        run_id = first_client.post("/v1/runs", json=payload).json()["run_id"]
        run = wait_for_terminal(first_client, run_id)
        assert run["status"] == "succeeded"
        assert (storage_root / "fake-engine" / "runs" / run_id / "answer.txt").read_text() == "durable"
        assert run_id in (storage_root / "fake-engine" / "runs-index.json").read_text()
        assert not (scratch_root / "fake-engine" / run_id).exists()

    runs_root = (storage_root / "fake-engine" / "runs").resolve()
    real_glob = Path.glob

    def s3_like_glob(path: Path, pattern: str):
        # Some object-backed mounts can resolve exact keys but do not expose
        # implicit S3 prefix directories through filesystem globbing.
        if path.resolve() == runs_root and pattern == "*/status.json":
            return iter(())
        return real_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", s3_like_glob)
    with TestClient(create_app(FakeAdapter())) as second_client:
        restored = second_client.get(f"/v1/runs/{run_id}")
        assert restored.status_code == 200
        assert restored.json()["result"]["answer"] == "durable"


def mcp_call(client: TestClient, method: str, params: dict, request_id: int) -> dict:
    response = client.post(
        "/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": TEST_PROTOCOL_VERSION,
        },
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_mcp_and_rest_share_runs_and_artifacts(tmp_path, monkeypatch):
    if core_module.MCPServer is None:
        pytest.skip("MCP SDK is not installed in this REST-only test environment")
    monkeypatch.setenv("HCLS_RUN_ROOT", str(tmp_path))
    monkeypatch.setenv("HCLS_ENABLE_MCP", "1")
    monkeypatch.delenv("HCLS_STORAGE_ROOT", raising=False)
    with TestClient(create_app(FakeAdapter())) as client:
        initialized = mcp_call(
            client,
            "initialize",
            {
                "protocolVersion": TEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "hcls-test", "version": "1.0"},
            },
            1,
        )
        assert initialized["result"]["serverInfo"]["name"] == "Nebius HCLS fake-engine"

        tools = mcp_call(client, "tools/list", {}, 2)
        tool_names = {tool["name"] for tool in tools["result"]["tools"]}
        assert {"get_capabilities", "submit_run", "get_run", "list_run_artifacts"} <= tool_names

        submitted = mcp_call(
            client,
            "tools/call",
            {
                "name": "submit_run",
                "arguments": {
                    "input": {"value": "from-agent"},
                    "client_request_id": "mcp-rest-shared",
                    "research_use_acknowledgement": True,
                },
            },
            3,
        )
        run_id = submitted["result"]["structuredContent"]["run_id"]
        run = wait_for_terminal(client, run_id)
        assert run["result"]["answer"] == "from-agent"

        artifacts = mcp_call(
            client,
            "tools/call",
            {"name": "list_run_artifacts", "arguments": {"run_id": run_id}},
            4,
        )
        names = {item["name"] for item in artifacts["result"]["structuredContent"]["artifacts"]}
        assert "answer.txt" in names
