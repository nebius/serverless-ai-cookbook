#!/usr/bin/env python3
"""Compare two real public DiffDock cohorts against frozen numerical tolerances."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from manage_campaign import save
from run_campaign import digest
from verify_diffdock_candidate import compare


def normalize(result):
    if isinstance(result.get("poses"), list):
        return result
    sdf = result["ligand_positions"]
    confidence = result["position_confidence"]
    if not isinstance(sdf, list) or not sdf or len(sdf) != len(confidence):
        raise ValueError("Public pose/confidence count mismatch")
    return {"poses": [{"sdf": block, "confidence": score} for block, score in zip(sdf, confidence, strict=True)]}


def retained_result(folder, case):
    receipt = json.loads((folder / "receipt.json").read_text())
    operation = json.loads((folder / "operation.json").read_text())
    if receipt["identity"]["case_sha256"] != digest(case):
        raise ValueError("Public case differs from frozen manifest")
    if receipt["state"] != "verified" or operation["status"] != "succeeded":
        raise ValueError("Public operation/evaluation did not succeed")
    if operation["id"] != receipt["operation_id"] or operation["model_id"] != "diffdock":
        raise ValueError("Public operation identity mismatch")
    reference = json.loads((folder / "result-envelope.json").read_text())["result"]["artifact"]
    raw = (folder / (reference["artifact_id"] + ".artifact")).read_bytes()
    if len(raw) != reference["size_bytes"] or hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("Public result artifact checksum/size mismatch")
    result = json.loads(raw)
    if result != json.loads((folder / "result.json").read_text()):
        raise ValueError("Derived result differs from downloaded artifact")
    return result, {
        "operation_id": operation["id"],
        "runtime": operation.get("runtime"),
        "artifact_sha256": reference["sha256"],
        "accepted_at": operation.get("accepted_at"),
        "started_at": operation.get("started_at"),
        "completed_at": operation.get("completed_at"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--scientist", required=True)
    parser.add_argument("--predeclared-tolerances", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text())["cases"]
    baseline = json.loads(args.predeclared_tolerances.read_text())
    coordinates = baseline["coordinate_tolerance_angstrom"]
    confidence = baseline["confidence_tolerance"]
    rows = []
    for case in cases:
        left, lm = retained_result(args.left / args.scientist / case["case_id"], case)
        right, rm = retained_result(args.right / args.scientist / case["case_id"], case)
        rows.append({"case_id": case["case_id"], "left": lm, "right": rm,
                     **compare(normalize(left), normalize(right), coordinates, confidence)})
    report = {
        "schema": "fs2-diffdock-public-paired-repeatability/v1",
        "cases_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "predeclared_tolerances_sha256": hashlib.sha256(args.predeclared_tolerances.read_bytes()).hexdigest(),
        "coordinate_tolerance_angstrom": coordinates,
        "confidence_tolerance": confidence,
        "public_calls": 2 * len(rows),
        "all_artifacts_verified": True,
        "numerical_repeatability_pass": all(row["numerical_repeatability_pass"] for row in rows),
        "rows": rows,
        "scope": "Paired public-route numerical repeatability; not docking accuracy, clinical efficacy or whole-platform readiness.",
    }
    save(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}))


if __name__ == "__main__":
    main()
