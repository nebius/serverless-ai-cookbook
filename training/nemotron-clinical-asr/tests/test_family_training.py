import sys
from types import SimpleNamespace

import pytest

from clinical_asr.cloud_evaluate import evaluate_cohorts
from clinical_asr.common import base_checkpoint
from clinical_asr.families import assert_training_model, family_spec, runtime_model_class, training_batch_evidence


def test_pins_and_native_training_contracts_are_explicit():
    english = family_spec("english_specialist")
    multi = family_spec("nemotron35")
    assert (english.left_context, multi.left_context) == (70, 56)
    assert english.model_class == "EncDecRNNTBPEModel"
    assert multi.model_class == "EncDecRNNTBPEModelWithPrompt"
    assert english.revision == "ebe59e5a817142986528bbbee5dba8db7b38ed50"
    assert training_batch_evidence(["audio", "lens", "tokens", "token_lens"], "english_specialist") == (
        "lens", "tokens", "token_lens")
    assert training_batch_evidence(["audio", "lens", "tokens", "token_lens", "prompt"], "nemotron35") == (
        "lens", "tokens", "token_lens")
    for name, batch in [("english_specialist", [0] * 5), ("nemotron35", [0] * 4)]:
        with pytest.raises(ValueError, match="batch_contract"):
            training_batch_evidence(batch, name)
    with pytest.raises(ValueError, match="unknown_model_family"):
        family_spec("guessed-model")


def test_restored_family_class_must_match():
    english = type("EncDecRNNTBPEModel", (), {})()
    assert_training_model(english, "english_specialist")
    with pytest.raises(ValueError, match="class_mismatch"):
        assert_training_model(english, "nemotron35")


def test_runtime_family_checks_actual_restored_object_not_requested_label():
    model = type("EncDecRNNTBPEModel", (), {})()
    pipeline = SimpleNamespace(asr_model=SimpleNamespace(asr_model=model))
    assert runtime_model_class(pipeline, "english_specialist") == "EncDecRNNTBPEModel"
    with pytest.raises(ValueError, match="class_mismatch"):
        runtime_model_class(pipeline, "nemotron35")
    with pytest.raises(ValueError, match="class_mismatch"):
        runtime_model_class(SimpleNamespace(), "english_specialist")


def test_base_download_is_revision_and_checksum_pinned(monkeypatch, tmp_path):
    from clinical_asr import common
    local = tmp_path / "model.nemo"
    local.write_bytes(b"fixture")
    calls = []
    def download(repo, filename, revision):
        calls.append((repo, filename, revision))
        return str(local)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(hf_hub_download=download))
    monkeypatch.setattr(common, "sha256_file", lambda path: family_spec("english_specialist").sha256)
    assert base_checkpoint("english_specialist") == str(local)
    assert calls == [(family_spec("english_specialist").repository, family_spec("english_specialist").filename,
                      family_spec("english_specialist").revision)]
    monkeypatch.setattr(common, "sha256_file", lambda path: "0" * 64)
    with pytest.raises(ValueError, match="upstream_checkpoint_sha256_mismatch"):
        base_checkpoint("english_specialist")


def test_english_candidate_pairs_with_english_base_and_marks_family(tmp_path):
    calls = []
    cohort = {"name": "fixed", "manifest": tmp_path / "ref.jsonl", "directory": tmp_path}
    evaluate_cohorts([cohort], "tuned.nemo", "a" * 64, lambda name, args: calls.append((name, args)),
                     model_family="english_specialist")
    assert calls[0][1][0] == "evaluate-english"
    assert calls[0][1][-1].endswith("base-predictions.jsonl")
    assert calls[1][1][0] == "evaluate"
    assert calls[1][1][-2:] == ["--model-family", "english_specialist"]
    with pytest.raises(ValueError, match="already_in_paired_comparison"):
        evaluate_cohorts([cohort], "tuned.nemo", "a" * 64, lambda *args: None,
                         model_family="english_specialist", include_english_specialist=True)
