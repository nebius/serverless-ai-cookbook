#!/usr/bin/env python3
"""Summarize a frozen refolding study without dropping failed/missing cases.

Reads existing independent evaluations only. No requests, inference, threshold
selection, or modification of original receipts. Shared backbones are counted
separately from designs; these are not independent experimental replicates.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

from manage_campaign import now, save


def sha(data):
    return hashlib.sha256(data).hexdigest()


def summarize(manifest, cohort):
    document = json.loads(manifest.read_text())
    cases = [case for case in document["cases"] if case["expected"]["evaluator"] == "backbone_recovery"]
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate frozen case identity")
    receipts = {}
    for path in sorted(cohort.glob("scientist-*/*/receipt.json")):
        receipt = json.loads(path.read_text())
        if receipt["case_id"] in receipts:
            raise ValueError("Duplicate case receipt; select one explicit cohort")
        receipts[receipt["case_id"]] = (path, receipt)
    rows = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        provenance = case["provenance"]
        row = {"case_id": case["case_id"], "upstream_model": provenance["upstream_model_id"],
               "upstream_case_id": provenance["upstream_case_id"],
               "reference_sha256": provenance["reference_sha256"], "state": "not_observed"}
        rows.append(row)
        if case["case_id"] not in receipts:
            continue
        path, receipt = receipts[case["case_id"]]
        row.update(state=receipt["state"], operation_id=receipt.get("operation_id"),
                   receipt_sha256=sha(path.read_bytes()))
        result_path = path.parent / "result.json"
        if result_path.exists():
            row["result_sha256"] = sha(result_path.read_bytes())
        evaluation_path = path.parent / "evaluation.json"
        if not evaluation_path.exists():
            continue
        raw = evaluation_path.read_bytes()
        evaluation = json.loads(raw)
        if evaluation.get("evaluator") != "backbone_recovery":
            raise ValueError("Unexpected evaluator in refolding study")
        reference = (manifest.parent / case["expected"]["reference_path"]).read_bytes()
        if sha(reference) != provenance["reference_sha256"] or evaluation.get("reference_sha256") != sha(reference):
            raise ValueError("Reference bytes/manifest/evaluation identity differ")
        row.update(evaluation_sha256=sha(raw), independent_semantic_pass=evaluation["service_semantic_pass"],
                   predictions=evaluation.get("predictions", []))
        for prediction in row["predictions"]:
            for name in ("ca_rmsd_angstrom", "ca_lddt_15A"):
                if not isinstance(prediction.get(name), (int, float)) or not math.isfinite(prediction[name]):
                    raise ValueError("Non-finite or missing recovery metric")
    groups = []
    for upstream in sorted({row["upstream_model"] for row in rows}):
        selected = [row for row in rows if row["upstream_model"] == upstream]
        predictions = [prediction for row in selected for prediction in row.get("predictions", [])]
        metrics = {}
        for field in ("ca_rmsd_angstrom", "ca_lddt_15A"):
            values = [prediction[field] for prediction in predictions]
            metrics[field] = None if not values else {"min": min(values), "median": statistics.median(values), "max": max(values)}
        groups.append({"upstream_model": upstream, "frozen_cases": len(selected),
                       "case_states": dict(Counter(row["state"] for row in selected)),
                       "source_requests": len({row["upstream_case_id"] for row in selected}),
                       "unique_backbone_references": len({row["reference_sha256"] for row in selected}),
                       "measured_predictions": len(predictions), "metrics": metrics})
    return {"at": now(), "manifest_sha256": sha(manifest.read_bytes()), "selected_frozen_cases": len(cases),
            "non_refolding_manifest_cases": len(document["cases"]) - len(cases), "groups": groups, "rows": rows,
            "scope": "Descriptive full-position CA recovery; all frozen cases retained. No affinity, stability, paper-reproduction or independent-replicate claim. No post-hoc quality threshold."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output path; preserve historical reports")
    report = summarize(args.manifest, args.cohort)
    save(args.output, report)
    print(json.dumps({"selected_frozen_cases": report["selected_frozen_cases"], "groups": report["groups"]}))
