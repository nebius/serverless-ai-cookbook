import pytest
from clinical_asr.exposure import ExposureCounter


def record(names, samples=16000):
    return {"audio_samples": samples, "candidate_segments": [{"conversation_id": name} for name in names]}


def test_actual_exposure_uses_domains_not_manifest_membership():
    counter = ExposureCounter()
    counter.update([record(["clinical-a", "clinical-b"]), record([], 8000),
                    record(["librispeech-train-clean100:a:b"], 32000)])
    assert counter.summary(50)["audio_seconds"] == {"clinical": 1.0, "general_replay": 2.0, "unresolved": 0.5}
    counter.validate("mixed", 50, 50)
    with pytest.raises(RuntimeError, match="unexpected_replay"):
        counter.validate("clinical-only", 50, 50)


def test_cross_domain_ambiguity_cannot_pass_replay_guard():
    counter = ExposureCounter()
    counter.update([record(["clinical", "librispeech-train-clean100:a:b"])])
    counter.validate("mixed", 49, 50)
    with pytest.raises(RuntimeError, match="not_consumed"):
        counter.validate("mixed", 50, 50)
