#!/usr/bin/env python3
"""Prepare actual cross-model design/refolding cases from completed artifacts.

No inference is submitted. Original operation results and manifests are never
modified. Missing backbone positions remain explicit blockers rather than
silently shortening or filling a scientist's designed sequence.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from datasets import digest, write_json
from evaluators import (design_input_chains, evaluate, extract_structures,
                        fasta_records, parse_chain, protein_chain_ids, unwrap)


def provenance(source: dict, receipt: dict, result_bytes: bytes) -> dict:
    return {**copy.deepcopy(source["provenance"]), "upstream_case_id": source["case_id"],
            "upstream_model_id": source["model_id"], "upstream_operation_id": receipt["operation_id"],
            "upstream_result_sha256": digest(result_bytes),
            "protocol_deviation": "Cross-model computational backbone-design recovery, not paper reproduction or experimental binding. Known positional correspondence includes every redesigned amino acid; no sequence-identity-only fit."}


def prepare_refolding(source: dict, receipt: dict, result_bytes: bytes, reference: str,
                      reference_chain: str, sequence: str, index: int, output: Path) -> dict:
    if set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
        raise ValueError("Unresolved/noncanonical sequence requires an explicit downstream gap policy.")
    if len(parse_chain(reference, reference_chain)["sequence"]) != len(sequence):
        raise ValueError("Complete residue-position correspondence is unavailable; not silently aligned or truncated.")
    case_id = f"refold-{source['case_id']}-design{index + 1}"
    folder = output / "sources" / case_id
    folder.mkdir(parents=True, exist_ok=True)
    reference_path, input_path = folder / "source-backbone.pdb", folder / "input.json"
    reference_path.write_text(reference)
    write_json(input_path, {"sequences": [{"id": "A", "sequence": sequence, "type": "protein"}]})
    return {"case_id": case_id, "persona": "protein-design-researcher", "model_id": "esmfold2-fast",
        "tool": "submit_esmfold2_fast", "mode": "scientific-batch",
        "arguments": {"schema": "fs2-serve.nebius.ai/scientific-run-request/v1", "operation": "predict-protein-structure",
                      "service_class": "customer-batch", "parameters": {"sequence": sequence, "mode": "single-sequence", "seed": 1}},
        "preparation": {"inputs": [{"name": "esmfold2-fast-input", "semantic_type": "esmfold2-fast-input-json/v1",
            "local_path": str(input_path.relative_to(output)), "media_type": "application/json", "compression": "none",
            "sha256": digest(input_path.read_bytes()), "size_bytes": input_path.stat().st_size}]},
        "expected": {"evaluator": "backbone_recovery", "reference_path": str(reference_path.relative_to(output)),
                     "reference_chain": reference_chain, "input_sequence": sequence},
        "provenance": {**provenance(source, receipt, result_bytes), "reference_sha256": digest(reference.encode()),
                       "designed_sequence_sha256": digest(sequence.encode()), "source_sample_index": index},
        "workload": {"unique_input_id": source["workload"]["unique_input_id"], "seed": 1, "repetition": 1,
                     "priority": "batch", "parent_case_id": source["case_id"]}}


def prepare_inverse_folding(source: dict, receipt: dict, result_bytes: bytes,
                            structure: str, index: int, output: Path) -> dict:
    chains = design_input_chains(structure)
    if len(chains) != 1 or chains[0]["incomplete_backbone_positions_1based"]:
        raise ValueError("Initial generated-backbone study requires one complete N/CA/C/O chain.")
    case_id = f"inverse-{source['case_id']}-backbone{index + 1}"
    path = output / "sources" / case_id / "input.pdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(structure)
    return {"case_id": case_id, "persona": "protein-design-researcher", "model_id": "proteinmpnn",
        "tool": "infer_proteinmpnn_native", "mode": "native",
        "arguments": {"input_pdb": structure, "input_pdb_chains": [chains[0]["chain_id"]],
            "num_seq_per_target": 4, "random_seed": 1, "sampling_temp": 0.1, "omit_AAs": ["X"]},
        "expected": {"evaluator": "protein_sequence_design", "input_sequence": chains[0]["sequence"],
                     "num_sequences": 4, "omit_AAs": ["X"]},
        "preparation": {"artifact_fields": [{"argument_path": "input_pdb", "local_path": str(path.relative_to(output)),
                                              "media_type": "chemical/x-pdb"}]},
        "provenance": provenance(source, receipt, result_bytes),
        "workload": {"unique_input_id": case_id, "seed": 1, "repetition": 1, "priority": "batch"},
        "followups": [{"model_id": "esmfold2-fast", "mode": "independent-backbone-recovery"}]}


def prepare(manifest: Path, results: list[Path], output: Path) -> dict:
    if output.exists():
        raise ValueError("Use a fresh versioned output directory; consumed manifests are immutable.")
    source_cases = {case["case_id"]: case for case in json.loads(manifest.read_text())["cases"]}
    prepared, notes, seen = [], [], set()
    for root in results:
        for path in sorted(root.rglob("receipt.json")):
            receipt = json.loads(path.read_text())
            source = source_cases.get(receipt.get("case_id"))
            if not source or source["model_id"] not in {"proteinmpnn", "mosaic", "rfdiffusion"}:
                continue
            if source["model_id"] == "proteinmpnn" and source["workload"].get("seed") != 1:
                continue  # Declared design study uses all temperatures at seed1, not post-hoc cherry-picking.
            if source["case_id"] in seen:
                raise ValueError("Duplicate source operation across result roots; choose an explicit cohort.")
            seen.add(source["case_id"])
            note = {"source_case_id": source["case_id"], "source_receipt": str(path)}
            if receipt.get("state") != "verified":
                notes.append({**note, "status": "upstream_not_verified", "state": receipt.get("state")})
                continue
            try:
                result_bytes = (path.parent / "result.json").read_bytes()
                result = json.loads(result_bytes)
                if not evaluate(source, result, manifest.parent)["service_semantic_pass"]:
                    raise ValueError("Current independent upstream semantic evaluation failed.")
                cases = []
                if source["model_id"] == "proteinmpnn":
                    reference = source["arguments"]["input_pdb"]
                    chains = design_input_chains(reference, source["arguments"].get("input_pdb_chains"))
                    if len(chains) != 1 or chains[0]["incomplete_backbone_positions_1based"]:
                        raise ValueError("Partial experimental backbone needs explicit gap policy; excluded from complete-backbone recovery cohort, retained here.")
                    rows = [(header, sequence) for header, sequence in fasta_records(unwrap(result)["mfasta"])
                            if not header.startswith("input ")]
                    for index, (_, sequence) in enumerate(rows):
                        cases.append(prepare_refolding(source, receipt, result_bytes, reference,
                                                       chains[0]["chain_id"], sequence, index, output))
                else:
                    for index, structure in enumerate(extract_structures(result)):
                        if source["model_id"] == "rfdiffusion":
                            cases.append(prepare_inverse_folding(source, receipt, result_bytes, structure, index, output))
                        else:
                            chains = protein_chain_ids(structure)
                            if len(chains) != 1:
                                raise ValueError("Mosaic binder-only study requires an unambiguous binder chain.")
                            sequence = parse_chain(structure, chains[0])["sequence"]
                            cases.append(prepare_refolding(source, receipt, result_bytes, structure, chains[0], sequence, index, output))
                prepared.extend(cases)
                notes.append({**note, "status": "prepared", "cases": len(cases),
                              "operation_id": receipt["operation_id"], "result_sha256": digest(result_bytes)})
            except (ValueError, KeyError, OSError) as error:
                notes.append({**note, "status": "blocked_preparation", "error": str(error)})
    document = {"schema_version": 1, "study_id": "cross-model-design-recovery-v1",
                "created_at": datetime.now(timezone.utc).isoformat(), "source_manifest": str(manifest),
                "source_manifest_sha256": digest(manifest.read_bytes()), "preparations": notes, "cases": prepared}
    write_json(output / "cases.json", document)
    return {"manifest": str(output / "cases.json"), "cases": len(prepared), "preparations": notes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.manifest, args.results, args.output)
    print(json.dumps({"manifest": result["manifest"], "cases": result["cases"],
                      "prepared_sources": sum(row["status"] == "prepared" for row in result["preparations"]),
                      "nonprepared_sources": [row for row in result["preparations"] if row["status"] != "prepared"]}, indent=2))
