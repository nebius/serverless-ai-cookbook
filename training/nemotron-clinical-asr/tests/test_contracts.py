import asyncio
import io
import json
import wave
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from clinical_asr.contracts import SpeechOptions, TranscriptionRequest
from clinical_asr.events import TranscriptEvents
from clinical_asr.framing import PCMFramer
from clinical_asr.prepare import grouped_words
from clinical_asr.runtime import NeMoRuntime
from clinical_asr.server import APIError, Service
from clinical_asr.stream import run_stream
from clinical_asr.train import validate_manifests


def test_pcm_exact_tail_and_short_final():
    framer = PCMFramer(4)
    assert framer.push(b"\1\0" * 4) == []
    first = framer.push(b"\2\0")[0]
    final = framer.finish()
    assert first.first and not first.last and first.valid_samples == 4
    assert final.last and not final.first and final.valid_samples == 1
    assert framer.total_samples == 5 and len(final.pcm) == 8
    with pytest.raises(ValueError):
        framer.finish()


def test_revisions_replace_and_no_fabricated_final():
    events = TranscriptEvents("test")
    assert events.update(partial="metform")[0].revision == 1
    assert events.update(partial="metformin")[0].revision == 2
    final = events.update(final="metformin")[0]
    assert final.segment_id == 0 and final.revision == 3
    assert events.update(partial="500")[0].segment_id == 1
    with pytest.raises(ValueError, match="did_not_finalize"):
        events.update(partial="500", last=True)


def test_no_fake_clinical_checkpoint():
    with pytest.raises(ValueError, match="actual_finetuned"):
        NeMoRuntime(model_id="nemotron-clinical-en")


def test_word_boundary_grouping():
    words = [(0, 1, "One"), (1, 2, "two"), (5, 6, "Three")]
    assert list(grouped_words(words)) == [words[:2], words[2:]]
    with pytest.raises(ValueError):
        list(grouped_words([(1, 0, "bad")]))


def test_conversation_leakage_rejected(tmp_path):
    row = {"conversation_id": "shared", "duration": 1.0, "text": "hello", "target_lang": "en-US", "audio_filepath": str(tmp_path / "audio.wav")}
    (tmp_path / "audio.wav").touch()
    for split in ["train", "dev"]:
        (tmp_path / f"{split}.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="conversation_leakage"):
        validate_manifests(tmp_path / "train.jsonl", tmp_path / "dev.jsonl")


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    return buffer.getvalue()


def test_durable_idempotency_cancel_and_restart(tmp_path):
    async def scenario():
        runtime = SimpleNamespace(model_id="nemotron35-base-en", chunk_ms=560, identity={})
        service = Service(tmp_path, runtime)
        service.ready = True
        upload = await service.upload(UploadFile(io.BytesIO(wav_bytes()), filename="test.wav"))
        request = TranscriptionRequest(audio_artifact=upload["artifact"], idempotency_key="test-request-1", options=SpeechOptions(model=runtime.model_id))
        first = service.submit(request)
        assert service.submit(request)["id"] == first["id"]
        assert service.queue.qsize() == 1
        other = request.model_copy(update={"options": SpeechOptions(model=runtime.model_id, output_granularity="word")})
        with pytest.raises(APIError) as error:
            service.submit(other)
        assert error.value.detail["code"] == "idempotency_conflict"
        restored = Service(tmp_path, runtime)
        assert restored.poll(first["id"])["error"]["code"] == "worker_interrupted"
        assert restored.submit(request)["id"] == first["id"]
        cancelled = service.cancel(first["id"])
        assert cancelled["status"] == "cancelled"
    asyncio.run(scenario())


def test_stream_calls_runtime_incrementally_and_closes():
    class FakeRuntime:
        frame_samples = 4
        profile = SimpleNamespace(confidence=False)
        def __init__(self):
            self.calls = []
            self.closed = []
        def begin(self, options):
            return 12
        def step(self, stream, frame, options):
            self.calls.append(frame)
            return SimpleNamespace(final_transcript="final" if frame.last else "", partial_transcript="" if frame.last else "partial", final_segments=[])
        def close(self, stream):
            self.closed.append(stream)
    async def scenario():
        runtime = FakeRuntime()
        async def messages():
            yield json.dumps({"type": "session.start", "options": {"model": "nemotron35-base-en"}})
            yield b"\1\0" * 9
            yield '{"type":"input.finish"}'
        output = []
        async def send(value):
            output.append(value)
        await run_stream(runtime, messages(), send)
        assert [f.valid_samples for f in runtime.calls] == [4, 4, 1]
        assert runtime.closed == [12]
        assert output[-1]["type"] == "session.completed"
        assert any(e["type"] == "transcript.partial" for e in output)
    asyncio.run(scenario())
