#!/usr/bin/env python3
"""Prepare matched downstream cases from completed scientific operations.

No inference is submitted. Original receipts and artifacts remain unchanged.
Only completed, independently validated upstream results enter the manifest.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from datasets import digest, write_json
from evaluators import evaluate, fasta_records, unwrap


def stage_reference(case: dict, source_root: Path, output: Path) -> None:
    relative = Path(case["expected"]["reference_path"])
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_root / relative, target)


def msa_followups(source: dict, result: dict, templates: dict, source_root: Path,
                  output: Path, operation_id: str) -> list[dict]:
    evaluation = evaluate(source, result, source_root)
    if not evaluation["service_semantic_pass"]:
        raise ValueError("Upstream MSA failed independent sequence/alignment validation.")
    if not evaluation["can_support_downstream_comparison"]:
        raise ValueError("MSA contains only the query or duplicate rows; retain as uninformative, not real-MSA evidence.")
    alignment = unwrap(result)["alignments"]["pdb70_220313"]["a3m"]["alignment"]
    a3m_rows = fasta_records(alignment)
    sequence = source["arguments"]["sequence"]
    pdb_id = source["provenance"]["pdb_id"].lower()
    depth = source["arguments"]["max_msa_sequences"]
    cases = []
    for model in ("boltz2", "openfold3", "esmfold2"):
        template = next((case for case in templates.values() if case["model_id"] == model and
                         case["provenance"].get("pdb_id", "").lower() == pdb_id and
                         case["workload"].get("repetition") == 1), None)
        if template is None:
            raise ValueError(f"Missing matched query-only baseline for {model}/{pdb_id}.")
        case = copy.deepcopy(template)
        case_id = f"{model}-{pdb_id}-pdb70-depth{depth}"
        case["case_id"] = case_id
        case.pop("preparation", None)
        folder = output / "upstream-msa" / f"{pdb_id}-depth{depth}"
        folder.mkdir(parents=True, exist_ok=True)
        alignment_path = folder / "alignment.a3m"
        alignment_path.write_text(alignment)
        if model == "boltz2":
            case["arguments"]["polymers"][0]["msa"]["msa_search"]["a3m"]["alignment"] = alignment
        elif model == "openfold3":
            case["arguments"]["request_id"] = case_id
            case["arguments"]["inputs"][0]["input_id"] = case_id
            case["arguments"]["inputs"][0]["molecules"][0]["msa"] = {
                "main": {"a3m": {"alignment": alignment, "format": "a3m"}}}
        else:
            # The deployed ESM wrapper expects aligned row strings, not A3M
            # headers or lowercase insertions. Query-column gaps are retained.
            rows = ["".join(letter for letter in row if not letter.islower() and letter != ".")
                    for _, row in a3m_rows]
            raw_path = folder / "esmfold2-input.json"
            write_json(raw_path, {"sequence": sequence, "msa_sequences": rows})
            case["arguments"]["parameters"]["mode"] = "precomputed-msa"
            case["preparation"] = {"inputs": [{"name": "esmfold2-input", "semantic_type": "esmfold2-input-json/v1",
                "local_path": str(raw_path.relative_to(output)), "media_type": "application/json", "compression": "none",
                "sha256": digest(raw_path.read_bytes()), "size_bytes": raw_path.stat().st_size}]}
        stage_reference(case, source_root, output)
        case["provenance"].update(upstream_operation_id=operation_id,
            upstream_case_id=source["case_id"], upstream_alignment_sha256=digest(alignment.encode()),
            alignment_rows=len(a3m_rows), alignment_path=str(alignment_path.relative_to(output)),
            protocol_deviation="Local PDB70 supplied MSA; no templates. Matched query-only baseline uses identical sequence/settings. Historical structure/training overlap unknown; not paper reproduction.")
        case["workload"].update(priority="batch", matched_baseline=template["case_id"])
        cases.append(case)
    return cases


def prepare(manifest_path: Path, results_root: Path, output: Path) -> dict:
    original = json.loads(manifest_path.read_text())
    templates = {case["case_id"]: case for case in original["cases"]}
    cases, receipts, seen = [], [], set()
    for path in sorted(results_root.rglob("receipt.json")):
        receipt = json.loads(path.read_text())
        case_id = receipt.get("case_id")
        source = templates.get(case_id)
        if not source or source["model_id"] != "msa-search-pdb70" or case_id in seen:
            continue
        if receipt.get("state") != "verified":
            receipts.append({"case_id": case_id, "status": "upstream_not_verified", "state": receipt.get("state")})
            continue
        try:
            result = json.loads((path.parent / "result.json").read_text())
            prepared = msa_followups(source, result, templates, manifest_path.parent, output, receipt["operation_id"])
            cases.extend(prepared)
            seen.add(case_id)
            receipts.append({"case_id": case_id, "status": "prepared", "downstream_cases": len(prepared),
                             "source_receipt": str(path), "result_sha256": digest((path.parent / "result.json").read_bytes())})
        except (ValueError, OSError, KeyError) as error:
            receipts.append({"case_id": case_id, "status": "blocked_preparation", "error": str(error)})
    result = {"schema_version": 1, "study_id": "matched-pdb70-msa-followups-v1",
              "created_at": datetime.now(timezone.utc).isoformat(), "source_manifest": str(manifest_path),
              "source_manifest_sha256": digest(manifest_path.read_bytes()), "preparations": receipts, "cases": cases}
    write_json(output / "cases.json", result)
    return {"manifest": str(output / "cases.json"), "cases": len(cases), "preparations": receipts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.results, args.output), indent=2))


if __name__ == "__main__":
    main()
