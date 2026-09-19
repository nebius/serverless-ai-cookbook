"""Count retained MindEval consultations/completions separately from GPU operations.

Read-only and payload-free output. A seeded greeting, human turn, poll or planned
round is never a model call. Provider retries are not uniquely identified calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from aggregate_campaign import identifier, stamp, utc


def number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def completion(value, role, run_id):
    if not isinstance(value, dict) or not value.get("model"):
        return None
    telemetry = value.get("telemetry") or {}
    request = telemetry.get("request_id") or value.get("provider_request_id")
    if not isinstance(request, str) or not request:
        return None
    usage = value.get("usage") or {}
    return {
        "request_identity": request,
        "provider_request_id": value.get("provider_request_id"),
        "run_id": run_id,
        "role": role,
        "model": value["model"],
        "provider_model": value.get("provider_model"),
        "finish_reason": value.get("finish_reason"),
        "reported_retries": telemetry.get("retries")
        if number(telemetry.get("retries"))
        else None,
        "latency_ms": telemetry.get("latency_ms")
        if number(telemetry.get("latency_ms"))
        else None,
        "queue_ms": telemetry.get("queue_ms")
        if number(telemetry.get("queue_ms"))
        else None,
        "usage": {
            k: usage[k]
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            if number(usage.get(k))
        },
        "completion_sha256": hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def summarize(run_ids, runs, calls):
    selected = [r for key, r in runs.items() if key in run_ids]
    observed = [c for c in calls.values() if c["run_id"] in run_ids]
    return {
        "consultations": len(selected),
        "consultation_states": dict(Counter(r["status"] for r in selected)),
        "completed_model_responses": len(observed),
        "responses_by_role": dict(Counter(c["role"] for c in observed)),
        "responses_by_model": dict(Counter(c["model"] for c in observed)),
        "reported_retry_attempts_not_deduplicated_provider_calls": sum(
            c["reported_retries"] or 0 for c in observed
        ),
        "seeded_greetings_not_calls": sum(r["seed_turns"] for r in selected),
        "human_turns_not_calls": sum(r["human_turns"] for r in selected),
        "unidentified_model_completions": sum(
            r["unidentified_completions"] for r in selected
        ),
        "judgments_with_five_finite_1_to_6_scores": sum(
            r["valid_judgment_shape"] for r in selected
        ),
        "exact_configured_model_turn_count_completed": sum(
            r["exact_model_turn_count_completed"] for r in selected
        ),
        "failed_history_retained": sum(
            "failed" in r["status_history"] for r in selected
        ),
        "token_usage_observed": {
            k: sum(c["usage"].get(k, 0) for c in observed)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
        "token_usage_missing_responses": sum(not c["usage"] for c in observed),
    }


def scan_workshop(root, as_of):
    paths = set(root.glob("browser-evidence/**/workshop-runs.json"))
    for name in ("admission.json", "latest-runs.json", "prior-runs.json"):
        paths.update(root.glob("workshop-batches/*/" + name))
    runs, calls, cohorts, sources, issues = {}, {}, defaultdict(set), [], []
    completion_values = {}
    histories = defaultdict(set)
    for path in sorted(paths):
        try:
            raw = path.read_bytes()
            doc = json.loads(raw)
        except (OSError, ValueError) as exc:
            issues.append(
                {"path": str(path.relative_to(root)), "reason": type(exc).__name__}
            )
            continue
        observed = utc(doc.get("at")) if isinstance(doc, dict) else None
        if observed and observed > as_of:
            continue
        rows = doc.get("data", []) if isinstance(doc, dict) else doc
        if not isinstance(rows, list):
            continue
        source = {
            "path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        sources.append(source)
        for row in rows:
            if (
                not isinstance(row, dict)
                or not identifier(row.get("id"))
                or not isinstance(row.get("state"), dict)
            ):
                continue
            run_id, state = row["id"], row["state"]
            updated = utc(row.get("updated_at"))
            if updated and updated > as_of:
                continue
            if "config" not in state or not isinstance(state.get("transcript"), list):
                continue
            if (
                path.parent.parent.name == "workshop-batches"
                and path.name == "admission.json"
            ):
                cohorts[path.parent.name].add(run_id)
            histories[run_id].add(row.get("status", "unknown"))
            generated_ids, seed, human, unknown = set(), 0, 0, 0
            for turn in state["transcript"]:
                if turn.get("seed"):
                    seed += 1
                    continue
                if turn.get("human") or turn.get("source") == "human":
                    human += 1
                    continue
                at = utc(turn.get("at"))
                if at and at > as_of:
                    continue
                value = completion(
                    turn.get("completion"), turn.get("role", "unknown"), run_id
                )
                if value:
                    key = value["request_identity"]
                    generated_ids.add(key)
                    if (
                        key in completion_values
                        and completion_values[key] != turn["completion"]
                    ):
                        issues.append(
                            {
                                "run_id": run_id,
                                "reason": "conflicting_completion_identity",
                                "source": source,
                            }
                        )
                    else:
                        calls[key] = value
                        completion_values[key] = turn["completion"]
                elif turn.get("source") == "model" or turn.get("completion"):
                    unknown += 1
            judge = state.get("judgment") or {}
            judged = completion(judge, "judge", run_id)
            if judged:
                key = judged["request_identity"]
                if key in completion_values and completion_values[key] != judge:
                    issues.append(
                        {
                            "run_id": run_id,
                            "reason": "conflicting_judge_identity",
                            "source": source,
                        }
                    )
                else:
                    calls[key] = judged
                    completion_values[key] = judge
            scores = judge.get("judgment", {}) if isinstance(judge, dict) else {}
            rounds = state["config"].get("max_turns")
            rank = (updated.timestamp() if updated else 0, row.get("version", 0))
            if run_id not in runs or rank > runs[run_id]["_rank"]:
                runs[run_id] = {
                    "run_id": run_id,
                    "batch_id": row.get("batch_id"),
                    "status": row.get("status", "unknown"),
                    "updated_at": stamp(updated),
                    "created_at": row.get("created_at"),
                    "profile_id": state["config"].get("profile_id"),
                    "mode": state["config"].get("mode"),
                    "clinician_model": state["config"].get("clinician_model"),
                    "patient_model": state["config"].get("patient_model"),
                    "judge_model": (state.get("registration") or {}).get("judge_model"),
                    "configured_rounds_not_observed_calls": rounds,
                    "identified_generated_turns": len(generated_ids),
                    "seed_turns": seed,
                    "human_turns": human,
                    "unidentified_completions": unknown,
                    "intervened": bool(state.get("intervened")),
                    "valid_judgment_shape": isinstance(scores, dict)
                    and len(scores) == 5
                    and all(number(v) and 1 <= v <= 6 for v in scores.values()),
                    "exact_model_turn_count_completed": isinstance(rounds, int)
                    and rounds > 0
                    and len(generated_ids) == 2 * rounds,
                    "source": source,
                    "_rank": rank,
                }
    for run_id, row in runs.items():
        row.pop("_rank")
        row["status_history"] = sorted(histories[run_id])
    return {
        "schema": "fs2.mindeval-retained-population/v1",
        "as_of": stamp(as_of),
        "summary": summarize(set(runs), runs, calls),
        "by_cohort": {
            key: summarize(ids, runs, calls) for key, ids in sorted(cohorts.items())
        },
        "consultations": sorted(runs.values(), key=lambda r: r["run_id"]),
        "model_responses": sorted(calls.values(), key=lambda r: r["request_identity"]),
        "sources": sources,
        "issues": issues,
        "scope": "Separate Token Factory consultation population; "
        "never added to serving/scientific operation or GPU-hour denominators.",
        "limitations": [
            "Only retained successful completion objects with request identity are counted; "
            "failed or interrupted calls without receipts remain unknown.",
            "Retries are reported separately; attempt IDs are unavailable, "
            "so total provider API calls are not reconstructed.",
            "Seed greetings, human turns, polls and configured/planned rounds are not calls. "
            "Model responses are deduplicated across captures.",
            "Five finite scores is a shape check, not independent clinician validation or calibrated judge accuracy.",
            "No transcript, hidden profile, completion content, reasoning, "
            "credentials or signed URL is included in this report.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--as-of", default=stamp(datetime.now(timezone.utc)))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    as_of = utc(args.as_of)
    if as_of is None or args.output.exists():
        parser.error("valid timestamp and new output directory required")
    report = scan_workshop(args.root, as_of)
    os.umask(0o077)
    args.output.mkdir(parents=True, mode=0o700)
    (args.output / "workshop.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {key: report[key] for key in ("as_of", "summary", "by_cohort", "issues")}
        )
    )


if __name__ == "__main__":
    main()
