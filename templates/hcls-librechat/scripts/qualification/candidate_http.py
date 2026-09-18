#!/usr/bin/env python3
"""Isolated runtime repair matrix; never a public/customer qualification.

The manager creates a digest-pinned candidate Pod and owns promotion. This
runner uses the same retained model arguments and independent evaluators,
without altering original cohort evidence or production routes.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from evaluators import evaluate


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model", required=True, choices=["proteinmpnn", "genmol", "nv-segment-ct"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--identity", required=True, type=Path, help="Actual Pod/node/GPU/driver identity receipt.")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing candidate cohort.")
    args.output.mkdir(parents=True)
    source = args.manifest.read_bytes()
    cases = [case for case in json.loads(source)["cases"] if case["model_id"] == args.model]
    if args.model == "proteinmpnn":
        cases = [case for case in cases if case["provenance"]["pdb_id"].upper() in {"1QYS", "1TIM", "1TEN", "1UBQ"}]
        assert len(cases) == 36, "Expected 18 original failures, nine partial-known and nine complete-backbone regressions."
        path = "/biology/ipd/proteinmpnn/predict"
    elif args.model == "genmol":
        assert len(cases) == 36
        path = "/generate"
        for scoring in ("QED", "LogP"):
            cases.append({"case_id": f"genmol-extra-unique-{scoring.lower()}-16",
                "arguments": {"smiles": "[*{10-20}]", "num_molecules": 16, "scoring": scoring,
                              "temperature": 1, "noise": 1, "unique": True},
                "expected": {"evaluator": "molecule_generation", "num_molecules": 16, "scoring": scoring}})
    else:
        assert len(cases) == 27, "Expected nine unmodified expert-labelled scans in three prompt modes."
        path = "/segment"
    identity = json.loads(args.identity.read_text())
    receipts = []
    with httpx.Client(base_url=args.base_url, timeout=300) as client:
        health = client.get("/readyz" if args.model == "nv-segment-ct" else "/v1/health/ready")
        health.raise_for_status()
        save(args.output / "health.json", health.json())
        for case in cases:
            folder = args.output / case["case_id"]
            folder.mkdir()
            arguments = copy.deepcopy(case["arguments"])
            if args.model == "nv-segment-ct":
                prepared = case["preparation"]["artifact_fields"]
                if len(prepared) != 1 or prepared[0]["field"] != "input_nifti_base64":
                    raise ValueError("Unexpected CT input preparation")
                field = prepared[0]
                raw = (args.manifest.parent / field["local_path"]).read_bytes()
                if len(raw) != field["size_bytes"] or hashlib.sha256(raw).hexdigest() != field["sha256"]:
                    raise ValueError("Prepared CT input differs from frozen source")
                arguments[field["field"]] = base64.b64encode(raw).decode()
                save(folder / "input-identity.json", field)
            # Large image bytes already have a frozen input identity. Preserve
            # every scientific parameter without duplicating the public dataset.
            save(folder / "request.json", case["arguments"])
            started_at = datetime.now(timezone.utc).isoformat()
            start = time.monotonic()
            response = client.post(path, json=arguments)
            elapsed = time.monotonic() - start
            result = response.json()
            save(folder / "result.json", result)
            measured = evaluate(case, result, args.manifest.parent) if response.status_code == 200 else {
                "service_semantic_pass": False, "http_failure": response.status_code}
            if args.model == "genmol" and response.status_code == 200:
                metrics = result.get("metrics", {})
                measured["bounded_generation_metrics_pass"] = (
                    metrics.get("requested_molecules") == case["arguments"]["num_molecules"]
                    and metrics.get("returned_molecules") == len(result.get("molecules", []))
                    and 0 < metrics.get("sampling_attempts", 0) <= metrics.get("max_sampling_attempts", 0)
                    and 0 < metrics.get("candidate_requests", 0) <= metrics.get("max_candidate_requests", 0))
                if case["arguments"].get("unique"):
                    from rdkit import Chem
                    canonical = [Chem.MolToSmiles(Chem.MolFromSmiles(item["smiles"])) for item in result["molecules"]]
                    measured["unique_requirement_pass"] = len(canonical) == len(set(canonical))
                measured["service_semantic_pass"] &= measured["bounded_generation_metrics_pass"] and measured.get("unique_requirement_pass", True)
            save(folder / "evaluation.json", measured)
            receipt = {"case_id": case["case_id"], "started_at": started_at, "elapsed_seconds": elapsed,
                       "http_status": response.status_code, "service_semantic_pass": measured["service_semantic_pass"],
                       "image": args.image, "scientific_coverage": measured.get("scientific_coverage"),
                       "result_sha256": hashlib.sha256((folder / "result.json").read_bytes()).hexdigest()}
            save(folder / "receipt.json", receipt)
            receipts.append(receipt)
            save(args.output / "summary.json", {"scope": "isolated exact-image runtime regression on observed GPU; not public, customer, cold-start, snapshot or scientific-efficacy qualification",
                "identity": identity, "image": args.image, "source_manifest_sha256": hashlib.sha256(source).hexdigest(),
                "planned_cases": len(cases), "completed_cases": len(receipts), "results": receipts})
            print(json.dumps(receipt), flush=True)
    return 0 if all(item["service_semantic_pass"] for item in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
