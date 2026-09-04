from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from hcls_api.core import create_app


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
