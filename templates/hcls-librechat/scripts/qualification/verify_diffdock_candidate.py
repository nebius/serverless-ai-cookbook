#!/usr/bin/env python3
"""Independently assess retained seeded GPU probes, without new model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np
from rdkit import Chem

from evaluators import evaluate
from manage_campaign import save


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_run(directory, cases, base):
    receipt = json.loads((directory / "receipt.json").read_text())
    results, evaluations = {}, []
    for run in receipt["runs"]:
        result_path = directory / run["result_file"]
        if digest(result_path) != run["result_sha256"]:
            raise ValueError("Retained runtime result checksum changed")
        case = cases[run["case_id"]]
        expected_sha = hashlib.sha256(json.dumps(case["arguments"], sort_keys=True,
                                                 separators=(",", ":")).encode()).hexdigest()
        if expected_sha != run["input_sha256"]:
            raise ValueError("Retained runtime request differs from frozen case")
        result = json.loads(result_path.read_text())
        results[run["case_id"], run["repetition"]] = result
        metric = evaluate(case, result, base)
        evaluations.append({"repetition": run["repetition"], "result_sha256": run["result_sha256"], **metric})
    expected_keys = {(key, repetition) for key in cases for repetition in (1, 2)}
    if set(results) != expected_keys or len(receipt["runs"]) != len(expected_keys):
        raise ValueError("Incomplete or duplicate probe outputs")
    return receipt, results, evaluations


def compare(left, right, coordinate_tolerance, confidence_tolerance):
    if len(left["poses"]) != len(right["poses"]):
        raise ValueError("Cross-process pose count mismatch")
    coordinate_delta = confidence_delta = 0.0
    for a, b in zip(left["poses"], right["poses"], strict=True):
        am, bm = (Chem.MolFromMolBlock(item["sdf"], sanitize=True, removeHs=True) for item in (a, b))
        if am is None or bm is None or Chem.MolToSmiles(am) != Chem.MolToSmiles(bm):
            raise ValueError("Cross-process ligand topology mismatch")
        coordinate_delta = max(coordinate_delta, float(np.max(np.abs(
            am.GetConformer().GetPositions() - bm.GetConformer().GetPositions()))))
        confidence_delta = max(confidence_delta, abs(a["confidence"] - b["confidence"]))
    return {"maximum_coordinate_difference_angstrom": coordinate_delta,
            "maximum_confidence_difference": confidence_delta,
            "numerical_repeatability_pass": coordinate_delta <= coordinate_tolerance
            and confidence_delta <= confidence_tolerance}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--reference-base", type=Path, required=True)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.cases.read_text())
    cases = {row["case_id"]: row for row in rows}
    if len(cases) != len(rows):
        raise ValueError("Duplicate frozen case identity")
    loaded = [load_run(directory, cases, args.reference_base) for directory in args.run]
    reports = []
    for directory, (receipt, results, metrics) in zip(args.run, loaded, strict=True):
        if receipt["cases_sha256"] != digest(args.cases):
            raise ValueError("Probe used a different input manifest")
        reports.append({"receipt_sha256": digest(directory / "receipt.json"), "gpu": receipt["gpu"],
                        "model_load_seconds": receipt["model_load_seconds"],
                        "inference_median_seconds": statistics.median(r["seconds"] for r in receipt["runs"]),
                        "inference_total_seconds": sum(r["seconds"] for r in receipt["runs"]),
                        "repeatability_pass": receipt["passed"], "evaluations": metrics})
    cross_process = []
    for index, (receipt, results, _) in enumerate(loaded[1:], start=1):
        baseline = loaded[0][0]
        if any(receipt[field] != baseline[field] for field in
               ("coordinate_tolerance_angstrom", "confidence_tolerance", "adapter_identity")):
            raise ValueError("Cross-process adapter or predeclared tolerances changed")
        for key in sorted(loaded[0][1]):
            try:
                comparison = compare(loaded[0][1][key], results[key], baseline["coordinate_tolerance_angstrom"],
                                     baseline["confidence_tolerance"])
            except ValueError as error:
                # Preserve the entire failed cohort rather than aborting the
                # report at its first uncomparable generated ligand.
                comparison = {"numerical_repeatability_pass": False, "error": str(error)}
            cross_process.append({"case_id": key[0], "repetition": key[1], "compared_run": index,
                                  **comparison})
    report = {"cases_sha256": digest(args.cases), "run_count": len(loaded),
              "inference_calls": sum(len(item[0]["runs"]) for item in loaded),
              "all_retained_bytes_verified": True, "runs": reports, "cross_process": cross_process,
              "service_semantic_pass": all(m["service_semantic_pass"] for item in reports for m in item["evaluations"]),
              "numerical_repeatability_pass": all(item["repeatability_pass"] for item in reports)
                  and all(item["numerical_repeatability_pass"] for item in cross_process),
              "scope": "Isolated adapter execution. Pose RMSD is independently measured, not paper reproduction, experimental affinity, public-route or snapshot qualification."}
    save(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key not in {"runs", "cross_process"}}))


if __name__ == "__main__":
    main()
