"""Offline, transcript-free descriptive summary of one frozen MindEval cohort."""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
import hashlib
import json
from pathlib import Path
from statistics import mean, median

from aggregate_campaign import stamp, utc
from aggregate_workshop import completion, number, summarize
from manage_campaign import save
from run_workshop_batch import AXES, state_of, validate_admission, verify_report


def describe(values):
    values = sorted(values)
    return (
        {
            "n": len(values),
            "min": min(values),
            "median": median(values),
            "mean": mean(values),
            "max": max(values),
        }
        if values
        else {"n": 0}
    )


def analyze(frozen, admission, latest, reports):
    request = frozen["request"]
    validate_admission(admission, request)
    validate_admission(latest["data"], request)
    expected_ids = {row["id"] for row in admission}
    if {row["id"] for row in latest["data"]} != expected_ids:
        raise ValueError("latest run IDs differ from admitted cohort")
    identities = {
        row["id"]: (
            state_of(row)["config"]["profile_id"],
            state_of(row)["config"]["clinician_model"],
        )
        for row in admission
    }
    runs, calls, original_calls, issues = {}, {}, {}, []
    for row in latest["data"]:
        state = state_of(row)
        generated, seed, human, unknown = set(), 0, 0, 0
        for turn in state["transcript"] + [
            {"role": "judge", "completion": state.get("judgment")}
        ]:
            if turn.get("seed"):
                seed += 1
                continue
            if turn.get("human") or turn.get("source") == "human":
                human += 1
                continue
            raw = turn.get("completion")
            value = completion(raw, turn.get("role", "unknown"), row["id"])
            if not value:
                unknown += bool(raw or turn.get("source") == "model")
                continue
            key = value["request_identity"]
            if key in original_calls and original_calls[key] != raw:
                raise ValueError("conflicting completion identity")
            if key in calls and calls[key]["run_id"] != row["id"]:
                raise ValueError("completion identity reused across consultations")
            original_calls[key], calls[key] = raw, value
            if turn["role"] != "judge":
                generated.add(key)
        scores = (state.get("judgment") or {}).get("judgment", {})
        runs[row["id"]] = {
            "status": row["status"],
            "seed_turns": seed,
            "human_turns": human,
            "unidentified_completions": unknown,
            "valid_judgment_shape": set(scores) == AXES
            and all(number(v) and 1 <= v <= 6 for v in scores.values()),
            "exact_model_turn_count_completed": len(generated)
            == 2 * request["max_turns"],
            "status_history": [row["status"]],
        }
    matrix, checks = {}, []
    for run_id, body in sorted(reports.items()):
        if run_id not in expected_ids or body["run"]["id"] != run_id:
            raise ValueError("report outside exact admitted population")
        state = state_of(body["run"])
        pair = (state["config"]["profile_id"], state["config"]["clinician_model"])
        if pair != identities[run_id] or any(
            state["config"].get(k) != v for k, v in request.items()
        ):
            raise ValueError("report configuration differs from admission")
        check = verify_report(body, request)
        checks.append(
            {
                "run_id": run_id,
                "profile_id": pair[0],
                "clinician_model": pair[1],
                "status": check["status"],
                "checks": check["checks"],
                "structural_workflow_pass": check["structural_workflow_pass"],
            }
        )
        if check["structural_workflow_pass"]:
            matrix[pair] = state["judgment"]["judgment"]
        else:
            issues.append(
                {
                    "run_id": run_id,
                    "failed_checks": [k for k, v in check["checks"].items() if not v],
                }
            )
    complete = len(matrix) == len(expected_ids) and all(
        r["status"] == "completed" for r in runs.values()
    )
    means, paired = {}, []
    if complete:
        for model in request["clinician_models"]:
            means[model] = {
                axis: mean(matrix[(p, model)][axis] for p in request["profile_ids"])
                for axis in sorted(AXES)
            }
        for a, b in combinations(request["clinician_models"], 2):
            for profile in request["profile_ids"]:
                paired.append(
                    {
                        "profile_id": profile,
                        "model_a": a,
                        "model_b": b,
                        "difference_a_minus_b": {
                            axis: matrix[(profile, a)][axis]
                            - matrix[(profile, b)][axis]
                            for axis in sorted(AXES)
                        },
                    }
                )
    by_model = {}
    for model in request["clinician_models"]:
        ids = {key for key, (_, m) in identities.items() if m == model}
        by_model[model] = summarize(ids, runs, calls)
        by_model[model]["retained_reports"] = sum(
            c["clinician_model"] == model for c in checks
        )
        by_model[model]["validated_reports"] = sum(
            c["clinician_model"] == model and c["structural_workflow_pass"]
            for c in checks
        )
    telemetry = {}
    for role in ("clinician", "patient", "judge"):
        selected = [v for v in calls.values() if v["role"] == role]
        telemetry[role] = {
            "responses": len(selected),
            "latency_ms": describe(
                [v["latency_ms"] for v in selected if v["latency_ms"] is not None]
            ),
            "queue_ms": describe(
                [v["queue_ms"] for v in selected if v["queue_ms"] is not None]
            ),
            "reported_retries": sum(v["reported_retries"] or 0 for v in selected),
            "missing_retry_telemetry": sum(
                v["reported_retries"] is None for v in selected
            ),
            "finish_reasons": dict(Counter(v["finish_reason"] for v in selected)),
            "usage": {
                k: {
                    "observed_total": sum(v["usage"].get(k, 0) for v in selected),
                    "missing_responses": sum(k not in v["usage"] for v in selected),
                }
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
        }
    generated_times = [
        utc(t.get("at"))
        for row in latest["data"]
        for t in state_of(row)["transcript"]
        if not t.get("seed") and t.get("completion")
    ]
    generated_times = [t for t in generated_times if t is not None]
    completed_rows = [r for r in latest["data"] if r["status"] == "completed"]
    wall_times = [
        (utc(r["updated_at"]) - utc(r["created_at"])).total_seconds()
        for r in completed_rows
        if utc(r.get("created_at")) is not None and utc(r.get("updated_at")) is not None
    ]
    return {
        "schema": "mindeval-cohort-descriptive-summary/v1",
        "cohort": frozen["cohort"],
        "as_of": latest.get("at"),
        "frozen_at": frozen.get("at"),
        "profiles": request["profile_ids"],
        "clinician_models": request["clinician_models"],
        "patient_model": request["patient_model"],
        "judge_model": frozen["judge"],
        "rounds": request["max_turns"],
        "upstream_revision": frozen.get("provenance", {}).get("revision"),
        "population": summarize(expected_ids, runs, calls),
        "by_clinician": by_model,
        "report_coverage": {
            "expected": len(expected_ids),
            "retained": len(reports),
            "validated": len(matrix),
            "complete_matrix": complete,
        },
        "report_checks": checks,
        "telemetry_by_role": telemetry,
        "timing": {
            "first_generated_turn_at": stamp(min(generated_times))
            if generated_times
            else None,
            "last_conversation_turn_at": stamp(max(generated_times))
            if generated_times
            else None,
            "completed_consultation_wall_seconds_including_queue": describe(wall_times),
            "boundary": "Turn timestamps are retained response events; per-run wall time includes waiting and judging, not GPU compute.",
        },
        "descriptive_axis_means": means,
        "paired_profile_axis_differences": paired,
        "issues": issues,
        "limits": [
            "One stochastic consultation per profile/model; five correlated axes are not independent replicates.",
            "Gemma judge is an uncalibrated pilot; no clinical quality, significance or winner claim.",
            "Patient responses diverge across clinicians even with fixed patient model/profile.",
            "Provider retries lack unique attempt IDs; latency/queue/token telemetry is not GPU occupancy or billing.",
            "Counts reuse aggregate_workshop semantics; seeded greetings are not model responses.",
            "No transcript, private profile, reasoning or credential is emitted; failed historical cohorts remain separate.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refuse to overwrite an existing checkpoint")
    hashes = {}

    def read(path):
        raw = path.read_bytes()
        hashes[str(path.relative_to(args.cohort))] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    frozen, admission, latest = (
        read(args.cohort / name)
        for name in ("frozen.json", "admission.json", "latest-runs.json")
    )
    reports = {}
    for row in latest["data"]:
        path = args.cohort / "runs" / row["id"] / "report.json"
        if path.exists():
            body = read(path)
            if body["run"]["updated_at"] <= row["updated_at"]:
                reports[row["id"]] = body
    result = analyze(frozen, admission, latest, reports)
    result["source_sha256"] = hashes
    save(args.output, result)
    print(
        json.dumps(
            {k: result[k] for k in ("as_of", "population", "report_coverage", "issues")}
        )
    )


if __name__ == "__main__":
    main()
