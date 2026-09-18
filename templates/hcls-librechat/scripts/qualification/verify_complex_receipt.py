#!/usr/bin/env python3
"""Independently verify a workbench complex receipt from downloaded coordinates.

This qualifier uses Gemmi and the campaign's independent alignment/Kabsch code,
not the customer's structure-analysis helper. It checks the explicitly stated
5-A heavy-atom contact convention, not DockQ or biological binding efficacy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import gemmi
import numpy as np
from Bio.SeqUtils import seq1

from evaluators import fit_coordinates, sequence_pairs, sha256


def chain_residues(path: Path, chain_id: str) -> list[dict]:
    structure = gemmi.read_structure(str(path))
    chain = structure[0][chain_id]
    result = []
    for residue in chain:
        if residue.het_flag != "A" and residue.name != "MSE":
            continue
        by_name = {}
        for atom in residue:
            if atom.element.is_hydrogen:
                continue
            if atom.name not in by_name or atom.occ > by_name[atom.name].occ:
                by_name[atom.name] = atom
        if "CA" not in by_name:
            continue
        xyz = lambda atom: [atom.pos.x, atom.pos.y, atom.pos.z]
        result.append({"aa": seq1(residue.name, custom_map={"MSE": "M"}),
                       "ca": np.asarray(xyz(by_name["CA"])),
                       "heavy": np.asarray([xyz(atom) for atom in by_name.values()])})
    if not result:
        raise ValueError(f"No protein CA residues in chain {chain_id!r}")
    return result


def contacts(first: list[dict], second: list[dict], cutoff: float) -> np.ndarray:
    return np.asarray([[bool((np.linalg.norm(a["heavy"][:, None] - b["heavy"][None, :],
                                             axis=-1) < cutoff).any())
                        for b in second] for a in first], dtype=bool)


def rmsd(reference: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum((reference - fit_coordinates(reference, prediction)) ** 2, axis=1))))


def verify(reference: Path, prediction: Path, claimed: dict) -> dict:
    mapping = claimed["chain_mapping"]
    if len(mapping) != 2 or len({x[0] for x in mapping}) != 2 or len({x[1] for x in mapping}) != 2:
        raise ValueError("This explicit verifier requires two distinct mapped chains")
    if claimed.get("correspondence_method") != "identical-sequence-alignment":
        raise ValueError("Only the declared identical-sequence correspondence is qualified here")
    provenance = claimed["provenance"]
    if (sha256(reference.read_bytes()) != provenance["reference_sha256"] or
            sha256(prediction.read_bytes()) != provenance["prediction_sha256"]):
        raise ValueError("Downloaded coordinates do not match the claimed source hashes")
    paired, chain_scores = [], []
    for ref_id, pred_id in mapping:
        ref, pred = chain_residues(reference, ref_id), chain_residues(prediction, pred_id)
        ref_sequence, pred_sequence = "".join(r["aa"] for r in ref), "".join(r["aa"] for r in pred)
        pairs = [(a, b) for a, b in sequence_pairs(ref_sequence, pred_sequence)
                 if ref_sequence[a] == pred_sequence[b]]
        left, right = [ref[a] for a, _ in pairs], [pred[b] for _, b in pairs]
        paired.append((left, right))
        chain_scores.append(rmsd(np.asarray([r["ca"] for r in left]), np.asarray([r["ca"] for r in right])))
    ref_a, pred_a = paired[0]
    ref_b, pred_b = paired[1]
    ref_xyz = np.asarray([r["ca"] for r in ref_a + ref_b])
    pred_xyz = np.asarray([r["ca"] for r in pred_a + pred_b])
    cutoff = float(claimed["interface"]["heavy_atom_cutoff_angstrom"])
    ref_contacts, pred_contacts = contacts(ref_a, ref_b, cutoff), contacts(pred_a, pred_b, cutoff)
    interface = np.concatenate([ref_contacts.any(axis=1), ref_contacts.any(axis=0)])
    measured = {"global_ca_rmsd_angstrom": rmsd(ref_xyz, pred_xyz),
                "independently_fitted_chain_ca_rmsds": chain_scores,
                "mapped_residues": len(ref_xyz),
                "native_contacts_mapped_residues": int(ref_contacts.sum()),
                "predicted_contacts_mapped_residues": int(pred_contacts.sum()),
                "recovered_native_contacts": int((ref_contacts & pred_contacts).sum()),
                "interface_residues_mapped": int(interface.sum()),
                "interface_ca_rmsd_angstrom": rmsd(ref_xyz[interface], pred_xyz[interface])}
    errors = {"global_ca_rmsd_angstrom": abs(measured["global_ca_rmsd_angstrom"] - claimed["global_ca_rmsd_angstrom"]),
              "interface_ca_rmsd_angstrom": abs(measured["interface_ca_rmsd_angstrom"] - claimed["interface"]["interface_ca_rmsd_angstrom"])}
    for index, score in enumerate(chain_scores):
        errors[f"chain_{index}_ca_rmsd"] = abs(score - claimed["chains"][index]["independently_fitted_ca_rmsd_angstrom"])
    integer_checks = {key: measured[key] == claimed["interface"][key] for key in
                      ("native_contacts_mapped_residues", "predicted_contacts_mapped_residues",
                       "recovered_native_contacts", "interface_residues_mapped")}
    integer_checks["mapped_residues"] = measured["mapped_residues"] == claimed["mapped_residues"]
    return {"verified": max(errors.values()) < 1e-5 and all(integer_checks.values()),
            "coordinate_tolerance_angstrom": 1e-5, "measured": measured,
            "absolute_errors": errors, "exact_integer_checks": integer_checks,
            "reference_sha256": sha256(reference.read_bytes()),
            "prediction_sha256": sha256(prediction.read_bytes()),
            "scope": "Independent numerical receipt verification; no validation of narrative or biological efficacy"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--claimed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.reference, args.prediction, json.loads(args.claimed.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["verified"] else 1)


if __name__ == "__main__":
    main()
