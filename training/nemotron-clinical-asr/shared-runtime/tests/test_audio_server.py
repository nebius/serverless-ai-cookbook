import asyncio
import hashlib
import wave
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_stream import FINISH, START, FakeRuntime

from fs2_speech.audio import AudioInputError, DownloadAudio, decoded_pcm, download_audio, transcribe_file
from fs2_speech.contracts import ENGLISH_ID, RuntimeProfile, SpeechOptions
from fs2_speech.server import create_app


def fixture(path, samples=1600):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x01\0" * samples)


def app(runtime=None):
    return create_app(runtime or FakeRuntime(), RuntimeProfile(model=ENGLISH_ID),
                      allowed_hosts=frozenset({"storage.example.test"}), load=False)


def test_failed_websocket_accept_releases_admitted_slot():
    application = app()

    class FailedHandshake:
        headers = {}

        async def accept(self):
            raise RuntimeError("handshake disconnected")

    endpoint = next(route.endpoint for route in application.routes if route.path == "/v1/audio/stream")
    asyncio.run(endpoint(FailedHandshake()))
    assert application.state.runtime_state["active"] == 0
    assert application.state.scheduled_runtime.scheduler.snapshot()["active_sessions"] == 0


def test_drain_requires_configured_gateway_auth(tmp_path, monkeypatch):
    token = tmp_path / "worker-token"
    token.write_text("x" * 32)
    monkeypatch.setenv("FS2_STT_GATEWAY_TOKEN_FILE", str(token))
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "1")
    with TestClient(app()) as client:
        assert client.post("/drain").status_code == 401
        assert client.get("/readyz").status_code == 200
        assert client.post("/drain", headers={"Authorization": "Bearer " + "x" * 32}).status_code == 200
        assert client.get("/readyz").status_code == 503


def test_derivative_file_revision_is_actual_checkpoint_not_parent(tmp_path, monkeypatch):
    runtime = FakeRuntime()
    runtime.identity = lambda: {"checkpoint_kind": "operator_pinned", "checkpoint_sha256": "b" * 64,
                                "parent_revision": "parent-only"}

    async def download(source, path, hosts):
        fixture(path)

    monkeypatch.setattr("fs2_speech.server.download_audio", download)
    with TestClient(app(runtime)) as client:
        result = client.post("/generate", json={
            "audio": {"url": "https://storage.example.test/test.wav", "sha256": "a" * 64,
                      "size_bytes": 100, "media_type": "audio/wav"},
            "options": {"model": ENGLISH_ID},
        })
        assert result.status_code == 200
        assert result.json()["model_revision"] == "sha256:" + "b" * 64
        assert result.json()["runtime_identity"]["parent_revision"] == "parent-only"


def test_real_ffmpeg_preserves_every_sample_and_long_tail(tmp_path):
    path = tmp_path / "fixture.wav"
    fixture(path, 33001)

    async def collect():
        return b"".join([chunk async for chunk in decoded_pcm(path)])

    assert asyncio.run(collect()) == b"\x01\0" * 33001


def test_decode_limit_rejects_instead_of_reporting_truncated_success(tmp_path):
    path = tmp_path / "fixture.wav"
    fixture(path, 1600)

    async def collect():
        return [chunk async for chunk in decoded_pcm(path, max_seconds=0.01)]

    with pytest.raises(AudioInputError, match="audio_duration_exceeded"):
        asyncio.run(collect())


def test_bad_audio_does_not_return_success(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"invalid")
    with pytest.raises(AudioInputError, match="audio_decode_failed"):
        asyncio.run(transcribe_file(FakeRuntime(), path, SpeechOptions(model=ENGLISH_ID)))


def test_complete_file_finalizes_tail_and_does_not_append_partials(tmp_path):
    path = tmp_path / "fixture.wav"
    fixture(path, 1001)
    runtime = FakeRuntime()
    result = asyncio.run(transcribe_file(runtime, path, SpeechOptions(model=ENGLISH_ID)))
    assert result["text"] == "Complete."
    assert result["audio_seconds"] == 1001 / 16000
    assert sum(frame.valid_samples for frame in runtime.frames) == 1001
    assert runtime.frames[-1].last
    assert runtime.closed == [1]


def test_complete_file_uses_explicit_boundary_without_changing_native_finals(tmp_path):
    class BoundaryRuntime(FakeRuntime):
        frame_samples = 16000

        def step(self, stream_id, frame, options):
            output = super().step(stream_id, frame, options)
            output.final_transcript = "shall we stop?" if frame.last else "Hello, hi"
            output.partial_transcript = ""
            if frame.last:
                output.separator_before = " "
            return output

    path = tmp_path / "fixture.wav"
    fixture(path, 16001)
    result = asyncio.run(transcribe_file(BoundaryRuntime(), path, SpeechOptions(model=ENGLISH_ID)))
    assert result["text"] == "Hello, hi shall we stop?"
    assert [event["text"] for event in result["segments"]] == ["Hello, hi", "shall we stop?"]
    assert result["segments"][-1]["separator_before"] == " "


