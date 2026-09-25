import pytest
from clinical_asr.cloud_evaluate import evaluate_cohorts
from clinical_asr.runtime import NeMoRuntime


def test_english_benchmark_is_explicit_and_has_separate_output(tmp_path):
    calls = []
    cohort = {'name': 'frozen', 'manifest': tmp_path / 'refs.jsonl', 'directory': tmp_path}
    evaluate_cohorts([cohort], 'candidate.nemo', 'a' * 64, lambda name, args: calls.append((name, args)))
    assert len(calls) == 2
    calls.clear()
    evaluate_cohorts([cohort], 'candidate.nemo', 'a' * 64, lambda name, args: calls.append((name, args)),
                     include_english_specialist=True)
    assert len(calls) == 3 and calls[-1][1][0] == 'evaluate-english'
    assert calls[-1][1][-1].endswith('english-specialist-predictions.jsonl')


def test_family_requires_checkpoint_and_does_not_relabel_base_as_finetuned():
    with pytest.raises(ValueError, match='pinned_checkpoint'):
        NeMoRuntime(model_family='english_specialist')
    model = NeMoRuntime(checkpoint='pinned.nemo', checkpoint_sha='a' * 64,
                        model_family='english_specialist', fine_tuned=False)
    assert model.fine_tuned is False
    assert NeMoRuntime().model_family == 'nemotron35'
