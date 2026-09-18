#!/usr/bin/env python3
"""Inspect retained Proteina handoff bytes without extracting archive paths.

Role association follows each source CSV row, never presumed filename order.
This performs no model inference and does not modify original evidence.
"""
import argparse
import csv
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

from evaluators import backbone_recovery_metrics, design_metrics, parse_chain, protein_chain_ids


def audit(path: Path, expected_sha256: str) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Handoff digest differs from supplied retained artifact identity.")
    archive = tarfile.open(fileobj=BytesIO(subprocess.check_output(["zstd", "-dc", str(path)])))
    members = {member.name.removeprefix("./"): member for member in archive.getmembers() if member.isfile()}

    def content(name: str) -> str:
        normalized = name.removeprefix("./")
        if PurePosixPath(normalized).is_absolute() or ".." in PurePosixPath(normalized).parts:
            raise ValueError("CSV path is not an archive-relative member.")
        member = members[normalized]
        if member.size > 10_000_000:
            raise ValueError("Unexpectedly large text evidence member.")
        return archive.extractfile(member).read().decode()

    results = []
    for name in sorted(members):
        if not name.endswith(".csv") or "/binder_results_" not in name:
            continue
        for row in csv.DictReader(StringIO(content(name))):
            raw, refolded = content(row["pdb_path"]), content(row["self_complex_pdb_path"])
            raw_chains, folded_chains = protein_chain_ids(raw), protein_chain_ids(refolded)
            binder = sorted(raw_chains)[-1]
            sequence = row["self_sequence"]
            matched = [chain for chain in folded_chains if parse_chain(refolded, chain)["sequence"] == sequence]
            if len(matched) != 1 or parse_chain(raw, binder)["sequence"] != sequence:
                raise ValueError("Raw/refolded/CSV binder sequences do not uniquely match.")
            raw_binder, folded_binder = parse_chain(raw, binder), parse_chain(refolded, matched[0])
            # Shared metric primitive requires one prediction chain; compare
            # selected coordinates directly without rewriting source structures.
            import numpy as np
            from evaluators import fit_coordinates, ca_lddt
            fitted = fit_coordinates(raw_binder["coordinates"], folded_binder["coordinates"])
            rmsd = float(np.sqrt(np.mean(np.sum((raw_binder["coordinates"] - fitted) ** 2, axis=1))))
            results.append({"source_csv": name, "id_gen": row["id_gen"],
                "raw_member": row["pdb_path"].removeprefix("./"),
                "refolded_member": row["self_complex_pdb_path"].removeprefix("./"),
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "refolded_sha256": hashlib.sha256(refolded.encode()).hexdigest(),
                "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                "sequence_exact_across_roles": True,
                "raw_geometry": design_metrics(raw, {"binder_chain": binder}),
                "refolded_geometry": design_metrics(refolded, {"binder_chain": matched[0]}),
                "independent_binder_ca_rmsd_angstrom": rmsd,
                "csv_binder_ca_rmsd_angstrom": float(row["self_binder_scRMSD_ca"]),
                "rmsd_absolute_difference_angstrom": abs(rmsd - float(row["self_binder_scRMSD_ca"])),
                "ca_lddt_between_raw_and_refolded": ca_lddt(raw_binder["coordinates"], folded_binder["coordinates"]),
                "reported_refold_confidence": {key: float(row[key]) for key in ("self_complex_pLDDT", "self_complex_i_pTM")},
                "evaluation_config_generation_steps": int(row["generation_args_nsteps"]),
                "actual_generation_steps": "not established by separately loaded evaluation defaults",
                "refold_role": "AF2-Multimer prediction; no Amber relaxation claim"})
    return {"handoff_sha256": digest, "designs": results, "gpu_rerun": False,
            "source_revision": "54058860d43444c7289873f77d3e50b5b02348cd",
            "scope": "retained artifact-role and geometry audit; not binding efficacy or release qualification"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.handoff, args.sha256)
    if args.output.exists():
        raise SystemExit("Refusing to replace retained audit evidence.")
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "designs": len(result["designs"]),
                      "refold_geometry_pass": [row["refolded_geometry"]["constraint_pass"] for row in result["designs"]],
                      "rmsd_difference": [row["rmsd_absolute_difference_angstrom"] for row in result["designs"]]}))
