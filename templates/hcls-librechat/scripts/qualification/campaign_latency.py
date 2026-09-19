#!/usr/bin/env python3
"""Offline latency supplement for a deduplicated campaign aggregate.

No inference or platform requests. Timestamp spans are not GPU utilization.
Legacy cold_start_seconds means accepted-to-ready, not a thermal-state witness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from aggregate_campaign import current_runtimes, excluded, operation_documents, utc

PHASES = {
    "queue_before_activation": ("accepted_at", "activation_started_at"),
    "activation_worker_span": ("activation_started_at", "ready_at"),
    "ready_to_execution": ("ready_at", "started_at"),
    "execution_span": ("started_at", "completed_at"),
    "end_to_end": ("accepted_at", "completed_at"),
    "accepted_to_ready": ("accepted_at", "ready_at"),
    "pre_execution_wait": ("accepted_at", "started_at"),
}
PARTITION = (
    "queue_before_activation",
    "activation_worker_span",
    "ready_to_execution",
    "execution_span",
)
DIGEST = re.compile(r"sha256:[0-9a-f]{64}$")


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def duration(start, end):
    a, b = utc(start), utc(end)
    if a is None or b is None:
        return {"seconds": None, "reason": "missing_timestamp"}
    value = (b - a).total_seconds()
    if value < 0:
        return {
            "seconds": None,
            "reason": "negative_duration",
            "observed_delta_seconds": value,
        }
    return {"seconds": value, "reason": "observed_timestamp_span"}


def phases(operation):
    result = {
        name: duration(operation.get(a), operation.get(b))
        for name, (a, b) in PHASES.items()
    }
    # Never sum overlapping composite spans, or combine partial phases into a
    # fabricated total. A backwards boundary invalidates the phase partition.
    complete = all(result[key]["seconds"] is not None for key in PARTITION)
    total = result["end_to_end"]["seconds"]
    partition = sum(result[key]["seconds"] for key in PARTITION) if complete else None
    result["partition"] = {
        "complete_nonoverlapping": complete
        and total is not None
        and abs(partition - total) < 1e-5,
        "sum_seconds": partition,
        "scope": "four disjoint intervals only; composite accepted-to-ready/pre-execution spans overlap them",
    }
    return result


def overlap_seconds(intervals):
    """Return union and overlap explicitly, rejecting backwards observations."""
    parsed = []
    invalid = 0
    for start, end in intervals:
        a, b = utc(start), utc(end)
        if a is None or b is None or b < a:
            invalid += 1
        else:
            parsed.append((a.timestamp(), b.timestamp()))
    union = 0.0
    cursor = None
    for start, end in sorted(parsed):
        if cursor is None or start > cursor:
            union += end - start
        else:
            union += max(0, end - cursor)
        cursor = max(cursor or end, end)
    summed = sum(end - start for start, end in parsed)
    return {
        "union_seconds": union,
        "summed_seconds": summed,
        "overlap_seconds": summed - union,
        "invalid_intervals": invalid,
    }


def distribution(values, population):
    finite = sorted(
        value
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )
    return {
        "observed": len(finite),
        "unknown_or_invalid": population - len(finite),
        "min": finite[0] if finite else None,
        "median": statistics.median(finite) if finite else None,
        "p95_nearest_rank": finite[math.ceil(len(finite) * 0.95) - 1]
        if finite
        else None,
        "max": finite[-1] if finite else None,
    }


def pod_records(document):
    if not isinstance(document, dict):
        return []
    if document.get("metadata", {}).get("uid") and document.get("spec", {}).get(
        "containers"
    ):
        return [document]
    return [pod for item in document.get("items", []) for pod in pod_records(item)]


def pod_index(root):
    result = defaultdict(list)
    for path in root.rglob("*.json"):
        if excluded(path.relative_to(root)) or not (
            "pods" in path.name or path.name.endswith("pod.json")
        ):
            continue
        try:
            pods = pod_records(json.loads(path.read_bytes()))
        except (OSError, ValueError, AttributeError):
            continue
        if not pods:
            continue
        # The observer directory marks request start; the immutable file write
        # is a conservative upper bound for the actual Kubernetes observation.
        # Undated ad-hoc captures cannot bracket an operation.
        try:
            observed_after = datetime.strptime(
                path.parent.name, "%Y%m%dT%H%M%SZ"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        observed_before = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if observed_before < observed_after:
            continue
        source = ref(path)
        for pod in pods:
            metadata, spec, status = (
                pod.get(key, {}) for key in ("metadata", "spec", "status")
            )
            gpu = [
                container
                for container in spec.get("containers", [])
                if any(
                    key.endswith("/gpu") and str(value).isdigit() and int(value) > 0
                    for key, value in container.get("resources", {})
                    .get("limits", {})
                    .items()
                )
            ]
            if len(gpu) != 1:
                continue
            container = gpu[0]
            digest = str(container.get("image", "")).rsplit("@", 1)[-1]
            if not DIGEST.fullmatch(digest):
                continue
            ready = [
                condition.get("lastTransitionTime")
                for condition in status.get("conditions", [])
                if condition.get("type") == "Ready"
                and condition.get("status") == "True"
            ]
            runtime = next(
                (
                    item
                    for item in status.get("containerStatuses", [])
                    if item.get("name") == container["name"]
                ),
                {},
            )
            result[metadata["uid"]].append(
                {
                    "image_digest": digest,
                    "image_id": runtime.get("imageID"),
                    "container_id": runtime.get("containerID"),
                    "restart_count": runtime.get("restartCount"),
                    "observed_after": observed_after.isoformat(),
                    "observed_before": observed_before.isoformat(),
                    "created_at": metadata.get("creationTimestamp"),
                    "ready_at": ready[0] if len(ready) == 1 else None,
                    "container_started_at": runtime.get("state", {})
                    .get("running", {})
                    .get("startedAt"),
                    "source": source,
                }
            )
    return result


def bracketed_pods(operation, pods):
    """Require immutable container continuity around the entire execution."""
    started, completed = (
        utc(operation.get("started_at")),
        utc(operation.get("completed_at")),
    )
    if not started or not completed or completed < started:
        return [], "missing_execution_interval"
    matches = [
        item
        for item in pods.get(operation.get("runtime", {}).get("pod_uid"), [])
        if utc(item.get("container_started_at"))
        and utc(item["container_started_at"]) <= started
        and item.get("image_id")
        and item.get("container_id")
    ]
    before = [
        item
        for item in matches
        if utc(item.get("observed_before")) and utc(item["observed_before"]) <= started
    ]
    after = [
        item
        for item in matches
        if utc(item.get("observed_after")) and utc(item["observed_after"]) >= completed
    ]
    if not before or not after:
        return [], "unbracketed_pod_observation"
    first = max(before, key=lambda item: utc(item["observed_before"]))
    last = min(after, key=lambda item: utc(item["observed_after"]))
    # Include all intervening captures so a restart or in-place image mutation
    # cannot be hidden by choosing two convenient observations.
    span = [
        item
        for item in pods.get(operation["runtime"]["pod_uid"], [])
        if utc(item.get("observed_after"))
        and utc(item.get("observed_before"))
        and utc(item["observed_before"]) >= utc(first["observed_after"])
        and utc(item["observed_after"]) <= utc(last["observed_before"])
    ]
    identities = {
        (
            item.get("image_digest"),
            item.get("image_id"),
            item.get("container_id"),
            item.get("restart_count"),
            item.get("container_started_at"),
        )
        for item in span
    }
    if len(identities) != 1:
        return [], "conflicting_pod_container_observations"
    return span, "timestamp_bracketed_operation_pod_uid"


def native_identity(operation, pods):
    """Join immutable operation Pod UID; never select the newest deployment."""
    runtime = operation.get("runtime", {})
    explicit = runtime.get("runtime_image_digest", runtime.get("image_digest"))
    if isinstance(explicit, str) and DIGEST.fullmatch(explicit):
        return {"image_digest": explicit, "method": "operation_runtime", "sources": []}
    matches, method = bracketed_pods(operation, pods)
    digests = {item["image_digest"] for item in matches}
    actual = {
        str(item["image_id"]).rsplit("@", 1)[-1].removeprefix("containerd://")
        for item in matches
    }
    if digests and actual != digests:
        # An updated desired spec is not proof the running container changed.
        # Multi-platform index-to-manifest relationships need separate evidence.
        return {
            "image_digest": None,
            "method": "desired_actual_image_relationship_unverified",
            "actual_image_ids": sorted({item["image_id"] for item in matches}),
            "sources": list(
                {item["source"]["sha256"]: item["source"] for item in matches}.values()
            ),
        }
    if len(digests) == 1:
        return {
            "image_digest": next(iter(digests)),
            "method": method,
            "sources": list(
                {item["source"]["sha256"]: item["source"] for item in matches}.values()
            ),
        }
    return {
        "image_digest": None,
        "method": method,
        "sources": [],
    }


def thermal_state(operation, pods):
    matches, _ = bracketed_pods(operation, pods)
    if len({item["image_digest"] for item in matches}) != 1:
        return "unknown"
    ready = [utc(item["ready_at"]) for item in matches if utc(item.get("ready_at"))]
    started = [
        utc(item["container_started_at"])
        for item in matches
        if utc(item.get("container_started_at"))
    ]
    accepted, completed = (
        utc(operation.get("accepted_at")),
        utc(operation.get("completed_at")),
    )
    if (
        not accepted
        or not completed
        or len(ready) != len(matches)
        or not ready
        or not started
    ):
        return "unknown"
    # A late restart/readiness transition invalidates a warm inference from an
    # older capture. These are worker-state witnesses, not a storage-cache tier.
    if max(ready) <= accepted and max(started) <= accepted:
        return "ready_worker_before_acceptance"
    created = [
        utc(item["created_at"]) for item in matches if utc(item.get("created_at"))
    ]
    if created and min(created) >= accepted and max(ready) <= completed:
        return "new_worker_during_request"
    return "unknown"


def raw_operations(row, root, issues=None):
    result = []
    seen = set()
    for source in row["sources"]:
        path = root / source["path"]
        if path in seen or path.name == "receipt.json":
            continue
        seen.add(path)
        try:
            raw = path.read_bytes()
            actual = hashlib.sha256(raw).hexdigest()
            if source.get("sha256") and actual != source["sha256"]:
                if issues is not None:
                    issues.append(
                        {
                            "path": str(path),
                            "reason": "changed_since_aggregate",
                            "aggregate_sha256": source["sha256"],
                            "current_sha256": actual,
                        }
                    )
                continue
            document = json.loads(raw)
        except (OSError, ValueError):
            continue
        for operation in operation_documents(document):
            if operation.get("id") == row["operation_id"]:
                result.append((operation, source))
    return result


def stage_overlap(row, root):
    attempts = {}
    sources = {
        item["source"]["path"]: item["source"] for item in row.get("stage_attempts", [])
    }
    for name, source in sources.items():
        try:
            raw = (root / name).read_bytes()
            if (
                source.get("sha256")
                and hashlib.sha256(raw).hexdigest() != source["sha256"]
            ):
                continue
            document = json.loads(raw)
        except (OSError, ValueError):
            continue
        values = document.get("attempts", [])
        for stage in document.get("data", {}).get("stages", []):
            values += stage.get("attempts", [])
        for attempt in values:
            identity = attempt.get("attempt_id", attempt.get("id"))
            if identity and attempt.get("started_at") and attempt.get("completed_at"):
                attempts[identity] = (attempt["started_at"], attempt["completed_at"])
    return {
        "observed_attempts_with_intervals": len(attempts),
        **overlap_seconds(attempts.values()),
        "scope": "retained stage wall-clock intervals; overlaps retained, not added to parent latency or GPU hours",
    }


def summarize(rows):
    return {
        "operations": len(rows),
        "service_states": dict(Counter(row["service_state"] for row in rows)),
        "worker_state": dict(Counter(row["worker_state"] for row in rows)),
        "cause_groups": dict(Counter(row["cause_group"] for row in rows)),
        "timings_seconds": {
            phase: distribution(
                [row["phases"][phase]["seconds"] for row in rows], len(rows)
            )
            for phase in PHASES
        },
        "client_elapsed_seconds": distribution(
            [row["client_elapsed_seconds"] for row in rows], len(rows)
        ),
        "invalid_phase_rows": sum(
            any(row["phases"][key]["reason"] == "negative_duration" for key in PHASES)
            for row in rows
        ),
    }


def analyze(aggregate, root, baseline, pods, diagnoses=None):
    rows = []
    for row in aggregate["operations"]:
        changed_sources = []
        documents = raw_operations(row, root, changed_sources)
        # Use one coherent record, not timestamp fragments spliced across retries.
        documents.sort(
            key=lambda pair: (
                bool(pair[0].get("completed_at")),
                sum(
                    pair[0].get(key) is not None
                    for key in (
                        "accepted_at",
                        "activation_started_at",
                        "ready_at",
                        "started_at",
                    )
                ),
                pair[0].get("completed_at") or "",
            )
        )
        operation, source = documents[-1] if documents else ({}, None)
        identity = native_identity(operation, pods)
        explicit = row.get("runtime_image_digests", [])
        if identity["image_digest"] is None and len(explicit) == 1:
            identity = {
                "image_digest": explicit[0],
                "method": "retained_execution_identity",
                "sources": [],
            }
        expected = baseline.get("apps", {}).get(row["model_id"], {})
        identities = row.get("execution_identities", [])
        if identities and expected.get("execution_identity_sha256"):
            comparison = (
                "exact_latest_execution_identity"
                if identities == [expected["execution_identity_sha256"]]
                else "different_execution_identity"
            )
        elif identity["image_digest"] and expected.get("runtime_image_digest"):
            comparison = (
                "exact_latest_image_only"
                if identity["image_digest"] == expected["runtime_image_digest"]
                else "historical_or_different_image"
            )
        else:
            comparison = "unknown"
        clients = [receipt.get("elapsed_seconds") for receipt in row["receipts"]]
        clients = [
            value
            for value in clients
            if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
        ]
        diagnosis = (diagnoses or {}).get("operations", {}).get(row["operation_id"])
        rows.append(
            {
                "operation_id": row["operation_id"],
                "model_id": row["model_id"],
                "operation_kind": row["operation_kind"],
                "workflow": row["workflow"],
                "service_state": row["service_state"],
                "phases": phases(operation),
                "client_elapsed_seconds": max(clients) if clients else None,
                "worker_state": thermal_state(operation, pods),
                "runtime": identity,
                "reported_runtime": {
                    key: operation.get("runtime", {}).get(key)
                    for key in (
                        "pod_uid",
                        "node_uid",
                        "gpu_uuids",
                        "gpu_count",
                        "preemptible",
                    )
                },
                "runtime_comparison": comparison,
                "cause_group": diagnosis["cause_group"]
                if diagnosis
                else row["cause_classification"],
                "retained_structured_cause_group": row["cause_classification"],
                "separate_retained_diagnosis": diagnosis,
                "error_codes": row["error_codes"],
                "operation_record": source,
                "changed_sources_excluded": changed_sources,
                "stage_intervals": stage_overlap(row, root),
                "attempt": operation.get("attempt"),
                "legacy_cold_start_seconds_not_thermal_state": operation.get(
                    "cold_start_seconds"
                ),
            }
        )
    by_app = {}
    for model in sorted({row["model_id"] for row in rows}):
        selected = [row for row in rows if row["model_id"] == model]
        top = [
            row for row in selected if row["operation_kind"].startswith("top_level_")
        ]
        by_app[model] = {
            "top_level": summarize(top),
            "children": summarize(
                [
                    row
                    for row in selected
                    if not row["operation_kind"].startswith("top_level_")
                ]
            ),
            "by_runtime": {
                group: summarize(
                    [row for row in top if row["runtime_comparison"] == group]
                )
                for group in sorted({row["runtime_comparison"] for row in top})
            },
            "by_outcome": {
                group: summarize([row for row in top if row["service_state"] == group])
                for group in sorted({row["service_state"] for row in top})
            },
            "by_cause": {
                group: summarize([row for row in top if row["cause_group"] == group])
                for group in sorted({row["cause_group"] for row in top})
            },
            "by_operation_kind": {
                group: summarize([row for row in top if row["operation_kind"] == group])
                for group in sorted({row["operation_kind"] for row in top})
            },
            "by_worker_state": {
                group: summarize([row for row in top if row["worker_state"] == group])
                for group in sorted({row["worker_state"] for row in top})
            },
            "runtime_by_outcome": {
                group: {
                    outcome: summarize(
                        [
                            row
                            for row in top
                            if row["runtime_comparison"] == group
                            and row["service_state"] == outcome
                        ]
                    )
                    for outcome in sorted(
                        {
                            row["service_state"]
                            for row in top
                            if row["runtime_comparison"] == group
                        }
                    )
                }
                for group in sorted({row["runtime_comparison"] for row in top})
            },
        }
    return {
        "schema": "fs2.campaign-latency/v1",
        "as_of": aggregate["as_of"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "descriptive_evidence_not_readiness",
        "baseline": baseline.get("source"),
        "by_app": by_app,
        "operations": rows,
        "all_top_level": summarize(
            [row for row in rows if row["operation_kind"].startswith("top_level_")]
        ),
        "diagnosed_delays": [row for row in rows if row["separate_retained_diagnosis"]],
        "limitations": [
            "Latest means the explicitly supplied captured baseline, "
            "never the newest successful request or inferred image.",
            "Queue-before-activation is the operation-worker dispatch boundary; "
            "activation spans occur for hot requests too.",
            "Legacy cold_start_seconds is accepted-to-ready and includes queue/capacity; "
            "it is not model cold-start time.",
            "Worker state requires matching immutable Pod UID and timestamp-bracketing observations with "
            "the same container ID, image ID, restart count and readiness timestamps. "
            "Low traffic proves nothing.",
            "A new worker during a request is not an empty-node or uncached-weight benchmark. "
            "Warm worker is not a cache-tier claim.",
            "Started-to-completed includes the server execution/result path, not measured GPU-active time.",
            "For scientific batch, started-to-completed spans the orchestration plus all stages, "
            "Kueue waits, pulls and artifacts. Its short pre-execution wait is not the total GPU queue delay.",
            "Missing phases stay unknown. Negative durations are invalid, never clipped to zero; "
            "overlapping composites are not summed.",
            "Success and failure latencies are separated; distributions span varied input sizes "
            "and are not controlled speedup estimates.",
            "Generic upstream errors remain unknown causes; "
            "preemptible GPU placement alone does not establish preemption delay.",
            "Client elapsed includes receipt/poll/transport time. "
            "Scientific stage overlap is not added to parent wall-clock time.",
            "Operation/stage files changed since the aggregate hash are excluded, not silently reinterpreted. "
            "Rerun the aggregate to include later completions. Pod captures enrich exact-UID evidence independently. "
            "Observation-directory time and retained file mtime bound capture time; undated captures are not used.",
        ],
    }


def markdown(report):
    lines = [
        "# Customer wait and latency — retained evidence",
        "",
        f"Evidence as of {report['as_of']}. No new requests; no readiness verdict.",
        "",
        "Only top-level requests appear in this table. Child operations are separate in JSON. Values are seconds.",
        "",
        "| App | Requests | Completed timing n | End-to-end median / p95 / max | "
        "Queue-before-activation median (n) | Activation span median (n) | Execution median |",
        "|---|---:|---:|---|---|---|---:|",
    ]

    def number(value):
        return "unknown" if value is None else f"{value:.3f}"

    for model, group in report["by_app"].items():
        value = group["top_level"]
        phases_ = value["timings_seconds"]
        end = phases_["end_to_end"]
        lines.append(
            f"| {model} | {value['operations']} | {end['observed']} | "
            + " / ".join(
                number(end[key]) for key in ("median", "p95_nearest_rank", "max")
            )
            + f" | {number(phases_['queue_before_activation']['median'])} "
            + f"({phases_['queue_before_activation']['observed']})"
            + f" | {number(phases_['activation_worker_span']['median'])} "
            + f"({phases_['activation_worker_span']['observed']})"
            + f" | {number(phases_['execution_span']['median'])} |"
        )
    lines += [
        "",
        "The table includes terminal failures as experienced by customers; JSON additionally separates outcomes, "
        "exact latest-runtime evidence, different/historical identities and unknown identities. "
        "Use those strata before comparing runtimes. Queue/activation phase counts and missing values are in JSON.",
        "",
        "Worker-state evidence: `"
        + json.dumps(report["all_top_level"]["worker_state"], sort_keys=True)
        + "`.",
        "",
        "## Runtime-stratified terminal requests",
        "",
        "Compared only with the supplied dated baseline. Image-only is not full release identity. "
        "Inputs differ; failure timing is not evidence of faster inference. Unknown identities remain in JSON.",
        "",
        "| App | Identity evidence | Service outcome | Requests | End-to-end n / median / p95 |",
        "|---|---|---|---:|---|",
    ]
    for model, group in report["by_app"].items():
        for identity, outcomes in group["runtime_by_outcome"].items():
            if identity == "unknown":
                continue
            for outcome, values in outcomes.items():
                if outcome not in {
                    "succeeded",
                    "succeeded_receipt_only",
                    "failed",
                    "cancelled",
                }:
                    continue
                end = values["timings_seconds"]["end_to_end"]
                lines.append(
                    f"| {model} | {identity} | {outcome} | {values['operations']} | "
                    f"{end['observed']} / {number(end['median'])} / {number(end['p95_nearest_rank'])} |"
                )
    lines += [
        "",
        "## Interpretation",
        "",
    ] + ["- " + item for item in report["limitations"]]
    if report["diagnosed_delays"]:
        lines += ["", "## Explicitly diagnosed delays (not inferred from GPU type)", ""]
        for row in report["diagnosed_delays"]:
            lines.append(
                f"- {row['model_id']} `{row['operation_id']}`: "
                + row["separate_retained_diagnosis"]["summary"]
                + " End-to-end "
                + number(row["phases"]["end_to_end"]["seconds"])
                + "s; this total is not attributed wholly to capacity or software."
            )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnoses", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    if args.output.exists():
        parser.error("use a new output directory to preserve prior evidence")
    aggregate = json.loads(args.aggregate.read_bytes())
    root = Path(aggregate["evidence_root"])
    report = analyze(
        aggregate,
        root,
        current_runtimes(args.baseline),
        pod_index(root),
        json.loads(args.diagnoses.read_bytes()) if args.diagnoses else None,
    )
    if args.diagnoses:
        report["diagnosis_source"] = ref(args.diagnoses)
    report["aggregate_source"] = ref(args.aggregate)
    args.output.mkdir(parents=True, mode=0o700)
    (args.output / "latency.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (args.output / "LATENCY.md").write_text(markdown(report))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "top_level": report["all_top_level"]["operations"],
                "worker_state": report["all_top_level"]["worker_state"],
            }
        )
    )


if __name__ == "__main__":
    main()
