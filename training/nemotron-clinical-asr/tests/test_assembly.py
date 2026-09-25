from types import SimpleNamespace
import wave

import pytest

from clinical_asr.assembly import TEXT_ASSEMBLY, assemble_final_fragments
from clinical_asr.evaluate import transcribe_wav


@pytest.mark.parametrize("fragments,expected", [
    (["naus", "ea and vomiting"], "nausea and vomiting"),
    (["sor", "ry"], "sorry"),
    ([" Hello", " world."], "Hello world."),
    (["Hello ", "world."], "Hello world."),
    ([" Hello", "  world. "], "Hello  world."),
    (["Hello", "how"], "Hellohow"),  # Preserve native error, no language repair.
    (["four hun", "dred milligrams"], "four hundred milligrams"),
    ([], ""),
])
def test_native_final_boundaries_are_not_word_boundaries(fragments, expected):
    events = [{"type": "transcript.partial", "text": "stale hypothesis"}]
    events += [{"type": "transcript.final", "text": text} for text in fragments]
    assert assemble_final_fragments(events) == expected


def test_invalid_final_fragment_fails_closed():
    with pytest.raises(ValueError, match="invalid_final_fragment"):
        assemble_final_fragments([{"type": "transcript.final", "text": None}])


def test_real_batch_wrapper_preserves_native_fragments(tmp_path):
    audio = tmp_path / "source.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        handle.writeframes(b"\x00\x00" * 16000)

    class Runtime:
        frame_samples = 8000
        model_id = "fake-contract-test"
        identity = {"scope": "offline fake runtime, not model qualification"}
        closed = False
        calls = 0

        def begin(self, options):
            return 1

        def step(self, stream_id, frame, options):
            self.calls += 1
            value = ["naus", "ea and vomiting", ""][self.calls - 1]
            return SimpleNamespace(final_transcript=value, partial_transcript="", final_segments=[])

        def close(self, stream_id):
            self.closed = True

    runtime = Runtime()
    result = transcribe_wav(runtime, audio, SimpleNamespace(output_granularity="word"))
    assert result["text"] == "nausea and vomiting"
    assert result["text_assembly"] == TEXT_ASSEMBLY
    assert [event["text"] for event in result["events"]] == ["naus", "ea and vomiting"]
    assert result["audio_seconds"] == 1.0
    assert runtime.closed
