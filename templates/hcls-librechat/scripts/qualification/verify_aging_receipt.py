#!/usr/bin/env python3
"""Recompute saved aging-study rows against the independent model reference.

Read-only qualification of downloaded customer deliverables. This reuses the
campaign Decimal/NumPy reference (not the serving or workbench analysis code),
and also checks the original request/result bytes and every exported CSV row.
It does not establish clinical validity or validate free-form narrative.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from evaluators import altumage_reference, phenoage_reference, sha256


def verify(metrics_path: Path, rows_path: Path, downloaded_workspace: Path, assets: Path) -> dict:
    metrics = json.loads(metrics_path.read_text())
    with rows_path.open() as stream:
        csv_rows = list(csv.DictReader(stream))
    exported = {(row["cohort"], row["sample_id"]): row for row in csv_rows}
    measured = {(row["cohort"], row["sample_id"]): row for row in metrics["rows"]}
    if len(exported) != len(csv_rows) or len(measured) != metrics["row_count"] or exported.keys() != measured.keys():
        raise ValueError("CSV/metrics row identities or counts disagree")
    model = metrics["model_id"]
    if model == "altumage":
        manifest = json.loads((assets / "manifest.json").read_text())
        for name in ("preprocessing.json", "AltumAge.h5"):
            if sha256((assets / name).read_bytes()) != manifest["runtime_artifacts"][name]:
                raise ValueError("Original reference artifact checksum differs")
        if manifest["source_revision"] != metrics["model_version"]:
            raise ValueError("Reference model revision differs")
        prep = json.loads((assets / "preprocessing.json").read_text())
    checks = []
    for cohort in metrics["cohorts"]:
        documents = {}
        for kind in ("input", "result"):
            claimed = cohort[kind]
            relative = Path(claimed["path"]).relative_to("/workspace")
            if ".." in relative.parts:
                raise ValueError("Expected workspace-relative source")
            raw = (downloaded_workspace / relative).read_bytes()
            if len(raw) != claimed["size_bytes"] or sha256(raw) != claimed["sha256"]:
                raise ValueError("Downloaded source does not match claimed byte hash")
            documents[kind] = json.loads(raw)
        request, result = documents["input"], documents["result"]
        if result.get("model_id") != model or result.get("model_version") != metrics["model_version"]:
            raise ValueError("Result model identity differs from declared reference")
        samples = request["samples"]
        actual = {row["sample_id"]: row for row in result["predictions"]}
        if len(actual) != len(samples) or set(actual) != {row["sample_id"] for row in samples}:
            raise ValueError("Result and request sample identities disagree")
        if model == "phenoage":
            references = [phenoage_reference(row) for row in samples]
            field, tolerance = "phenotypic_age_years", 1e-7
        elif model == "altumage":
            positions = {name: index for index, name in enumerate(request["cpg_sites"])}
            if len(positions) != 20318 or set(positions) != set(prep["cpgs"]):
                raise ValueError("Expected exact original named CpGs")
            order = [positions[name] for name in prep["cpgs"]]
            values = np.asarray([[row["beta_values"][index] for index in order] for row in samples], dtype=float)
            missing = np.isnan(values)
            if missing.any() and request.get("missing_values", "error") != "reference_median":
                raise ValueError("Unexpected missing value policy")
            values = (np.where(missing, prep["center"], values) - prep["center"]) / prep["scale"]
            references = altumage_reference(assets / "AltumAge.h5", values)
            field, tolerance = "predicted_chronological_age_years", 0.002
        else:
            raise ValueError("Unsupported aging modality")
        for sample, expected in zip(samples, references, strict=True):
            key = (cohort["label"], sample["sample_id"])
            prediction = actual[sample["sample_id"]][field]
            error = abs(prediction - float(expected))
            row, csv_row = measured[key], exported[key]
            values = {"hosted_age_years": prediction, "independent_age_years": float(expected),
                      "absolute_error_years": error}
            consistent = all(abs(float(source[name]) - value) < 1e-10
                             for source in (row, csv_row) for name, value in values.items())
            checks.append({"cohort": key[0], "sample_id": key[1], "absolute_error_years": error,
                           "csv_and_metrics_match": consistent, "reference_tolerance_pass": error <= tolerance})
    return {"verified": len(checks) == len(exported) and all(row["csv_and_metrics_match"] and row["reference_tolerance_pass"] for row in checks),
            "model_id": model, "row_count": len(checks), "maximum_absolute_error_years": max(row["absolute_error_years"] for row in checks),
            "rows": checks, "metrics_sha256": sha256(metrics_path.read_bytes()), "csv_sha256": sha256(rows_path.read_bytes()),
            "clinical_validity": "not_evaluated", "free_narrative": "requires_separate_review"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.metrics, args.rows, args.workspace, args.assets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
    raise SystemExit(0 if result["verified"] else 1)
