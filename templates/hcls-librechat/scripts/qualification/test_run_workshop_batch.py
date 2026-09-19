from copy import deepcopy

import pytest

from run_workshop_batch import (
    AXES,
    CLINICIANS,
    PATIENT,
    request_for,
    validate_admission,
    verify_report,
)


def catalog():
    return {
        "catalog": {
            "data": [
                {"id": m, "clinician_eligible": m in CLINICIANS}
                for m in [*CLINICIANS, PATIENT]
            ],
            "judge_model": "google/gemma-3-27b-it",
        },
        "profiles": {"data": [{"id": f"profile-{i:03}"} for i in range(40)]},
    }


def rows():
    request = request_for(catalog())
    return request, [
        {
            "id": f"{p}-{m}",
            "state": {
                "worker_limit": 1,
                "config": {**request, "profile_id": p, "clinician_model": m},
            },
        }
        for p in request["profile_ids"]
        for m in CLINICIANS
    ]


def report():
    return {
        "run": {
            "id": "run-one",
            "status": "completed",
            "created_at": "start",
            "updated_at": "end",
            "state": {
                "transcript": [{"role": "patient", "content": "Hello"}]
                + [
                    {
                        "role": role,
                        "content": "Synthetic utterance",
                        "completion": {"finish_reason": "stop"},
                    }
                    for _ in range(10)
                    for role in ["clinician", "patient"]
                ],
                "intervened": False,
                "judgment": {
                    "model": "google/gemma-3-27b-it",
                    "judgment": {axis: 4.5 for axis in AXES},
                    "finish_reason": "stop",
                },
            },
        },
        "events": [{"kind": "turn.completed"} for _ in range(20)],
    }


def test_frozen_matrix_is_sixty_runs_without_worker_increase():
    request, admitted = rows()
    assert len(admitted) == 60
    assert request["max_completion_tokens"] == 4096 and request["max_turns"] == 10
    validate_admission(admitted, request)


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "different_model", "workers", "budget"]
)
def test_admission_rejects_matrix_or_policy_drift(change):
    request, admitted = rows()
    if change == "missing":
        admitted.pop()
    elif change == "duplicate":
        admitted[1] = deepcopy(admitted[0])
    elif change == "different_model":
        admitted[0]["state"]["config"]["clinician_model"] = "unexpected"
    elif change == "workers":
        admitted[0]["state"]["worker_limit"] = 5
    else:
        admitted[0]["state"]["config"]["max_completion_tokens"] = 8192
    with pytest.raises(ValueError):
        validate_admission(admitted, request)


@pytest.mark.parametrize("change", ["judge", "clinician", "profiles"])
def test_catalog_cannot_silently_replace_the_comparison(change):
    value = catalog()
    if change == "judge":
        value["catalog"]["judge_model"] = CLINICIANS[0]
    elif change == "clinician":
        value["catalog"]["data"][0]["clinician_eligible"] = False
    else:
        value["profiles"]["data"] = [{"id": "same"}] * 20
    with pytest.raises(ValueError):
        request_for(value)


def test_complete_export_is_only_structural_evidence():
    result = verify_report(report(), request_for(catalog()))
    assert result["structural_workflow_pass"]
    assert (
        not result["clinical_validation"] and not result["natural_librechat_acceptance"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "short",
        "role",
        "empty",
        "truncated",
        "score",
        "judge",
        "event",
        "failed",
        "intervened",
    ],
)
def test_report_defects_are_not_hidden_by_completed_status(change):
    value = report()
    state = value["run"]["state"]
    if change == "short":
        state["transcript"].pop()
    elif change == "role":
        state["transcript"][1]["role"] = "patient"
    elif change == "empty":
        state["transcript"][1]["content"] = " "
    elif change == "truncated":
        state["transcript"][1]["completion"]["finish_reason"] = "length"
    elif change == "score":
        state["judgment"]["judgment"][next(iter(AXES))] = float("nan")
    elif change == "judge":
        state["judgment"]["model"] = CLINICIANS[0]
    elif change == "event":
        value["events"].pop()
    elif change == "failed":
        value["run"]["status"] = "failed"
    else:
        state["intervened"] = True
    assert not verify_report(value, request_for(catalog()))["structural_workflow_pass"]
