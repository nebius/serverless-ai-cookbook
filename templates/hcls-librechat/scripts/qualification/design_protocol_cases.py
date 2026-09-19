"""Freeze benign, source-backed missing design protocols; never submit work."""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

import gemmi
import yaml

from datasets import fetch, write_json
from evaluators import parse_chain

REVISION = "31d9d9b9c72245b4ed6fe8742d6fbf4e1a3552a0"
RFD_REVISION = "9273ef67335acaf91df0150473a274759229cdf6"
AA = "[ACDEFGHIKLMNPQRSTVWY]"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def indices(value, size):
    if value == "all":
        return set(range(1, size + 1))
    result = set()
    for item in str(value).split(","):
        ends = [int(x) for x in item.split("..")]
        result.update(range(ends[0], ends[-1] + 1))
    return result


def polymer_sequence(path, label_chain):
    structure = gemmi.read_structure(str(path))
    entities = [e for e in structure.entities if label_chain in e.subchains and e.full_sequence]
    if len(entities) != 1:
        raise ValueError("Expected one pinned polymer entity for label chain")
    sequence = "".join(gemmi.find_tabulated_residue(r).one_letter_code for r in entities[0].full_sequence)
    if set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
        raise ValueError("Noncanonical framework needs an explicit policy")
    return sequence


def framework_pattern(sequence, config, chain):
    """Independent mask/insertions interpretation of pinned upstream YAML."""
    def selected(key, fallback):
        rows = [i["chain"] for i in config.get(key, []) if i["chain"]["id"] == chain]
        return set().union(*(indices(r.get("res_index", "all"), len(sequence)) for r in rows)) if rows else fallback
    included = selected("include", set(range(1, len(sequence) + 1)))
    excluded, designed = selected("exclude", set()), selected("design", set())
    insertions = {r["insertion"]["res_index"]: r["insertion"]["num_residues"]
                  for r in config.get("design_insertions", []) if r["insertion"]["id"] == chain}
    pieces = []
    for position, aa in enumerate(sequence, 1):
        if position in insertions:
            lengths = indices(insertions[position], len(sequence))
            pieces.append(AA + "{" + str(min(lengths)) + "," + str(max(lengths)) + "}")
        if position in included and position not in excluded:
            pieces.append(AA if position in designed else re.escape(aa))
    return "".join(pieces)


