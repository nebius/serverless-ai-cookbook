#!/usr/bin/env python3
"""Read retained campaign evidence; never submit, poll, or change a platform.

Admission receipts anchor the population. UUIDs are deduplicated globally, not by
filename or cohort. Evaluator verdicts and offline reassessments are observations
of those operations, never additional calls. Output deliberately omits payloads,
credentials, signed URLs and free-form exception text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

TERMINAL = {"succeeded", "failed", "cancelled", "expired", "preempted"}
STATES = TERMINAL | {"queued", "activating", "running", "loading", "pending", "accepted", "admitted"}
CAPACITY_CODES = {
    "preempted",
    "capacity_unavailable",
    "capacity_exhausted",
    "insufficient_capacity",
    "node_preempted",
    "workload_preempted",
}
SAFE_FILES = {
    "operation.json",
    "final-status.json",
    "status.json",
    "admin-final.json",
    "result-envelope.json",
    "children.json",
    "submission.json",
}
WORKFLOWS = {
    "protein_structure": "structure prediction",
    "protein_complex": "complex prediction",
    "backbone_recovery": "design-to-refold recovery",
    "design_constraints": "protein design",
    "design_protocol": "protein design",
    "protein_sequence_design": "inverse folding",
    "docking_pose": "molecular docking",
    "molecule_generation": "molecule generation",
    "scalar_predictions": "aging biomarkers",
    "msa_alignment": "MSA search",
    "ct_segmentation": "medical imaging",
    "cxr_findings": "medical imaging",
    "speech_transcription": "speech transcription",
    "dna_continuation": "genomics",
    "generated_image": "image generation",
    "chat_json": "structured LLM extraction",
    "chat_tool_call": "LLM tool calling",
}
APP_WORKFLOWS = {
    **dict.fromkeys(
        (
            "boltz2",
            "openfold2",
            "openfold3",
            "esmfold2",
            "esmfold2-fast",
            "protenix-v2",
            "openfold3-openbind",
            "alphafold3",
        ),
        "structure prediction (mode unobserved)",
    ),
    **dict.fromkeys(
        ("proteina-complexa", "boltzgen", "mosaic", "bindcraft", "rfdiffusion"),
        "protein design",
    ),
    **dict.fromkeys(("genmol", "molmim"), "molecule generation"),
    **dict.fromkeys(("altumage", "phenoage"), "aging biomarkers"),
    "diffdock": "molecular docking",
    "proteinmpnn": "inverse folding",
    "evo2-40b": "genomics",
    "cosmos3-nano": "generative video/image",
    "cosmos3-lerobot-augmentation": "robotic dataset augmentation",
}
METRICS = {
    "design_count",
    "coordinate_artifact_count",
    "unique_structure_count",
    "generated_geometry_pass_count",
    "self_refolded_geometry_pass_count",
    "returned_molecules",
    "requested_molecules",
    "samples_returned",
    "generated_bases",
    "unique_sequences",
    "alignment_rows",
    "max_reference_error",
    "top1_within_2_angstrom",
    "topN_within_2_angstrom",
    "best_heavy_atom_rmsd_angstrom",
    "scientific_checks_pass",
    "full_duration",
}
NUMERIC_QUALITY = {
    "ca_rmsd_angstrom",
    "ca_lddt_15A",
    "tm_score_kabsch",
    "gdt_ts_kabsch",
    "independent_binder_ca_rmsd_angstrom",
    "ca_lddt_raw_vs_refolded",
    "heavy_atom_rmsd_angstrom",
    "best_heavy_atom_rmsd_angstrom",
    "dice",
    "iou",
    "wer",
    "weak_label_precision",
    "weak_label_recall",
    "max_reference_error",
    "reference_coverage",
    "input_coverage",
}


def utc(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def stamp(value):
    return value.isoformat().replace("+00:00", "Z") if value else None


def identifier(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def read(path):
    return json.loads(path.read_bytes())


def evidence(path, root):
    return {
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def excluded(path):
    return any(
        part.startswith("test_")
        or "-tests" in part
        or "contract-tests" in part
        or "isolated" in part
        or part == "campaign-reports"
        for part in path.parts
    )


def operation_documents(doc):
    """Only recognized operation envelopes, not arbitrary nested IDs/results."""
    if not isinstance(doc, dict):
        return []
    if (
        identifier(doc.get("id"))
        and doc.get("model_id")
        and doc.get("status") in STATES
    ):
        return [doc]
    result = []
    if doc.get("http_status") == 200 and isinstance(doc.get("body"), dict):
        result.extend(operation_documents(doc["body"]))
    if isinstance(doc.get("operation"), dict):
        result.extend(operation_documents(doc["operation"]))
    for child in (
        doc.get("children", []) if isinstance(doc.get("children"), list) else []
    ):
        result.extend(operation_documents(child))
    data = doc.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("operation"), dict):
        result.extend(operation_documents(data["operation"]))
    run = data.get("run", {}) if isinstance(data, dict) else {}
    if identifier(run.get("id")) and isinstance(run.get("model"), dict):
        result.append(
            {
                **run,
                "model_id": run["model"].get("model_id"),
                "protocol": "scientific-batch-v1",
                "accepted_at": run.get("submitted_at"),
                "execution_identity": run["model"].get("backend", {}),
            }
        )
    if identifier(doc.get("operation_id")) and doc.get("terminal_status") in TERMINAL:
        identity = doc.get("execution_identity", {})
        result.append(
            {
                "id": doc["operation_id"],
                "model_id": identity.get("model_id"),
                "status": doc["terminal_status"],
                "protocol": "scientific-batch-v1",
                "accepted_at": doc.get("submitted_at"),
                "completed_at": doc.get("completed_at"),
                "execution_identity": identity,
            }
        )
    return result


def stage_attempts(doc):
    if not isinstance(doc, dict):
        return []
    stages = doc.get("batch", {}).get("stages", [])
    if not stages:
        stages = doc.get("data", {}).get("stages", [])
    result = []
    for stage in stages:
        for attempt in stage.get("attempts", []):
            aid = attempt.get("attempt_id") or attempt.get("id")
            if not identifier(aid):
                continue
            result.append(
                {
                    "attempt_id": aid,
                    "stage": stage.get("stage_id", stage.get("id")),
                    "status": attempt.get("outcome", attempt.get("status", "unknown")),
                    "resource_class": stage.get("resource_class", "unknown"),
                    "failure_code": attempt.get("failure_code"),
                }
            )
    # Public scientific results expose attempts without the status envelope.
    if doc.get("schema", "").endswith("scientific-run-result/v1"):
        for attempt in doc.get("attempts", []):
            aid = attempt.get("attempt_id")
            if identifier(aid):
                result.append(
                    {
                        "attempt_id": aid,
                        "stage": attempt.get("stage_id"),
                        "status": attempt.get(
                            "outcome", attempt.get("status", "unknown")
                        ),
                        "resource_class": "gpu"
                        if attempt.get("gpu_uuids")
                        else "unknown",
                        "failure_code": attempt.get("failure_code"),
                    }
                )
    return result


def observed_time(doc):
    for key in (
        "reevaluated_at",
        "finished_at",
        "updated_at",
        "updated_unix_seconds",
        "completed_at",
        "admitted_at",
        "submitted_unix_seconds",
        "started_at",
        "started_unix",
    ):
        if (value := utc(doc.get(key))) is not None:
            return value
    return None


def evaluation_summary(doc, source):
    if not isinstance(doc, dict):
        return None
    verdict = doc.get("service_semantic_pass", doc.get("service_integrity_pass"))
    if not isinstance(verdict, bool):
        return None
    name = source["path"].rsplit("/", 1)[-1]
    historical = "-before-" in name or "original" in name
    reassessed = any(word in name for word in ("reassess", "reeval"))
    metrics = {
        key: value
        for key, value in doc.items()
        if key in METRICS and isinstance(value, (int, float, bool))
    }
    for key in ("predictions", "sequences", "molecules", "samples"):
        if isinstance(doc.get(key), list):
            metrics[key + "_count"] = len(doc[key])
    return {
        "evaluator": doc.get("evaluator", "unspecified"),
        "pass": verdict,
        "kind": "historical"
        if historical
        else "reassessment"
        if reassessed
        else "retained",
        "paper_reproduction": doc.get("paper_reproduction", "not_established"),
        "metrics": metrics,
        "numeric_quality": numeric_quality(doc),
        "source": source,
    }


def numeric_quality(doc):
    result = defaultdict(list)

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    key in NUMERIC_QUALITY
                    and isinstance(item, (int, float))
                    and not isinstance(item, bool)
                ):
                    if math.isfinite(item):
                        result[key].append(item)
                elif isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(doc)
    return dict(result)


def new_row(opid):
    return {
        "operation_id": opid,
        "receipts": [],
        "observations": [],
        "evaluations": [],
        "stage_attempts": {},
        "sources": [],
        "cohorts": [],
        "workflow_labels": [],
    }


def join_retained_status(rows, root, as_of, counters, errors):
    """Refresh admitted IDs from canonical captures, never invent admissions.

    Operator status captures may be stored separately from the original client
    receipt. Exact parent links also admit child observations, not new top-level
    requests. Preserve old observations and their hashes alongside each refresh.
    """
    paths = set()
    for name in ("operation.json", "children.json", "final-status.json", "admin-final.json"):
        paths.update(root.rglob(name))
    for path in sorted(paths):
        if excluded(path.relative_to(root)) or not path.is_file():
            continue
        try:
            documents = operation_documents(read(path))
        except (OSError, ValueError) as error:
            errors.append({"path": str(path.relative_to(root)), "error_type": type(error).__name__})
            continue
        source = evidence(path, root)
        for operation in documents:
            oid = identifier(operation.get("id"))
            parent = identifier(operation.get("parent_operation_id"))
            if not oid or (oid not in rows and parent not in rows):
                continue
            moment = observed_time(operation)
            if moment and moment > as_of:
                continue
            row = rows.setdefault(oid, new_row(oid))
            selected = {key: operation.get(key) for key in (
                "model_id", "status", "protocol", "operation", "parent_operation_id",
                "accepted_at", "started_at", "completed_at", "error_code", "attempt",
            )}
            selected.update(observed_at=stamp(moment), source=source)
            runtime = operation.get("execution_identity") or {}
            selected["runtime_image_digest"] = runtime.get("runtime_image_digest")
            selected["execution_identity_sha256"] = runtime.get(
                "execution_identity_sha256", runtime.get("execution_identity_digest")
            )
            if selected not in row["observations"]:
                row["observations"].append(selected)
                row["sources"].append(source)
                counters["joined_retained_status_observations"] += 1
            if parent in rows:
                row["cohorts"].extend(rows[parent]["cohorts"])


def scan(root, as_of, *, current=None, annotations=None):
    rows, unadmitted, scan_errors = {}, [], []
    counters = Counter()
    files = sorted(
        path
        for path in root.rglob("receipt.json")
        if not excluded(path.relative_to(root))
    )
    for path in files:
        try:
            doc = read(path)
        except (OSError, ValueError) as error:
            scan_errors.append(
                {
                    "path": str(path.relative_to(root)),
                    "error_type": type(error).__name__,
                }
            )
            continue
        if not isinstance(doc, dict):
            continue
        # Browser acquisition receipts, artifact uploads and workflow step ledgers
        # are not inference admissions. An API key or arbitrary UUID is not enough.
        identity = doc.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
        model = doc.get("model_id", doc.get("model", identity.get("model_id")))
        opid = identifier(doc.get("operation_id"))
        if doc.get("state") in {
            "finalized",
            "uploaded",
            "uploading",
            "reserved",
        } or doc.get("upload_id"):
            counters["artifact_receipts_excluded"] += 1
            continue
        if not opid and not model:
            counters["non_admission_receipts_excluded"] += 1
            continue
        moment = observed_time(doc)
        if moment and moment > as_of:
            counters["receipts_after_as_of_excluded"] += 1
            continue
        source = evidence(path, root)
        receipt = {
            "state": doc.get("state", "unknown"),
            "model_id": model,
            "case_id": doc.get("case_id", doc.get("case")),
            "scientist": doc.get("scientist"),
            "observed_at": stamp(moment),
            "elapsed_seconds": doc.get("elapsed_seconds"),
            "source": source,
            "reevaluated": bool(doc.get("reevaluated_at")),
            "error_code": doc.get("error_code"),
            "error_type": doc.get("error_type"),
        }
        if not opid:
            # A client-side timeout/rejection is not automatically a model failure.
            receipt["logical_identity_sha256"] = hashlib.sha256(
                json.dumps(
                    [
                        identity.get("caller_fingerprint"),
                        identity.get("key_id"),
                        model,
                        doc.get("idempotency_key", identity.get("idempotency_key")),
                        identity.get("case_sha256", identity.get("input_sha256")),
                    ],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            unadmitted.append(receipt)
            continue
        row = rows.setdefault(opid, new_row(opid))
        row["receipts"].append(receipt)
        row["sources"].append(source)
        if identity.get("cohort"):
            row["cohorts"].append(identity["cohort"])
        parts = path.relative_to(root).parts
        if parts[0] == "cohorts" and len(parts) > 1:
            row["cohorts"].append(parts[1])
        if "browser-evidence" in parts:
            row["workflow_labels"].append("actual-client retained workspace")
        for extra in sorted(path.parent.iterdir()):
            if not extra.is_file() or extra.suffix != ".json" or extra == path:
                continue
            is_eval = "evaluation" in extra.name or "reassessment" in extra.name
            is_status = extra.name in SAFE_FILES or extra.name.startswith(
                ("status-", "child-")
            )
            if not is_eval and not is_status:
                continue
            try:
                value = read(extra)
            except (OSError, ValueError) as error:
                scan_errors.append(
                    {
                        "path": str(extra.relative_to(root)),
                        "error_type": type(error).__name__,
                    }
                )
                continue
            ref = evidence(extra, root)
            if is_eval:
                if summary := evaluation_summary(value, ref):
                    row["evaluations"].append(summary)
                continue
            for operation in operation_documents(value):
                oid = identifier(operation.get("id"))
                if oid != opid and operation.get("parent_operation_id") != opid:
                    continue
                other = rows.setdefault(oid, new_row(oid))
                time = observed_time(operation)
                if time and time > as_of:
                    continue
                selected = {
                    key: operation.get(key)
                    for key in (
                        "model_id",
                        "status",
                        "protocol",
                        "operation",
                        "parent_operation_id",
                        "accepted_at",
                        "started_at",
                        "completed_at",
                        "error_code",
                        "attempt",
                    )
                }
                selected["observed_at"] = stamp(time)
                selected["source"] = ref
                runtime = operation.get("execution_identity", {})
                selected["runtime_image_digest"] = runtime.get("runtime_image_digest")
                selected["execution_identity_sha256"] = runtime.get(
                    "execution_identity_sha256",
                    runtime.get("execution_identity_digest"),
                )
                other["observations"].append(selected)
                other["sources"].append(ref)
                if oid != opid:
                    other["cohorts"].extend(row["cohorts"])
            for attempt in stage_attempts(value):
                previous = row["stage_attempts"].get(attempt["attempt_id"], {})
                # Prefer a terminal and richer observation to a stale poll.
                if (
                    previous.get("status") in TERMINAL
                    and attempt["status"] not in TERMINAL
                ):
                    continue
                for key in ("stage", "resource_class"):
                    if not attempt.get(key) or attempt[key] == "unknown":
                        attempt[key] = previous.get(key, "unknown")
                row["stage_attempts"][attempt["attempt_id"]] = {
                    **attempt,
                    "source": ref,
                }
    join_retained_status(rows, root, as_of, counters, scan_errors)
    auxiliary = []
    inference_rows = []
    for row in rows.values():
        if any(item.get("protocol") == "scientific-artifact-upload-v1"
               or item.get("operation") == "upload" for item in row["observations"]):
            auxiliary.append({"operation_id": row["operation_id"], "kind": "artifact_upload",
                              "sources": row["sources"]})
        else:
            inference_rows.append(row)
    normalized = [finalize(row, current or {}) for row in inference_rows]
    normalized.sort(key=lambda row: (row["model_id"], row["operation_id"]))
    annotations = annotations or {}
    for row in normalized:
        row["annotations"] = annotations.get("operations", {}).get(
            row["operation_id"], []
        )
    unadmitted_by_key = defaultdict(list)
    for item in unadmitted:
        unadmitted_by_key[item["logical_identity_sha256"]].append(item)
    from aggregate_workshop import scan_workshop

    return {
        "schema": "fs2.qualification-campaign-aggregate/v1",
        "as_of": stamp(as_of),
        "scan_finished_at": stamp(datetime.now(timezone.utc)),
        "verdict": "not_a_readiness_decision",
        "evidence_root": str(root),
        "counts": aggregate_counts(normalized),
        "by_app": groups(normalized, "model_id"),
        "by_workflow": groups(normalized, "workflow"),
        "operations": normalized,
        "auxiliary_operations_excluded": auxiliary,
        "separate_workshop_population": scan_workshop(root, as_of),
        "unadmitted_logical_items": list(unadmitted_by_key.values()),
        "scan": {
            **dict(counters),
            "admission_receipt_files": len(files),
            "errors": scan_errors,
        },
        "manual_interventions": annotations.get("manual_interventions", []),
        "client_report_findings": annotations.get("client_report_findings", []),
        "separately_qualified_isolated_evidence": annotations.get(
            "isolated_evidence", []
        ),
        "runtime_comparison_source": current.get("source") if current else None,
        "limitations": [
            "Retained admission receipts anchor this population; missing receipts or undownloaded browser "
            "workspace operations are not reconstructed.",
            "Poll/discovery/upload/reassessment counts are excluded. "
            "A durable operation is not necessarily a GPU execution.",
            "Child operations without started_at are excluded from model-execution counts "
            "and labelled unconfirmed, not presumed inference.",
            "Service success, independent artifact checks, reference accuracy and actual-client "
            "report delivery are different gates.",
            "Current-runtime matches require explicit exact captured identity; "
            "release and snapshot qualification are not inherited.",
            "Runtime match does not prove the control-plane or client release. "
            "These identities are generally absent from operation records.",
            "Independent-check pass is bounded to its evaluator, not publication reproduction, "
            "binding efficacy or clinical validation.",
            "As-of filters explicit evidence times; timestamp-less observations "
            "are retained as time-unknown, not backdated.",
            "Stage-attempt and sample totals are observed lower bounds, not top-level model-call totals.",
            "Operator interventions and client/report failures need the separately sourced "
            "annotation ledger; absence is not proof of zero.",
        ],
    }


def finalize(row, current):
    observations = row["observations"]
    terminal = [x for x in observations if x.get("status") in TERMINAL]
    ranked = sorted(terminal or observations, key=lambda x: x.get("observed_at") or "")
    latest = ranked[-1] if ranked else {}
    receipts = sorted(row["receipts"], key=lambda x: x.get("observed_at") or "")
    model_ids = {
        x["model_id"]
        for x in observations + receipts
        if isinstance(x.get("model_id"), str)
    }
    model = (
        next(iter(model_ids))
        if len(model_ids) == 1
        else "unknown"
        if not model_ids
        else "conflicting"
    )
    parents = {
        x["parent_operation_id"] for x in observations if x.get("parent_operation_id")
    }
    protocol = next(
        (x["protocol"] for x in observations if x.get("protocol")), "unknown"
    )
    kind = (
        "child_inference"
        if parents and any(x.get("started_at") for x in observations)
        else (
            "child_execution_unconfirmed"
            if parents
            else "top_level_scientific_batch"
            if protocol == "scientific-batch-v1"
            else "top_level_serving"
        )
    )
    state = latest.get("status", "unknown")
    if state == "unknown" and receipts:
        retained = receipts[-1]["state"]
        state = (
            "succeeded_receipt_only"
            if retained in {"verified", "semantic_failed", "succeeded"}
            else retained
        )
    verdicts = list(
        {
            (x["source"]["sha256"], x["source"]["path"]): x for x in row["evaluations"]
        }.values()
    )
    active = [x for x in verdicts if x["kind"] != "historical"]
    passing, failing = (
        any(x["pass"] for x in active),
        any(not x["pass"] for x in active),
    )
    check = (
        "mixed_retained_verdicts"
        if passing and failing
        else "pass"
        if passing
        else "fail"
        if failing
        else "not_linked"
    )
    historical_fail = any(not x["pass"] for x in verdicts) or any(
        x["state"] == "semantic_failed" for x in receipts
    )
    error_codes = sorted(
        {
            x["error_code"]
            for x in observations + receipts
            if isinstance(x.get("error_code"), str)
        }
    )
    cause = (
        "bounded_generation_exhaustion"
        if "generation_exhausted" in error_codes
        else "capacity_evidence"
        if any(x in CAPACITY_CODES for x in error_codes) or state == "preempted"
        else (
            "unknown_cause"
            if state in {"failed", "expired", "cancelled"}
            else "not_classified"
        )
    )
    runtimes = sorted(
        {
            x["runtime_image_digest"]
            for x in observations
            if x.get("runtime_image_digest")
        }
    )
    identities = sorted(
        {
            x["execution_identity_sha256"]
            for x in observations
            if x.get("execution_identity_sha256")
        }
    )
    expected = current.get("apps", {}).get(model, {})
    match = "unknown"
    if expected.get("execution_identity_sha256") and identities:
        match = (
            "exact_current_identity"
            if identities == [expected["execution_identity_sha256"]]
            else "different_or_historical_identity"
        )
    elif expected.get("runtime_image_digest") and runtimes:
        match = (
            "current_image_only"
            if runtimes == [expected["runtime_image_digest"]]
            else "different_or_historical_image"
        )
    evaluator_names = sorted({x["evaluator"] for x in active})
    workflow = "; ".join(
        sorted({WORKFLOWS.get(name, name) for name in evaluator_names})
    ) or APP_WORKFLOWS.get(model, "unclassified retained workflow")
    row.update(
        model_id=model,
        model_id_conflicts=sorted(model_ids) if len(model_ids) > 1 else [],
        operation_kind=kind,
        execution_started_witness=any(x.get("started_at") for x in observations),
        parent_operation_ids=sorted(parents),
        protocol=protocol,
        service_state=state,
        independent_check_state=check,
        historical_failed_check_retained=historical_fail,
        cause_classification=cause,
        error_codes=error_codes,
        runtime_image_digests=runtimes,
        execution_identities=identities,
        runtime_comparison=match,
        workflow=workflow,
        evaluations=verdicts,
        cohorts=sorted(set(row["cohorts"])),
        workflow_labels=sorted(set(row["workflow_labels"])),
        stage_attempts=list(row["stage_attempts"].values()),
    )
    # Dedup poll copies in report; observations remain separate, never count as calls.
    row["sources"] = list(
        {(x["path"], x["sha256"]): x for x in row["sources"]}.values()
    )
    return row


def aggregate_counts(rows):
    top_level = [row for row in rows if row["operation_kind"].startswith("top_level_")]
    children = [
        row for row in rows if not row["operation_kind"].startswith("top_level_")
    ]
    stages = {
        attempt["attempt_id"]: attempt
        for row in rows
        for attempt in row["stage_attempts"]
    }
    return {
        "durable_operation_ids": len(rows),
        "operation_kinds": dict(Counter(x["operation_kind"] for x in rows)),
        "top_level_inference_request_ids": sum(
            x["operation_kind"].startswith("top_level_") for x in rows
        ),
        "serving_execution_started_witnesses": sum(
            x["execution_started_witness"]
            and x["operation_kind"] in {"top_level_serving", "child_inference"}
            for x in rows
        ),
        "service_states": dict(Counter(x["service_state"] for x in rows)),
        "service_states_scope": "all durable IDs, including child operations; not the top-level request denominator",
        "top_level_service_states": dict(
            Counter(x["service_state"] for x in top_level)
        ),
        "child_service_states": dict(Counter(x["service_state"] for x in children)),
        "top_level_independent_checks": dict(
            Counter(x["independent_check_state"] for x in top_level)
        ),
        "child_independent_checks": dict(
            Counter(x["independent_check_state"] for x in children)
        ),
        "independent_checks": dict(Counter(x["independent_check_state"] for x in rows)),
        "operations_with_any_retained_failed_check": sum(
            x["historical_failed_check_retained"] for x in rows
        ),
        "runtime_comparison": dict(Counter(x["runtime_comparison"] for x in rows)),
        "cause_classification": dict(Counter(x["cause_classification"] for x in rows)),
        "observed_stage_attempts": len(stages),
        "stage_attempt_states": dict(Counter(x["status"] for x in stages.values())),
    }


def groups(rows, key):
    result = {}
    for value in sorted({row[key] for row in rows}):
        members = [row for row in rows if row[key] == value]
        result[value] = aggregate_counts(members)
        latencies = [
            max(
                (receipt.get("elapsed_seconds") or 0 for receipt in row["receipts"]),
                default=0,
            )
            for row in members
        ]
        latencies = [
            value
            for value in latencies
            if isinstance(value, (int, float)) and value > 0
        ]
        result[value]["observed_client_elapsed_seconds"] = {
            "samples": len(latencies),
            "median": statistics.median(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "scope": "client elapsed, including polling/queue/transport; not GPU time or cold start",
        }
        numeric = defaultdict(list)
        outputs = Counter()
        for row in members:
            # One canonical evaluation per operation. Reassessments remain in the
            # detailed evidence but cannot inflate scientific sample denominators.
            canonical = [
                item
                for item in row["evaluations"]
                if item["source"]["path"].endswith("/evaluation.json")
            ]
            unique = {item["source"]["sha256"]: item for item in canonical}
            if len(unique) != 1:
                continue
            item = next(iter(unique.values()))
            for metric, samples in item["numeric_quality"].items():
                numeric[metric].extend(samples)
            for metric, count in item["metrics"].items():
                if (
                    isinstance(count, int)
                    and not isinstance(count, bool)
                    and (
                        metric.endswith("_count")
                        or metric
                        in {
                            "samples_returned",
                            "returned_molecules",
                            "requested_molecules",
                            "unique_sequences",
                            "generated_geometry_pass_count",
                            "self_refolded_geometry_pass_count",
                        }
                    )
                ):
                    outputs[metric] += count
        result[value]["observed_output_counts_not_calls"] = dict(outputs)
        result[value]["numeric_quality_descriptive_only"] = {
            metric: {
                "samples": len(samples),
                "min": min(samples),
                "median": statistics.median(samples),
                "max": max(samples),
            }
            for metric, samples in sorted(numeric.items())
        }
    return result


def current_runtimes(path):
    """Accept an explicit map or a captured Kubernetes ConfigMapList, offline."""
    doc = read(path)
    if "apps" in doc:
        return doc
    apps = {}
    for item in doc.get("items", []):
        data = item.get("data", {})
        if "admin-configuration.json" in data:
            for model, spec in (
                json.loads(data["admin-configuration.json"]).get("models", {}).items()
            ):
                apps.setdefault(model, {})["runtime_image_digest"] = spec.get(
                    "artifact", {}
                ).get("image_digest")
        if "execution-map.json" in data:
            for spec in json.loads(data["execution-map.json"]).get("models", []):
                apps.setdefault(spec["model_id"], {}).update(
                    {
                        "runtime_image_digest": spec.get("runtime_image_digest"),
                        "execution_identity_sha256": spec.get(
                            "execution_identity_sha256"
                        ),
                    }
                )
    return {
        "source": {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "scope": "captured desired state, not per-request proof or later live state",
        },
        "apps": apps,
    }


def ledger_annotations(path):
    """Keep historical defect statements sourced, not inferred from HTTP codes."""
    source = {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    result = {"manual_interventions": [], "client_report_findings": []}
    manual_ids = {"Q41", "Q51"}
    client_ids = {
        "Q12",
        "Q13",
        "Q17",
        "Q19",
        "Q24",
        "Q28",
        "Q39",
        "Q48",
        "Q52",
        "Q53",
        "Q57",
    }
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        match = re.match(r"\| (Q\d+) \|", line)
        if not match:
            continue
        finding = match[1]
        if finding not in manual_ids | client_ids:
            continue
        cells = [item.strip() for item in line.split("|")[1:-1]]
        item = {
            "id": finding,
            "summary": finding + " (historical ledger): " + " — ".join(cells[1:]),
            "source": {**source, "line": line_number},
            "scope": "historical statement, not current-release resolution or exhaustive incident count",
        }
        result[
            "manual_interventions"
            if finding in manual_ids
            else "client_report_findings"
        ].append(item)
    return result


def markdown(report):
    counts = report["counts"]
    lines = [
        "# Scientific campaign — retained evidence rollup",
        "",
        f"As of **{report['as_of']}**. This is not a readiness verdict.",
        "",
        f"{counts['durable_operation_ids']} distinct durable operation IDs; "
        f"{counts['observed_stage_attempts']} separately observed scientific stage attempts.",
        "",
        "Operation population: `"
        + json.dumps(counts["operation_kinds"], sort_keys=True)
        + "`.",
        "",
        "Top-level service states: `"
        + json.dumps(counts["top_level_service_states"], sort_keys=True)
        + "`.",
        "",
        "Child service states (separate denominator): `"
        + json.dumps(counts["child_service_states"], sort_keys=True)
        + "`.",
        "",
        "| App | Top-level requests | Service succeeded | Service failed | "
        "Independent checks (pass / fail / mixed / missing) |",
        "|---|---:|---:|---:|---|",
    ]
    for app, values in report["by_app"].items():
        states, checks = (
            values["top_level_service_states"],
            values["top_level_independent_checks"],
        )
        lines.append(
            f"| {app} | {values['top_level_inference_request_ids']} | {states.get('succeeded', 0)} | "
            f"{states.get('failed', 0)} | "
            + " / ".join(
                str(checks.get(key, 0))
                for key in ("pass", "fail", "mixed_retained_verdicts", "not_linked")
            )
            + " |"
        )
    lines += [
        "",
        "Receipt-only successes are not included in the service-succeeded column. "
        "Check passes are bounded structural/semantic checks, not scientific efficacy.",
        "",
        "## Failure history and scope",
        "",
        f"{counts['operations_with_any_retained_failed_check']} operations retain a failed evaluator verdict "
        "(including corrected evaluator bugs); later reassessments do not erase it.",
        "",
        f"{len(report['unadmitted_logical_items'])} distinct pre-admission identities retained separately. "
        "These are not additional model calls.",
        "",
        "Runtime comparison: `"
        + json.dumps(counts["runtime_comparison"], sort_keys=True)
        + "`.",
        "",
        "## Scientific workflow population",
        "",
    ]
    for workflow, values in report["by_workflow"].items():
        lines.append(
            f"- {workflow}: {values['durable_operation_ids']} durable IDs; "
            f"{values['observed_stage_attempts']} observed stage attempts."
        )
        if workflow in {
            "protein design",
            "design-to-refold recovery",
            "inverse folding",
        }:
            lines.append(
                "  Observed outputs (not additional calls): `"
                + json.dumps(values["observed_output_counts_not_calls"], sort_keys=True)
                + "`."
            )
    for title, field in (
        ("Manual interventions", "manual_interventions"),
        ("Client/report findings", "client_report_findings"),
        (
            "Separate isolated candidate evidence",
            "separately_qualified_isolated_evidence",
        ),
    ):
        lines += ["", "## " + title, ""]
        for item in report[field]:
            lines.append(
                "- " + item["summary"] + " Evidence: `" + item["source"]["path"] + "`."
            )
        if not report[field]:
            lines.append("Not inventoried in this capture; do not read this as zero.")
    workshop = report.get("separate_workshop_population")
    if workshop:
        lines += [
            "",
            "## MindEval consultations — separate population",
            "",
            workshop["scope"],
            "",
        ]
        for name, values in [
            ("All retained workshop runs", workshop["summary"]),
            *workshop["by_cohort"].items(),
        ]:
            lines.append(
                f"- {name}: {values['consultations']} consultations; "
                f"{values['completed_model_responses']} identified model responses; "
                f"roles `{json.dumps(values['responses_by_role'], sort_keys=True)}`; "
                f"states `{json.dumps(values['consultation_states'], sort_keys=True)}`; "
                f"{values['judgments_with_five_finite_1_to_6_scores']} structurally valid judgments."
            )
        lines += [
            "",
            "Seed/human turns and planned rounds are excluded. Reported retries are separate; "
            "unobserved failed provider attempts cannot be reconstructed. Scores are not clinician validation.",
        ]
    lines += ["", "## Limitations", ""] + [
        "- " + item for item in report["limitations"]
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", default=stamp(datetime.now(timezone.utc)))
    parser.add_argument("--current-runtimes", type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--defect-ledger", type=Path)
    args = parser.parse_args()
    as_of = utc(args.as_of)
    if not as_of:
        parser.error("--as-of must be an ISO UTC timestamp")
    os.umask(0o077)
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("use a new empty output directory; prior snapshots are immutable")
    annotations = read(args.annotations) if args.annotations else {}
    if args.defect_ledger:
        for field, items in ledger_annotations(args.defect_ledger).items():
            annotations.setdefault(field, []).extend(items)
    report = scan(
        args.root,
        as_of,
        current=current_runtimes(args.current_runtimes)
        if args.current_runtimes
        else None,
        annotations=annotations,
    )
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    (args.output / "aggregate.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (args.output / "REPORT.md").write_text(markdown(report))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "as_of": report["as_of"],
                "counts": report["counts"],
            }
        )
    )


if __name__ == "__main__":
    main()
