import copy
import json

import pytest

from run_workshop_batch import AXES
from summarize_workshop_cohort import analyze


def fixture():
    request = {
        "profile_ids": ["profile-000", "profile-001"],
        "clinician_models": ["model-a", "model-b"],
        "patient_model": "patient",
        "max_turns": 1,
    }
    frozen = {"request": request, "cohort": "test", "judge": "google/gemma-3-27b-it"}
    rows, reports = [], {}
    for i, (profile, model) in enumerate(
        (p, m) for p in request["profile_ids"] for m in request["clinician_models"]
    ):

        def completed(role):
            return {
                "model": model if role == "clinician" else "patient",
                "content": "PRIVATE_CONTENT",
                "reasoning": "PRIVATE_REASONING",
                "finish_reason": "stop",
                "telemetry": {
                    "request_id": f"{i}-{role}",
                    "retries": 0,
                    "latency_ms": 100,
                    "queue_ms": 2,
                },
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 4,
                    "total_tokens": 9,
                },
            }

        row = {
            "id": str(i),
            "status": "completed",
            "created_at": "2026-09-19T03:00:00Z",
            "updated_at": "2026-09-19T04:00:00Z",
            "state": {
                "worker_limit": 1,
                "config": {**request, "profile_id": profile, "clinician_model": model},
                "profile": {"name": "PRIVATE_PROFILE"},
                "transcript": [
                    {"role": "patient", "seed": True, "content": "PRIVATE_GREETING"}
                ]
                + [
                    {
                        "role": role,
                        "source": "model",
                        "content": "PRIVATE_CONTENT",
                        "completion": completed(role),
                    }
                    for role in ("clinician", "patient")
                ],
                "judgment": {
                    **completed("judge"),
                    "model": "google/gemma-3-27b-it",
                    "judgment": {axis: 3 if model == "model-a" else 4 for axis in AXES},
                },
            },
        }
        rows.append(row)
        reports[str(i)] = {
            "run": copy.deepcopy(row),
            "events": [{"kind": "turn.completed"}] * 2,
        }
    return (
        frozen,
        rows,
        {"at": "2026-09-19T04:00:00Z", "data": copy.deepcopy(rows)},
        reports,
    )


def test_full_matrix_counts_paired_axes_and_no_private_content():
    result = analyze(*fixture())
    assert result["population"]["completed_model_responses"] == 12
    assert result["population"]["seeded_greetings_not_calls"] == 4
    assert result["report_coverage"]["complete_matrix"]
    assert len(result["paired_profile_axis_differences"]) == 2
    assert all(
        set(r["difference_a_minus_b"].values()) == {-1}
        for r in result["paired_profile_axis_differences"]
    )
    assert result["telemetry_by_role"]["judge"]["usage"]["total_tokens"] == {
        "observed_total": 36,
        "missing_responses": 0,
    }
    assert "PRIVATE_" not in json.dumps(result)


def test_partial_reports_never_produce_means_or_paired_differences():
    frozen, rows, latest, reports = fixture()
    reports.pop("3")
    result = analyze(frozen, rows, latest, reports)
    assert result["report_coverage"]["retained"] == 3
    assert not result["report_coverage"]["complete_matrix"]
    assert result["descriptive_axis_means"] == {}
    assert result["paired_profile_axis_differences"] == []


@pytest.mark.parametrize("invalid", [float("nan"), True, 7, "3"])
def test_invalid_axis_suppresses_complete_comparison(invalid):
    frozen, rows, latest, reports = fixture()
    reports["0"]["run"]["state"]["judgment"]["judgment"][next(iter(AXES))] = invalid
    result = analyze(frozen, rows, latest, reports)
    assert not result["report_coverage"]["complete_matrix"]
    assert result["paired_profile_axis_differences"] == []
    assert "five_valid_criteria" in result["issues"][0]["failed_checks"]


def test_wrong_report_identity_and_duplicate_admission_are_rejected():
    frozen, rows, latest, reports = fixture()
    reports["0"]["run"]["state"]["config"]["profile_id"] = "profile-001"
    with pytest.raises(ValueError, match="configuration"):
        analyze(frozen, rows, latest, reports)
    frozen, rows, latest, reports = fixture()
    rows[1] = rows[0]
    with pytest.raises(ValueError, match="matrix"):
        analyze(frozen, rows, latest, reports)


def test_truncation_missing_usage_and_reported_retry_stay_visible():
    frozen, rows, latest, reports = fixture()
    value = latest["data"][0]["state"]["transcript"][1]["completion"]
    value.pop("usage")
    value["telemetry"]["retries"] = 2
    reports["0"]["run"]["state"]["transcript"][1]["completion"]["finish_reason"] = (
        "length"
    )
    result = analyze(frozen, rows, latest, reports)
    assert (
        result["population"]["reported_retry_attempts_not_deduplicated_provider_calls"]
        == 2
    )
    assert (
        result["telemetry_by_role"]["clinician"]["usage"]["total_tokens"][
            "missing_responses"
        ]
        == 1
    )
    assert not result["report_coverage"]["complete_matrix"]
    assert "no_truncated_turn" in result["issues"][0]["failed_checks"]