def bundle(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(files.items()):
            info = tarfile.TarInfo("design-specs/" + name)
            info.size, info.mode, info.mtime = len(raw), 0o644, 0
            archive.addfile(info, io.BytesIO(raw))
    return gzip.compress(stream.getvalue(), mtime=0)


def prepare(backend, upstream, output):
    if output.exists():
        raise ValueError("Use a fresh output directory; frozen manifests are immutable")
    output.mkdir(parents=True)
    base = backend / "models/cancer-immunotherapy/runtime-images"
    source = output / "sources"
    source.mkdir()
    provenance = []
    def retained(path, name, origin):
        raw = path.read_bytes()
        target = source / name
        target.write_bytes(raw)
        provenance.append({"path": str(target.relative_to(output)), "sha256": digest(raw),
                           "size_bytes": len(raw), "source": origin})
        return raw
    pdl1 = retained(base / "boltzgen/activation/5J89-chain-A.cif", "5J89-chain-A.cif",
                    "Retained chain-A projection of public RCSB 5J89, unchanged campaign fixture")
    ubq = retained(base / "rfdiffusion/contract/fixtures/scaffold-motif/1UBQ.pdb", "1UBQ.pdb",
                   "https://files.rcsb.org/download/1UBQ.pdb")
    if digest(ubq) != "d4a6812d8951cf6594e6a0763f089e35f5a80b62acb3c117b2c5565228a7b161":
        raise ValueError("Retained motif fixture differs from its pinned identity")
    target_sequence = polymer_sequence(source / "5J89-chain-A.cif", "A")
    target = {"path": "5J89-chain-A.cif", "include": [{"chain": {"id": "A"}}]}
    definitions = []
    definitions.append(("peptide-anything", {"entities": [{"protein": {"id": "C", "sequence": "12..20"}},
        {"file": copy.deepcopy(target)}]}, {"5J89-chain-A.cif": pdl1},
        {"target_sequence": target_sequence, "designed_patterns": [AA + "{12,20}"]}))
    small_path = "example/protein_binding_small_molecule/chorismite.yaml"
    small_raw = retained(upstream / small_path, "chorismite.yaml", "https://raw.githubusercontent.com/HannesStark/boltzgen/" + REVISION + "/" + small_path)
    ccd_raw, ccd_provenance = fetch("https://files.rcsb.org/ligands/download/TSA.cif", source / "TSA.cif")
    ccd_provenance["path"] = str((source / "TSA.cif").relative_to(output))
    provenance.append(ccd_provenance)
    ccd = gemmi.cif.read_string(ccd_raw.decode()).sole_block()
    heavy = sorted([str(row[0]), str(row[1])] for row in ccd.find(["_chem_comp_atom.atom_id", "_chem_comp_atom.type_symbol"]) if row[1] != "H")
    definitions.append(("protein-small_molecule", yaml.safe_load(small_raw), {},
        {"designed_patterns": [AA + "{140,180}"], "ligand_ccd": "TSA", "ligand_heavy_atoms": heavy}))
    for protocol, directory, stem, chains in [("nanobody-anything", "nanobody_scaffolds", "7xl0", ["A"]),
                                            ("antibody-anything", "fab_scaffolds", "dupilumab.6wgb", ["A", "B"])]:
        files = {"5J89-chain-A.cif": pdl1}
        for extension in ("yaml", "cif"):
            relative = f"example/{directory}/{stem}.{extension}"
            files[f"{stem}.{extension}"] = retained(upstream / relative, f"{stem}.{extension}",
                "https://raw.githubusercontent.com/HannesStark/boltzgen/" + REVISION + "/" + relative)
        scaffold = yaml.safe_load(files[f"{stem}.yaml"])
        patterns = [framework_pattern(polymer_sequence(source / f"{stem}.cif", chain), scaffold, chain) for chain in chains]
        definitions.append((protocol, {"entities": [{"file": copy.deepcopy(target)}, {"file": {"path": f"{stem}.yaml"}}]},
                            files, {"target_sequence": target_sequence, "designed_patterns": patterns,
                                    "framework_source": f"sources/{stem}.cif"}))
    sequence = parse_chain(ubq.decode(), "A")["sequence"]
    redesign = {"path": "1UBQ.pdb", "include": [{"chain": {"id": "A"}}],
        "design": [{"chain": {"id": "A", "res_index": "7..11"}}],
        "structure_groups": [{"group": {"id": "A", "visibility": 2}},
                             {"group": {"id": "A", "visibility": 0, "res_index": "7..11"}}]}
    definitions.append(("protein-redesign", {"entities": [{"file": redesign}]}, {"1UBQ.pdb": ubq},
        {"designed_patterns": [framework_pattern(sequence, redesign, "A")], "fixed_reference": "sources/1UBQ.pdb",
         "fixed_chain": "A", "fixed_positions_1based": [i for i in range(1, 77) if not 7 <= i <= 11], "fixed_ca_rmsd_limit": 1.5}))
    cases = []
    for protocol, spec, files, constraints in definitions:
        case_id = "boltzgen-" + protocol + "-coverage-r1"
        files["protocol.yaml"] = yaml.safe_dump(spec, sort_keys=False).encode()
        raw = bundle(files)
        path = output / "inputs" / (case_id + ".tar.gz")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        cases.append({"case_id": case_id, "model_id": "boltzgen", "persona": "protein-design-methods-researcher",
            "tool": "submit_boltzgen", "mode": "scientific-batch", "arguments": {
                "schema": "fs2-serve.nebius.ai/scientific-run-request/v1", "operation": "design-binders", "service_class": "customer-batch",
                "parameters": {"protocol": protocol, "batches": [{"shard_id": "protocol", "num_designs": 20, "budget": 1, "reuse_completed": False}]}},
            "preparation": {"inputs": [{"name": "campaign-input", "semantic_type": "boltzgen-campaign-input/v1",
                "local_path": str(path.relative_to(output)), "media_type": "application/gzip", "compression": "gzip",
                "sha256": digest(raw), "size_bytes": len(raw)}]},
            "expected": {"evaluator": "design_protocol", "protocol": protocol, "minimum_structures": 1, **constraints},
            "provenance": {"source_revision": REVISION, "sources": copy.deepcopy(provenance),
                "protocol_deviation": "Bounded20candidate/1winner computational coverage, original filters retained. Pinned antibody scaffolds adapted to PD-L1; redesign uses benign ubiquitin. Not paper reproduction or binding evidence."},
            "workload": {"unique_input_id": protocol, "repetition": 1, "priority": "batch"}})
    request = json.loads((base / "rfdiffusion/contract/fixtures/scaffold-motif/request.json").read_text())
    del request["parameters"]["input_pdb_artifact_id"]
    cases.append({"case_id": "rfdiffusion-ubiquitin-motif-s9100", "model_id": "rfdiffusion", "persona": "protein-design-methods-researcher",
        "tool": "submit_rfdiffusion", "mode": "scientific-batch", "arguments": request,
        "preparation": {"artifact_id_parameters": {"input_pdb_artifact_id": "target_structure"}, "inputs": [{
            "name": "target_structure", "semantic_type": "protein-structure-pdb/v1", "local_path": "sources/1UBQ.pdb",
            "media_type": "chemical/x-pdb", "compression": "none", "sha256": digest(ubq), "size_bytes": len(ubq)}]},
        "expected": {"evaluator": "design_protocol", "protocol": "scaffold-motif", "minimum_structures": 1,
            "reference_path": "sources/1UBQ.pdb", "reference_chain": "A", "reference_residue_ids": list(range(23, 35)),
            "output_motif_positions_1based": list(range(11, 23)), "total_residues": 32, "motif_ca_rmsd_limit": 1.5},
        "provenance": {"source_revision": RFD_REVISION, "source_sha256": digest(ubq),
            "protocol_deviation": "Pinned ubiquitin motif plus explicit10residue flanks; geometric preservation, not fold/function qualification."},
        "workload": {"unique_input_id": "1UBQ-A23-34", "seed": 9100, "repetition": 1, "priority": "batch"}})
    write_json(output / "cases.json", {"schema_version": 1, "study_id": "design-protocol-coverage-v1", "cases": cases})
    return {"manifest": str(output / "cases.json"), "cases": len(cases), "sha256": digest((output / "cases.json").read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.backend, args.upstream, args.output)))