@pytest.mark.parametrize("url", [
    "http://storage.example.test/a", "https://other.test/a", "https://user@storage.example.test/a",
    "https://storage.example.test:444/a", "https://storage.example.test/a#fragment",
])
def test_internal_download_rejects_non_gateway_artifact_hosts(tmp_path, url):
    source = DownloadAudio(url=url, sha256=hashlib.sha256(b"x").hexdigest(), size_bytes=1, media_type="audio/wav")
    with pytest.raises(AudioInputError, match="invalid_audio_artifact"):
        asyncio.run(download_audio(source, tmp_path / "unused", frozenset({"storage.example.test"})))


def test_websocket_transcribes_incrementally_then_drains():
    runtime = FakeRuntime()
    with TestClient(app(runtime)) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        with client.websocket_connect("/v1/audio/stream") as stream:
            stream.send_text(START)
            assert stream.receive_json()["type"] == "session.ready"
            stream.send_bytes(b"\0" * 6)
            assert stream.receive_json()["type"] == "transcript.partial"
            assert client.get("/readyz").json()["active_sessions"] == 1
            assert client.post("/drain").status_code == 200
            assert client.get("/readyz").status_code == 503
            stream.send_text(FINISH)
            assert stream.receive_json()["type"] == "transcript.final"
            assert stream.receive_json()["type"] == "session.completed"
        assert runtime.closed == [1]
        assert b'fs2_speech_sessions_total{mode="live",outcome="completed"} 1.0' in client.get("/metrics").content


def test_busy_stream_is_explicit_and_disconnect_frees_capacity():
    runtime = FakeRuntime()
    with TestClient(app(runtime)) as client:
        with client.websocket_connect("/v1/audio/stream") as first:
            first.send_text(START)
            first.receive_json()
            with client.websocket_connect("/v1/audio/stream") as second:
                assert second.receive_json()["code"] == "runtime_busy"
        assert client.get("/readyz").json()["active_sessions"] == 0
        with client.websocket_connect("/v1/audio/stream") as stream:
            stream.send_text(START)
            assert stream.receive_json()["type"] == "session.ready"
            stream.send_text('{"type":"session.cancel"}')
            assert stream.receive_json()["type"] == "session.cancelled"


def test_file_runtime_rejects_profile_mismatch_before_acquiring():
    with TestClient(app()) as client:
        result = client.post("/generate", json={
            "audio": {"url": "https://storage.example.test/file", "sha256": "a" * 64,
                      "size_bytes": 12, "media_type": "audio/wav"},
            "options": {"model": ENGLISH_ID, "chunk_size_ms": 80},
        })
        assert result.status_code == 422
        assert client.get("/readyz").json()["active_sessions"] == 0


def test_two_streams_are_isolated_and_one_cancel_keeps_other_state():
    class IsolatedRuntime(FakeRuntime):
        def __init__(self):
            super().__init__()
            self.states = {}
            self.next_id = 0

        def begin(self, options):
            self.next_id += 1
            self.states[self.next_id] = ""
            return self.next_id

        def step_batch(self, entries):
            values = []
            for sid, frame, _ in entries:
                self.states[sid] += frame.pcm[:frame.valid_samples * 2:2].decode()
                values.append(SimpleNamespace(final_transcript=self.states[sid] if frame.last else "",
                                              partial_transcript="" if frame.last else self.states[sid]))
            return values

        def close(self, sid):
            self.closed.append(sid)
            self.states.pop(sid)

    runtime = IsolatedRuntime()
    application = create_app(runtime, RuntimeProfile(model=ENGLISH_ID), allowed_hosts=frozenset(),
                             load=False, max_sessions=2, max_batch_size=2)
    with TestClient(application) as client:
        with client.websocket_connect("/v1/audio/stream") as a, client.websocket_connect("/v1/audio/stream") as b:
            for stream in (a, b):
                stream.send_text(START)
                assert stream.receive_json()["type"] == "session.ready"
            a.send_bytes(b"A\0A\0A\0")
            b.send_bytes(b"B\0B\0B\0")
            assert a.receive_json()["text"] == "AA"
            assert b.receive_json()["text"] == "BB"
            a.send_json({"type": "session.cancel"})
            assert a.receive_json()["type"] == "session.cancelled"
            b.send_text(FINISH)
            assert b.receive_json()["text"] == "BBB"
            assert b.receive_json()["type"] == "session.completed"
        assert runtime.states == {}
        assert client.get("/readyz").json()["active_sessions"] == 0
