import io
import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from clinical_asr import server
from test_contracts import wav_bytes


def test_authenticated_http_ws_mcp_contract(monkeypatch, tmp_path):
    """Transport qualification with an explicitly synthetic engine, NOT model quality."""
    class FakeRuntime:
        frame_samples = 8960
        model_id = "nemotron35-base-en"
        chunk_ms = 560
        identity = {"id": model_id, "test_double": True}
        profile = SimpleNamespace(confidence=False)
        def __init__(self, **kwargs):
            self.active = None
        def load(self):
            pass
        def begin(self, options):
            assert self.active is None
            self.active = 1
            return 1
        def close(self, stream):
            self.active = None
        def step(self, stream, frame, options):
            return SimpleNamespace(final_transcript="test engine output" if frame.last else "",
                                   partial_transcript="" if frame.last else "test engine", final_segments=[])
    monkeypatch.setattr(server, "NeMoRuntime", FakeRuntime)
    monkeypatch.setenv("API_BEARER_TOKEN", "this-is-a-test-only-token-123456")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STATE_BUCKET", raising=False)
    monkeypatch.delenv("MODEL_S3_KEY", raising=False)
    headers = {"Authorization": "Bearer this-is-a-test-only-token-123456"}
    with TestClient(server.app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/v1/models").status_code == 401
        assert client.get("/v1/models", headers=headers).json()["data"][0]["model"]["test_double"]
        artifact = client.post("/v1/artifacts", headers=headers,
                               files={"file": ("test.wav", wav_bytes(), "audio/wav")}).json()["artifact"]
        request = {"audio_artifact": artifact, "idempotency_key": "http-test-123", "options": {"model": "nemotron35-base-en"}}
        accepted = client.post("/v1/transcriptions", headers=headers, json=request)
        assert accepted.status_code == 202 and accepted.headers["x-request-id"]
        operation_id = accepted.json()["id"]
        for _ in range(100):
            operation = client.get("/v1/operations/" + operation_id, headers=headers).json()
            if operation["status"] == "succeeded":
                break
            time.sleep(0.01)
        assert operation["result"]["text"] == "test engine output"
        assert client.post("/v1/transcriptions", headers=headers, json=request).json()["id"] == operation_id
        with client.websocket_connect("/v1/audio/stream", headers=headers) as ws:
            ws.send_json({"type": "session.start", "options": {"model": "nemotron35-base-en"}})
            assert ws.receive_json()["type"] == "session.ready"
            ws.send_bytes(b"\0\0" * 16000)
            ws.send_json({"type": "input.finish"})
            events = []
            while True:
                event = ws.receive_json()
                events.append(event)
                if event["type"] == "session.completed":
                    break
            assert [e["type"] for e in events] == ["transcript.partial", "transcript.final", "session.completed"]
        mcp_headers = {**headers, "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
        initialized = client.post("/mcp", headers=mcp_headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        assert initialized.status_code == 200
        listing = client.post("/mcp", headers=mcp_headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = listing.json()["result"]["tools"]
        assert {t["name"] for t in tools} == {"describe_clinical_asr", "transcribe_clinical_audio", "get_clinical_transcription", "cancel_clinical_transcription"}
        polled = client.post("/mcp", headers=mcp_headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                             "params": {"name": "get_clinical_transcription", "arguments": {"operation_id": operation_id}}})
        assert not polled.json()["result"]["isError"]
        assert operation_id in polled.text
        mcp_request = {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
            "name": "transcribe_clinical_audio", "arguments": {"audio_artifact": artifact,
                "idempotency_key": "mcp-submit-test-123", "model": "nemotron35-base-en"}}}
        mcp_submitted = client.post("/mcp", headers=mcp_headers, json=mcp_request).json()["result"]
        assert not mcp_submitted["isError"]
        mcp_operation = mcp_submitted["structuredContent"]
        assert mcp_operation["durable_admission"] is True
        replayed = client.post("/mcp", headers=mcp_headers, json=mcp_request).json()["result"]["structuredContent"]
        assert replayed["id"] == mcp_operation["id"]
        for _ in range(100):
            mcp_operation = client.get("/v1/operations/" + mcp_operation["id"], headers=headers).json()
            if mcp_operation["status"] == "succeeded":
                break
            time.sleep(0.01)
        assert mcp_operation["status"] == "succeeded"
        assert mcp_operation["result"]["text"] == "test engine output"
