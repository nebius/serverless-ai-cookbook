"""Freeze multi-chain inverse-folding cases from existing public references.

No downloads or inference. These test chain selection, requested omissions,
sample cardinality and missing-position handling, not binding or efficacy.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from evaluators import design_input_chains
from manage_campaign import save


def prepare(source, output):
    previous = json.loads(source.read_text())
    references = {}
    for case in previous["cases"]:
        references.setdefault(case["provenance"]["pdb_id"], case)
    cases = []
    for pdb_id, reference in sorted(references.items()):
        path = source.parent / reference["expected"]["reference_path"]
        raw = path.read_bytes()
        text = raw.decode()
        chains = design_input_chains(text)
        ids = [chain["chain_id"] for chain in chains]
        if len(ids) != 2:
            raise ValueError("This frozen matrix requires exactly two reference chains")
        for label, selected in [("all", None), ("first", [ids[0]]), ("second", [ids[1]]), ("reversed", ids[::-1])]:
            for seed in (7, 42):
                for omissions in (["X"], ["X", "C"]):
                    expected_chains = design_input_chains(text, selected)
                    case_id = f"proteinmpnn-{pdb_id.lower()}-{label}-s{seed}-omit{''.join(omissions)}"
                    provenance = copy.deepcopy(reference["provenance"])
                    provenance["protocol_deviation"] = "Inverse folding of crystallographic coordinates, not de novo structure prediction; selected chains redesigned in the unchanged full-complex context. No binding/efficacy claim."
                    provenance["input_sha256"] = hashlib.sha256(raw).hexdigest()
                    cases.append({"case_id": case_id, "persona": "protein-design-researcher",
                        "model_id": "proteinmpnn", "tool": "infer_proteinmpnn_native", "mode": "native",
                        "arguments": {"input_pdb": text, "input_pdb_chains": selected, "random_seed": seed,
                                      "num_seq_per_target": 4, "sampling_temp": 0.3, "omit_AAs": omissions},
                        "preparation": {"artifact_fields": [{"argument_path": "input_pdb", "local_path": str(path.resolve()),
                                                             "media_type": "chemical/x-pdb"}]},
                        "expected": {"evaluator": "protein_sequence_design", "input_sequence": "".join(c["sequence"] for c in expected_chains),
                                     "num_sequences": 4, "omit_AAs": omissions},
                        "provenance": provenance,
                        "workload": {"unique_input_id": "rcsb-complex-" + pdb_id.lower(), "seed": seed,
                                     "repetition": 1, "priority": "batch"}})
    save(output, {"schema_version": 1, "study_id": "public-multichain-inverse-folding",
                  "source_manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "cases": cases})
    print(json.dumps({"cases": len(cases), "distinct_crystal_complexes": len(references), "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.source, arguments.output)
