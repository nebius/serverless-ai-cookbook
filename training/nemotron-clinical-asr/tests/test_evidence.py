import json
import wave
import pytest

from clinical_asr.consumption import ConsumptionAudit
from clinical_asr import environment
from clinical_asr.train import validate_manifests


def test_environment_never_collects_credentials(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN", "do-not-copy-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "do-not-copy-secret")
    monkeypatch.setenv("CUDA_MODULE_LOADING", "LAZY")
    monkeypatch.setattr(environment, "run", lambda command: {"available": False})
    monkeypatch.setattr(environment, "python_stack", lambda: {})
    evidence = environment.collect()
    assert evidence["safe_environment"]["CUDA_MODULE_LOADING"] == "LAZY"
    assert "do-not-copy-secret" not in json.dumps(evidence)


def test_consumed_tokens_require_unique_exact_sample_length(tmp_path):
    audio = tmp_path / "source.wav"
    with wave.open(str(audio), "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        target.writeframes(b"\x00\x00" * 16000)
    row = {"id": "source_1", "audio_filepath": str(audio), "text": "source",
           "target_lang": "en-US", "conversation_id": "source"}
    audit = ConsumptionAudit([row], lambda text, lang: [2, 7], tmp_path / "consumed.jsonl")
    result = audit.record([[2, 7], [2, 7]], [16000, 16001], batch_index=0, step_before=0, step_after=1)
    assert result[0]["match"] == "unique"
    assert result[0]["candidate_segments"][0]["id"] == "source_1"
    assert result[1]["match"] == "unmatched"
    audit = ConsumptionAudit([row, {**row, "id": "source_2"}], lambda text, lang: [2, 7], tmp_path / "ambiguous.jsonl")
    assert audit.record([[2, 7]], [16000], batch_index=0, step_before=0, step_after=1)[0]["match"] == "ambiguous"
    with pytest.raises(ValueError, match="new_attempt_required"):
        ConsumptionAudit([row], lambda text, lang: [2, 7], tmp_path / "consumed.jsonl")


def test_manifest_split_labels_fail_closed(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.touch()
    row = {"conversation_id": "train", "duration": 1.0, "text": "hello", "target_lang": "en-US", "audio_filepath": str(audio)}
    train, dev = tmp_path / "train.jsonl", tmp_path / "dev.jsonl"
    dev.write_text(json.dumps({**row, "conversation_id": "dev", "split": "dev"}) + "\n")
    for invalid_split in [None, "test", "dev"]:
        train.write_text(json.dumps({**row, "split": invalid_split}) + "\n")
        with pytest.raises(ValueError, match="explicit_train_dev_split"):
            validate_manifests(train, dev)
    train.write_text(json.dumps({**row, "split": "train"}) + "\n")
    assert len(validate_manifests(train, dev)[0]) == 1
