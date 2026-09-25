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


def test_explicit_corpus_requires_actual_unambiguous_component_consumption():
    counter = ExposureCounter()
    counter.update([{"audio_samples": 16000, "candidate_segments": [
        {"conversation_id": "clinical", "training_corpus": "simulated_clinical"},
        {"conversation_id": "day1_consultation03", "training_corpus": "primock57"}]}])
    assert counter.summary(1)["audio_seconds"]["clinical"] == 1
    assert counter.summary(1)["corpus_audio_seconds"] == {"unresolved": 1}
    with pytest.raises(RuntimeError, match="not_actually_consumed"):
        counter.validate_corpora(["primock57"], 50, 50)
    counter.update([{"audio_samples": 32000, "candidate_segments": [
        {"conversation_id": "day1_consultation03", "training_corpus": "primock57"}]}])
    counter.validate_corpora(["primock57"], 50, 50)
    assert counter.summary(50)["corpus_audio_seconds"]["primock57"] == 2
