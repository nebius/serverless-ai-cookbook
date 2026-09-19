import copy
import json

from aggregate_campaign import markdown, scan, utc
from aggregate_workshop import scan_workshop

RUN = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
NOW = utc("2026-09-19T04:00:00Z")


def put(root, name, doc):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def complete(request, role="clinician"):
    return {
        "role": role,
        "source": "model",
        "human": False,
        "at": "2026-09-19T03:00:00Z",
        "completion": {
            "model": "test/model",
            "content": "PRIVATE_CONTENT",
            "reasoning": "PRIVATE_REASONING",
            "telemetry": {"request_id": request, "retries": 1},
            "usage": {"total_tokens": 9},
        },
    }


def run():
    return {
        "id": RUN,
        "status": "running",
        "updated_at": "2026-09-19T03:00:00Z",
        "version": 1,
        "state": {
            "config": {
                "max_turns": 10,
                "profile_id": "profile-001",
                "mode": "canonical",
            },
            "transcript": [
                {"role": "patient", "seed": True, "content": "PRIVATE_PROFILE"},
                complete("request-1"),
            ],
            "judgment": None,
        },
    }


def test_dedup_snapshots_seed_human_and_planned_rounds_not_calls(tmp_path):
    row = run()
    row["state"]["transcript"].append(
        {"role": "patient", "human": True, "content": "PRIVATE_HUMAN"}
    )
    put(tmp_path, "workshop-batches/full20-r1/admission.json", [row])
    put(
        tmp_path,
        "workshop-batches/full20-r1/latest-runs.json",
        {"at": "2026-09-19T03:00:01Z", "data": [row]},
    )
    put(tmp_path, "browser-evidence/a/workshop-runs.json", {"data": [row]})
    report = scan_workshop(tmp_path, NOW)
    assert report["summary"]["consultations"] == 1
    assert report["summary"]["completed_model_responses"] == 1
    assert report["summary"]["seeded_greetings_not_calls"] == 1
    assert report["summary"]["human_turns_not_calls"] == 1
    assert (
        report["summary"]["reported_retry_attempts_not_deduplicated_provider_calls"]
        == 1
    )
    assert report["summary"]["exact_configured_model_turn_count_completed"] == 0
    assert report["by_cohort"]["full20-r1"]["completed_model_responses"] == 1
    assert "PRIVATE_" not in json.dumps(report)


def test_judge_is_separate_and_failure_history_retained(tmp_path):
    row = run()
    row["status"] = "failed"
    put(tmp_path, "workshop-batches/a/admission.json", [row])
    row = copy.deepcopy(row)
    row["status"], row["version"] = "completed", 2
    row["state"]["config"]["max_turns"] = 1
    row["state"]["transcript"].append(complete("request-2", "patient"))
    row["state"]["judgment"] = {
        **complete("request-judge")["completion"],
        "judgment": {str(k): 3 for k in range(5)},
    }
    put(tmp_path, "workshop-batches/a/latest-runs.json", {"data": [row]})
    report = scan_workshop(tmp_path, NOW)
    assert report["summary"]["completed_model_responses"] == 3
    assert report["summary"]["responses_by_role"] == {
        "clinician": 1,
        "patient": 1,
        "judge": 1,
    }
    assert report["summary"]["judgments_with_five_finite_1_to_6_scores"] == 1
    assert report["summary"]["exact_configured_model_turn_count_completed"] == 1
    assert report["summary"]["failed_history_retained"] == 1


def test_future_snapshot_and_old_pilot_not_full20(tmp_path):
    row = run()
    put(tmp_path, "workshop-batches/full20-r1/admission.json", [row])
    old = copy.deepcopy(row)
    old["id"] = OTHER
    old["state"]["transcript"] = [complete("pilot-request")]
    put(tmp_path, "workshop-batches/full20-r1/prior-runs.json", {"data": [old]})
    row["state"]["transcript"].append(complete("future-request"))
    put(
        tmp_path,
        "workshop-batches/full20-r1/latest-runs.json",
        {"at": "2026-09-19T05:00:00Z", "data": [row]},
    )
    report = scan_workshop(tmp_path, NOW)
    assert report["summary"]["consultations"] == 2
    assert report["summary"]["completed_model_responses"] == 2
    assert report["by_cohort"]["full20-r1"]["consultations"] == 1
    assert report["by_cohort"]["full20-r1"]["completed_model_responses"] == 1


def test_missing_identity_and_invalid_scores_not_invented(tmp_path):
    row = run()
    del row["state"]["transcript"][1]["completion"]["telemetry"]["request_id"]
    row["state"]["judgment"] = {"judgment": {"x": float("nan")}}
    put(tmp_path, "workshop-batches/a/admission.json", [row])
    report = scan_workshop(tmp_path, NOW)
    assert report["summary"]["completed_model_responses"] == 0
    assert report["summary"]["unidentified_model_completions"] == 1
    assert report["summary"]["judgments_with_five_finite_1_to_6_scores"] == 0


def test_campaign_operation_denominator_unchanged(tmp_path):
    put(tmp_path, "workshop-batches/a/admission.json", [run()])
    report = scan(tmp_path, NOW)
    assert report["counts"]["durable_operation_ids"] == 0
    assert (
        report["separate_workshop_population"]["summary"]["completed_model_responses"]
        == 1
    )
    assert "MindEval consultations — separate population" in markdown(report)


def test_equivalent_json_number_types_do_not_fabricate_conflicts(tmp_path):
    row = run()
    put(tmp_path, "workshop-batches/a/admission.json", [row])
    row["state"]["transcript"][1]["completion"]["usage"]["total_tokens"] = 9.0
    put(tmp_path, "workshop-batches/a/latest-runs.json", {"data": [row]})
    report = scan_workshop(tmp_path, NOW)
    assert report["summary"]["completed_model_responses"] == 1
    assert report["issues"] == []


def test_conflicting_response_identity_kept_as_issue_not_second_call(tmp_path):
    row = run()
    put(tmp_path, "workshop-batches/a/admission.json", [row])
    row["state"]["transcript"][1]["completion"]["content"] = "DIFFERENT_PRIVATE_TEXT"
    put(tmp_path, "workshop-batches/a/latest-runs.json", {"data": [row]})
    report = scan_workshop(tmp_path, NOW)
    assert report["summary"]["completed_model_responses"] == 1
    assert report["issues"][0]["reason"] == "conflicting_completion_identity"
    assert "DIFFERENT_PRIVATE_TEXT" not in json.dumps(report)
