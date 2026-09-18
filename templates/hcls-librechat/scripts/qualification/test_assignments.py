import json

import pytest

from run_campaign import freeze_assignments


def args():
    return {"cohort": "c1", "manifest_sha256": "x", "cases": [{"case_id": str(i)} for i in range(4)],
            "people": [{"id": "a"}, {"id": "b"}]}


def test_resume_retains_exact_owner(tmp_path):
    first = freeze_assignments(tmp_path, **args())
    assert first["assignments"] == {"a": ["0", "2"], "b": ["1", "3"]}
    assert freeze_assignments(tmp_path, **args()) == first


@pytest.mark.parametrize("change", [{"people": [{"id": "b"}]}, {"cohort": "c2"},
                                    {"cases": [{"case_id": "new"}]}])
def test_resume_rejects_repartition(tmp_path, change):
    freeze_assignments(tmp_path, **args())
    with pytest.raises(ValueError, match="frozen case ownership"):
        freeze_assignments(tmp_path, **{**args(), **change})


def test_legacy_or_duplicate_is_not_silently_rewritten(tmp_path):
    (tmp_path / "campaign.json").write_text(json.dumps({"legacy": True}))
    with pytest.raises(ValueError, match="Legacy"):
        freeze_assignments(tmp_path, **args())
    with pytest.raises(ValueError, match="unique"):
        freeze_assignments(tmp_path, **{**args(), "cases": [{"case_id": "a"}, {"case_id": "a"}]})


def test_exact_replay_selection_preserves_manifest_order_and_rejects_unknown_cases():
    from run_campaign import select_case_ids
    cases = [{"case_id": "a"}, {"case_id": "b"}, {"case_id": "c"}]
    assert select_case_ids(cases, "c,a") == [cases[0], cases[2]]
    assert select_case_ids(cases, "") is cases
    with pytest.raises(ValueError, match="absent"):
        select_case_ids(cases, "typo")
