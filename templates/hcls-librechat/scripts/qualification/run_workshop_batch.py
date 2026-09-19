#!/usr/bin/env python3
"""Observe a frozen public workshop batch through the scientist's ordinary key.

This is durable API/batching evidence, not a natural LibreChat or clinical test.
No provider bypass, worker-limit change, hidden restart, or failure replacement.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

import httpx

from manage_campaign import now, save

ORIGIN = "https://89.169.99.188"
TERMINAL = {"completed", "failed", "aborted"}
AXES = {
    "Assessment & Response",
    "Clinical Accuracy & Competence",
    "Ethical & Professional Conduct",
    "AI-Specific Communication Quality",
    "Therapeutic Relationship & Alliance",
}
PATIENT = "Qwen/Qwen3-30B-A3B-Instruct-2507"
CLINICIANS = [
    "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "openai/gpt-oss-120b",
    "zai-org/GLM-5.1",
]


def state_of(row):
    state = row["state"]
    return json.loads(state) if isinstance(state, str) else state


def request_for(catalog):
    eligible = {m["id"] for m in catalog["catalog"]["data"] if m["clinician_eligible"]}
    available = {m["id"] for m in catalog["catalog"]["data"]}
    if not set(CLINICIANS).issubset(eligible) or PATIENT not in available:
        raise ValueError("Frozen comparison model is not currently available/eligible")
    profiles = sorted(p["id"] for p in catalog["profiles"]["data"])[:20]
    if len(profiles) != 20 or len(set(profiles)) != 20:
        raise ValueError("Expected twenty distinct upstream profiles")
    if catalog["catalog"]["judge_model"] != "google/gemma-3-27b-it":
        raise ValueError("The calibrated judge changed; review before comparison")
    return {
        "profile_ids": profiles,
        "patient_model": PATIENT,
        "clinician_models": list(CLINICIANS),
        "mode": "canonical",
        "max_turns": 10,
        "temperature": 0.7,
        "max_completion_tokens": 4096,
        "language": "en",
        "patient_voice": "Sofia",
        "clinician_voice": "Jason",
    }


def validate_admission(rows, request):
    expected = {
        (p, m) for p in request["profile_ids"] for m in request["clinician_models"]
    }
    actual = [
        (state_of(r)["config"]["profile_id"], state_of(r)["config"]["clinician_model"])
        for r in rows
    ]
    if (
        len(rows) != len(expected)
        or set(actual) != expected
        or len({r["id"] for r in rows}) != len(rows)
    ):
        raise ValueError("Durable admission does not match the frozen study matrix")
    for row in rows:
        state = state_of(row)
        if state["worker_limit"] != 1:
            raise ValueError("Expected the scientist's existing one-worker policy")
        if any(state["config"].get(k) != v for k, v in request.items()):
            raise ValueError("Admitted configuration differs from the frozen request")


def verify_report(body, request):
    row = body["run"]
    state = state_of(row)
    turns = state.get("transcript", [])
    checks = {}
    checks["service_completed"] = row["status"] == "completed"
    checks["full_transcript"] = len(turns) == 1 + 2 * request["max_turns"]
    checks["roles_ordered"] = [t.get("role") for t in turns] == ["patient"] + [
        "clinician",
        "patient",
    ] * request["max_turns"]
    checks["nonempty_turns"] = bool(turns) and all(
        isinstance(t.get("content"), str) and t["content"].strip() for t in turns
    )
    checks["no_truncated_turn"] = all(
        t.get("completion", {}).get("finish_reason") != "length" for t in turns
    )
    judge = state.get("judgment") or {}
    scores = judge.get("judgment") or {}
    checks["five_valid_criteria"] = set(scores) == AXES and all(
        not isinstance(v, bool)
        and isinstance(v, (int, float))
        and math.isfinite(v)
        and 1 <= v <= 6
        for v in scores.values()
    )
    checks["fixed_judge"] = judge.get("model") == "google/gemma-3-27b-it"
    checks["judge_not_truncated"] = judge.get("finish_reason") != "length"
    checks["no_intervention"] = not state.get("intervened", False)
    checks["turn_events_complete"] = (
        sum(e["kind"] == "turn.completed" for e in body["events"])
        == 2 * request["max_turns"]
    )
    return {
        "run_id": row["id"],
        "status": row["status"],
        "checks": checks,
        "structural_workflow_pass": all(checks.values()),
        "clinical_validation": False,
        "natural_librechat_acceptance": False,
        "turn_count": len(turns),
        "error": state.get("error"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientists", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scientist", default="scientist-09")
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--deadline", default="2026-09-19T06:04:00+00:00")
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    person = next(
        p
        for p in json.loads(args.scientists.read_text())["scientists"]
        if p["id"] == args.scientist
    )
    deadline = datetime.fromisoformat(args.deadline).astimezone(timezone.utc)
    if datetime.now(timezone.utc) >= deadline:
        raise ValueError("Review deadline passed; do not admit a new batch")
    with httpx.Client(
        base_url=ORIGIN,
        timeout=30,
        trust_env=False,
        headers={"Authorization": "Bearer " + person["api_key"]},
    ) as client:
        frozen = args.output / "frozen.json"
        if frozen.exists():
            manifest = json.loads(frozen.read_text())
            if (
                manifest["scientist"] != args.scientist
                or manifest["cohort"] != args.cohort
            ):
                raise ValueError("Existing cohort ownership differs")
        else:
            response = client.get("/v1/workshop/catalog")
            response.raise_for_status()
            catalog = response.json()
            save(args.output / "catalog.json", catalog)
            request = request_for(catalog)
            if catalog["limits"]["workers_per_team"] != 1:
                raise ValueError("Existing policy is not one worker")
            response = client.get("/v1/workshop/runs")
            response.raise_for_status()
            prior = response.json()
            save(args.output / "prior-runs.json", prior)
            if any(r["status"] not in TERMINAL for r in prior["data"]):
                raise ValueError("Scientist has unfinished workshop work")
            manifest = {
                "at": now(),
                "scientist": args.scientist,
                "cohort": args.cohort,
                "request": request,
                "origin": ORIGIN,
                "idempotency_key": args.cohort
                + "-"
                + hashlib.sha256(
                    json.dumps(request, sort_keys=True).encode()
                ).hexdigest()[:20],
                "profile_selection": "First twenty IDs from the pinned public MindEval catalog; not representative clinical sampling",
                "judge": catalog["catalog"]["judge_model"],
                "provenance": catalog["catalog"]["provenance"],
            }
            save(frozen, manifest)
        admission = args.output / "admission.json"
        if not admission.exists():
            response = client.post(
                "/v1/workshop/runs",
                json=manifest["request"],
                headers={"Idempotency-Key": manifest["idempotency_key"]},
            )
            save(
                args.output / "admission-http.json",
                {"at": now(), "status": response.status_code, "body": response.json()},
            )
            response.raise_for_status()
            rows = response.json()["data"]
            validate_admission(rows, manifest["request"])
            save(admission, rows)
        rows = json.loads(admission.read_text())
        validate_admission(rows, manifest["request"])
        ids = {row["id"] for row in rows}
        print(
            json.dumps(
                {"admitted_runs": len(ids), "worker_limit": 1, "cohort": args.cohort}
            ),
            flush=True,
        )
        previous = None
        counts = {}
        while datetime.now(timezone.utc) < deadline:
            response = client.get("/v1/workshop/runs")
            response.raise_for_status()
            selected = [r for r in response.json()["data"] if r["id"] in ids]
            if {r["id"] for r in selected} != ids:
                raise ValueError("An admitted run is missing from customer history")
            save(args.output / "latest-runs.json", {"at": now(), "data": selected})
            counts = dict(Counter(r["status"] for r in selected))
            observation = {
                "at": now(),
                "statuses": counts,
                "transcript_turns": sum(
                    len(state_of(r).get("transcript", [])) for r in selected
                ),
            }
            with (args.output / "progress.jsonl").open("a") as stream:
                stream.write(json.dumps(observation) + "\n")
            for row in selected:
                folder = args.output / "runs" / row["id"]
                if (
                    row["status"] not in TERMINAL
                    or (folder / "verification.json").exists()
                ):
                    continue
                response = client.get("/v1/workshop/runs/" + row["id"] + "/report")
                response.raise_for_status()
                body = response.json()
                save(folder / "report.json", body)
                save(
                    folder / "verification.json",
                    verify_report(body, manifest["request"]),
                )
            if counts != previous:
                print(json.dumps(observation), flush=True)
                previous = counts
            if all(r["status"] in TERMINAL for r in selected):
                break
            time.sleep(15)
        save(
            args.output / "summary.json",
            {
                "at": now(),
                "statuses": counts,
                "admitted": len(ids),
                "deadline": args.deadline,
                "verifications": [
                    json.loads(p.read_text())
                    for p in sorted((args.output / "runs").glob("*/verification.json"))
                ],
            },
        )


if __name__ == "__main__":
    main()
