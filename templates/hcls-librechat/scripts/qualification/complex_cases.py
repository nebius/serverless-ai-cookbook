#!/usr/bin/env python3
"""Prepare experimentally referenced, non-pathogenic heteromer studies."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from datasets import digest, fetch, protein_chain, write_json
from evaluators import complex_metrics, parse_chain


COMPLEXES = [
    ("1BRS", [("1", "A"), ("2", "D")], "Barnase-barstar"),
    ("2PTC", [("1", "E"), ("2", "I")], "Trypsin-pancreatic trypsin inhibitor"),
    ("1ACB", [("1", "E"), ("2", "I")], "Chymotrypsin-eglin C"),
]


def prepare(spec: tuple, output: Path) -> list[dict]:
    pdb_id, chain_entities, label = spec
    folder = output / "references" / pdb_id.lower()
    pdb_data, source = fetch(f"https://files.rcsb.org/download/{pdb_id}.pdb", folder / "source.pdb")
    chains, pieces, sources = [], [], [source]
    for entity, chain in chain_entities:
        raw, source = fetch(f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity}", folder / f"entity-{entity}.json")
        metadata = json.loads(raw)
        if chain not in metadata["rcsb_polymer_entity_container_identifiers"]["auth_asym_ids"]:
            raise ValueError("Experimental chain/entity mismatch.")
        sequence = "".join(metadata["entity_poly"]["pdbx_seq_one_letter_code_can"].split())
        if set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
            raise ValueError("Non-canonical protein sequence needs a separately specified protocol.")
        chains.append({"reference_chain": chain, "input_sequence": sequence})
        pieces.append(protein_chain(pdb_data.decode(), chain).removesuffix("END\n"))
        sources.append(source)
    reference = "".join(pieces) + "END\n"
    reference_path = folder / "reference-complex.pdb"
    reference_path.write_text(reference)
    # Validate that these crystallographic chains form an actual interface.
    reference_expected = {"chains": [{**chain, "input_sequence": parse_chain(reference, chain["reference_chain"])["sequence"]}
                                     for chain in chains]}
    reference_metrics = complex_metrics(reference, reference, reference_expected)
    for source in sources:
        source["path"] = str(Path(source["path"]).relative_to(output))
    expected = {"evaluator": "protein_complex", "reference_path": str(reference_path.relative_to(output)), "chains": chains}
    provenance = {"dataset_id": f"rcsb-complex-{pdb_id.lower()}", "pdb_id": pdb_id, "label": label,
                  "source_url": f"https://www.rcsb.org/structure/{pdb_id}", "license": "CC0", "sources": sources,
                  "native_ca_interface_contacts": reference_metrics["native_ca_contacts"],
                  "protocol_deviation": "Two protein chains; query-only or no MSA, no templates, no crystal coordinates in model input. Historical training overlap unknown. C-alpha interface metrics are not DockQ/CAPRI; not paper reproduction."}
    cases = []
    for repetition, seed in enumerate((1, 7, 42), 1):
        for model in ("boltz2", "openfold3", "protenix-v2", "openfold3-openbind", "alphafold3"):
            case_id = f"{model}-{pdb_id.lower()}-heteromer-s{seed}"
            case = {"case_id": case_id, "persona": "protein-interaction-researcher", "model_id": model,
                    "expected": copy.deepcopy(expected), "provenance": copy.deepcopy(provenance),
                    "workload": {"unique_input_id": f"rcsb-complex-{pdb_id.lower()}", "repetition": repetition,
                                 "seed": seed, "priority": "batch"}}
            seqs = [chain["input_sequence"] for chain in chains]
            if model == "boltz2":
                case.update(tool="boltz2_predict_native", mode="native", arguments={
                    "polymers": [{"id": name, "molecule_type": "protein", "sequence": sequence,
                                  "msa": {"msa_search": {"a3m": {"alignment": f">query\n{sequence}\n"}}}}
                                 for name, sequence in zip(("A", "B"), seqs)],
                    "recycling_steps": 3, "sampling_steps": 200, "diffusion_samples": 1, "output_format": "mmcif"})
                case["workload"]["seed"] = None
            elif model == "openfold3":
                case.update(tool="infer_openfold3_native", mode="native", arguments={"request_id": case_id,
                    "inputs": [{"input_id": case_id, "output_format": "cif", "molecules": [
                        {"type": "protein", "id": name, "sequence": sequence} for name, sequence in zip(("A", "B"), seqs)]}]})
                case["workload"]["seed"] = 42
                case["provenance"]["protocol_deviation"] += " Preview2 repeats use fixed seed42, not independent seeds."
            else:
                if model == "protenix-v2":
                    name, semantic = "protenix-input", "protenix-input-json/v1"
                    document = [{"name": case_id, "sequences": [{"proteinChain": {"count": 1, "sequence": sequence}} for sequence in seqs]}]
                    parameters = {"checkpoint": "protenix-v2", "msa_mode": "none", "sample_count": 1, "model_seeds": [seed]}
                elif model == "openfold3-openbind":
                    name, semantic = "openfold3-input", "openfold3-input-json/v1"
                    document = {"queries": {case_id: {"chains": [{"chain_ids": [name], "molecule_type": "protein", "sequence": sequence}
                                                             for name, sequence in zip(("A", "B"), seqs)]}}}
                    parameters = {"msa_mode": "none", "model_seeds": [seed]}
                else:
                    name, semantic = "fold-input", "alphafold3-fold-input/v1"
                    document = {"dialect": "alphafold3", "version": 2, "name": case_id, "modelSeeds": [seed], "sequences": [
                        {"protein": {"id": name, "sequence": sequence, "unpairedMsa": f">query\n{sequence}\n", "pairedMsa": "", "templates": []}}
                        for name, sequence in zip(("A", "B"), seqs)]}
                    parameters = {"input_mode": "raw"}
                input_path = folder / f"{case_id}-input.json"
                write_json(input_path, document)
                case.update(tool="submit_" + model.replace("-", "_"), mode="scientific-batch", arguments={
                    "schema": "fs2-serve.nebius.ai/scientific-run-request/v1", "operation": "predict-complex-structure",
                    "service_class": "customer-batch", "parameters": parameters}, preparation={"inputs": [
                        {"name": name, "semantic_type": semantic, "local_path": str(input_path.relative_to(output)),
                         "media_type": "application/json", "compression": "none", "sha256": digest(input_path.read_bytes()),
                         "size_bytes": input_path.stat().st_size}]})
            cases.append(case)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cases, preparations = [], []
    for spec in COMPLEXES:
        try:
            prepared = prepare(spec, args.output)
            cases.extend(prepared)
            preparations.append({"pdb_id": spec[0], "status": "prepared", "cases": len(prepared)})
        except Exception as error:
            preparations.append({"pdb_id": spec[0], "status": "blocked_preparation", "error": str(error)})
    manifest = {"schema_version": 1, "study_id": "experimental-heteromer-v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "preparations": preparations, "cases": cases}
    write_json(args.output / "cases.json", manifest)
    print(json.dumps({"manifest": str(args.output / "cases.json"), "cases": len(cases), "preparations": preparations}, indent=2))


if __name__ == "__main__":
    main()
