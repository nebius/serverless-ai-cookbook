import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_audio_server import app

from fs2_speech.capacity_observation import (
    BoundedHardwareSampler,
    WorkerObservation,
    hardware_snapshot,
    unknown_hardware,
)


def test_sampler_timeout_has_one_outstanding_query_and_no_exception_payload():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def query():
        calls.append(1)
        entered.set()
        release.wait(2)
        raise ValueError("private device details")

    async def run():
        sampler = BoundedHardwareSampler(query, timeout_seconds=0.01)
        for _ in range(3):
            assert (await sampler.sample())["reason"] == "hardware_query_deadline"
        assert entered.is_set() and calls == [1]
        release.set()
        await asyncio.sleep(0.02)
        result = await sampler.sample()
        assert result["reason"] == "hardware_query_failed"
        assert "private" not in json.dumps(result)
        sampler.close()
        assert (await sampler.sample())["reason"] == "sampler_closed"

    asyncio.run(run())


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, "1"])
def test_processed_counter_rejects_invalid_values(value):
    observer = WorkerObservation(identity=lambda: {}, profile=lambda: {}, state=lambda: {"ready": False})
    with pytest.raises(ValueError):
        observer.processed(value)


def test_not_ready_does_not_query_hardware_and_counters_are_not_capacity():
    observer = WorkerObservation(
        identity=lambda: {"checkpoint_sha256": None},
        profile=lambda: {},
        state=lambda: {"ready": False, "active_sessions": 2, "pending_sessions": 0},
        hardware=BoundedHardwareSampler(lambda: pytest.fail("not ready")),
    )
    observer.processed(0.1)
    result = asyncio.run(observer.sample())
    assert result["hardware"]["reason"] == "worker_not_ready"
    assert result["processed_audio_seconds_total"] == 0.1
    assert result["measured_capacity"] is None and result["cloud_identity"] is None
    assert result["gateway_pending_sessions"] is None and result["pending_sessions"] == 0
    assert "including_cancelled_work" in result["processed_audio_semantics"]


def test_hardware_uuid_mapping_no_synchronization_and_missing_utilization(monkeypatch):
    import sys

    cuda = SimpleNamespace(
        is_available=lambda: True,
        device_count=lambda: 1,
        get_device_properties=lambda _: SimpleNamespace(name="unit GPU", uuid=None),
        mem_get_info=lambda _: (10, 20),
        memory_allocated=lambda _: 2,
        memory_reserved=lambda _: 3,
        synchronize=lambda: pytest.fail("telemetry must not synchronize"),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda, version=SimpleNamespace(cuda="unit")))
    monkeypatch.setitem(sys.modules, "pynvml", None)
    result = hardware_snapshot()
    assert result["devices"][0]["utilization_percent"] is None
    assert result["devices"][0]["process_reserved_bytes"] == 3
    assert result["driver_version"] is None and result["llm_kv_cache"] == "not_applicable"


def test_detailed_observation_and_metrics_auth_no_scheduling_identifiers(tmp_path, monkeypatch):
    token = tmp_path / "token"
    token.write_text("x" * 32)
    monkeypatch.setenv("FS2_STT_GATEWAY_TOKEN_FILE", str(token))
    application = app()
    application.state.capacity_observation.hardware = BoundedHardwareSampler(lambda: unknown_hardware("unit"))
    headers = {"authorization": "Bearer " + "x" * 32, "x-fs2-scheduling-group": "b" * 64}
    with TestClient(application) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/metrics").status_code == 401
        assert client.get("/capacity-observation").status_code == 401
        result = client.get("/capacity-observation", headers=headers)
        assert result.status_code == 200
        assert "b" * 64 not in result.text and "x" * 32 not in result.text
        assert result.json()["active_sessions"] == 0
        assert result.json()["queued_chunk_actions"] == 0
        assert result.json()["measured_capacity"] is None
        assert client.get("/metrics", headers=headers).status_code == 200


def test_detailed_observation_is_unavailable_without_auth(monkeypatch):
    monkeypatch.delenv("FS2_STT_GATEWAY_TOKEN_FILE", raising=False)
    with TestClient(app()) as client:
        assert client.get("/capacity-observation").status_code == 503
