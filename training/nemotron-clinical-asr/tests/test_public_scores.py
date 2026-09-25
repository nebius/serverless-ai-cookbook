import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("score_asr", Path(__file__).resolve().parents[1] / "evaluation/score_asr.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def test_medication_error_survives_low_generic_wer():
    ref = {"id": "one", "text": "Please continue taking metoprolol five milligrams every morning.",
           "keywords": [{"text": "metoprolol", "category": "medication"}]}
    out = score.score_one(ref, {"text": "Please continue taking metformin five milligrams every morning."})
    assert out["substitutions"] == 1
    assert out["keywords"][0]["error_count"] == 1
    assert score.aggregate([out])["clinical_keywords"]["keyword_error_rate"] == 1


def test_repeated_terms_do_not_get_credit_from_wrong_position():
    ref = {"id": "one", "text": "aspirin morning and aspirin evening", "keywords": [{"text": "aspirin", "category": "drug"}]}
    out = score.score_one(ref, {"text": "aspirin morning and ibuprofen evening"})
    assert out["keywords"][0]["reference_count"] == 2
    assert out["keywords"][0]["correct_count"] == 1


def test_decimal_dose_and_negation_are_not_normalized_away():
    assert score.tokens("Do not take 0.5 mg") != score.tokens("Do take 5 mg")
    out = score.score_one({"id": "one", "text": "Do not take 0.5 mg"}, {"text": "Do take 5 mg"})
    assert out["deletions"] == 1
    assert out["substitutions"] == 1


def test_extra_term_reported_separately():
    out = score.score_one({"id": "one", "text": "take aspirin", "keywords": [{"text": "aspirin"}]}, {"text": "take aspirin aspirin"})
    assert out["keywords"][0]["unsupported_occurrences"] == 1


def test_missing_keyword_annotation_fails_closed():
    import pytest
    with pytest.raises(ValueError):
        score.score_one({"id": "one", "text": "take aspirin", "keywords": [{"text": "metoprolol"}]}, {"text": "take aspirin"})


def test_empty_reference_does_not_become_perfect_score():
    out = score.score_one({"id": "one", "text": ""}, {"text": "hallucinated"})
    assert out["wer"] is None
    assert out["insertions"] == 1
