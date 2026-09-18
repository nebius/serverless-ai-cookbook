#!/usr/bin/env python3
"""Independent artifact and scientific measurements for qualification cases.

Reference-fit metrics describe this protocol, not paper replication. In
particular, ``tm_score_kabsch`` and ``gdt_ts_kabsch`` use one least-squares fit;
they are deliberately not advertised as optimized TM-align or GDT scores.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
from io import BytesIO, StringIO
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from Bio.Align import PairwiseAligner
from Bio.PDB import MMCIFParser, PDBParser
from Bio.SeqUtils import seq1


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_coordinate_cif(text: str) -> bool:
    """Recognize the first CIF token without stripping provenance comments.

    AlphaFold3 prepends its output-terms notice. CIF permits comments and blank
    lines before the data block; they are not evidence of a malformed artifact.
    """
    for line in text.splitlines():
        token = line.strip()
        if token and not token.startswith("#"):
            return token.lower().startswith("data_")
    return False


def parse_chain(text: str, chain_id: str | None = None) -> dict:
    if is_coordinate_cif(text):
        # OpenFold3 emits valid coordinate CIF without optional occupancy. The
        # BioPython full-structure parser requires that column; Gemmi correctly
        # reads it without rewriting source bytes or rounding coordinates.
        import gemmi
        model = gemmi.make_structure_from_block(gemmi.cif.read_string(text).sole_block())[0]
        candidates = []
        for chain in model:
            residues = [(residue, [atom for atom in residue if atom.name == "CA"])
                        for residue in chain if residue.het_flag == "A" or residue.name == "MSE"]
            residues = [(residue, atoms) for residue, atoms in residues if atoms]
            if residues:
                candidates.append((chain, residues))
        if chain_id is None and len(candidates) != 1:
            raise ValueError("Multiple protein chains require explicit chain selection.")
        chosen = next(((chain, residues) for chain, residues in candidates
                       if chain_id is None or chain.name == chain_id), None)
        if chosen is None:
            raise ValueError(f"Reference/prediction lacks requested chain {chain_id!r}.")
        chain, residues = chosen
        atoms = [max(atoms, key=lambda atom: atom.occ if math.isfinite(atom.occ) else 0) for _, atoms in residues]
        coords = np.asarray([[atom.pos.x, atom.pos.y, atom.pos.z] for atom in atoms], dtype=float)
        if not np.isfinite(coords).all():
            raise ValueError("Structure contains non-finite coordinates.")
        return {"sequence": "".join(seq1(residue.name, custom_map={"MSE": "M"}) for residue, _ in residues),
                "coordinates": coords, "chain": chain.name,
                "residue_ids": [[residue.het_flag, residue.seqid.num, residue.seqid.icode] for residue, _ in residues]}
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("qualification", StringIO(text))
    model = next(structure.get_models())
    chains = [chain for chain in model if any("CA" in residue for residue in chain)]
    if chain_id is None:
        if len(chains) != 1:
            raise ValueError("Multiple protein chains require explicit chain selection.")
        chain = chains[0]
    else:
        chain = next((chain for chain in chains if chain.id == chain_id), None)
        if chain is None:
            raise ValueError(f"Reference/prediction lacks requested chain {chain_id!r}.")
    residues = [residue for residue in chain if "CA" in residue and residue.id[0] in {" ", "H_MSE"}]
    if not residues:
        raise ValueError("Structure contains no protein C-alpha coordinates.")
    sequence = "".join(seq1(residue.resname, custom_map={"MSE": "M"}) for residue in residues)
    coords = np.asarray([residue["CA"].coord for residue in residues], dtype=float)
    if not np.isfinite(coords).all():
        raise ValueError("Structure contains non-finite coordinates.")
    return {"sequence": sequence, "coordinates": coords, "chain": chain.id,
            "residue_ids": [list(residue.id) for residue in residues]}


def protein_chain_ids(text: str) -> list[str]:
    if is_coordinate_cif(text):
        import gemmi
        model = gemmi.make_structure_from_block(gemmi.cif.read_string(text).sole_block())[0]
        return [chain.name for chain in model if any(atom.name == "CA" for residue in chain for atom in residue)]
    model = next(PDBParser(QUIET=True).get_structure("chains", StringIO(text)).get_models())
    return [chain.id for chain in model if any("CA" in residue for residue in chain)]


def design_input_chains(pdb_text: str, chain_ids: list[str] | None = None) -> list[dict]:
    """Sequence represented by ATOM residues, including incomplete backbones.

    Coordinate-reference metrics require CA, but inverse-folding length must not
    silently discard an explicitly present residue merely because its CA is
    unresolved. PDB numbering holes are explicit X placeholders, not inventions.
    """
    model = next(PDBParser(QUIET=True).get_structure("design-input", StringIO(pdb_text)).get_models())
    chains = []
    for chain in sorted(model, key=lambda item: item.id):
        if chain_ids and chain.id not in chain_ids:
            continue
        residues = [residue for residue in chain if residue.id[0] in {" ", "H_MSE"}]
        if not residues:
            continue
        sequence, incomplete = [], []
        previous = residues[0].id[1] - 1
        for residue in residues:
            number = residue.id[1]
            for _ in range(previous + 1, number):
                sequence.append("X")
                incomplete.append(len(sequence))
            sequence.append(seq1(residue.resname, custom_map={"MSE": "M"}))
            if not all(atom in residue for atom in ("N", "CA", "C", "O")):
                incomplete.append(len(sequence))
            previous = number
        chains.append({"chain_id": chain.id, "sequence": "".join(sequence),
                       "incomplete_backbone_positions_1based": incomplete})
    if not chains:
        raise ValueError("Inverse-folding input contains no requested ATOM residues.")
    return chains


def design_input_sequence(pdb_text: str, chain_ids: list[str] | None = None) -> str:
    return "".join(chain["sequence"] for chain in design_input_chains(pdb_text, chain_ids))


def sequence_pairs(reference: str, prediction: str) -> list[tuple[int, int]]:
    aligner = PairwiseAligner(mode="global", match_score=2, mismatch_score=-1,
                             open_gap_score=-3, extend_gap_score=-0.2)
    alignment = aligner.align(reference, prediction)[0]
    pairs = []
    for ref_span, pred_span in zip(*alignment.aligned):
        pairs.extend(zip(range(*ref_span), range(*pred_span)))
    return [(int(a), int(b)) for a, b in pairs]


def fit_coordinates(reference: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    """Least-squares proper rotation: reflections are explicitly disallowed."""
    ref_center, pred_center = reference.mean(axis=0), prediction.mean(axis=0)
    centered_ref, centered_pred = reference - ref_center, prediction - pred_center
    u, _, vt = np.linalg.svd(centered_pred.T @ centered_ref)
    reflection = np.eye(3)
    reflection[2, 2] = np.linalg.det(u @ vt)
    return centered_pred @ (u @ reflection @ vt) + ref_center


def ca_lddt(reference: np.ndarray, prediction: np.ndarray, cutoff: float = 15.0) -> float | None:
    ref_dist = np.linalg.norm(reference[:, None, :] - reference[None, :, :], axis=-1)
    pred_dist = np.linalg.norm(prediction[:, None, :] - prediction[None, :, :], axis=-1)
    mask = np.triu((ref_dist < cutoff) & (ref_dist > 0), k=1)
    if not mask.any():
        return None
    differences = np.abs(ref_dist[mask] - pred_dist[mask])
    return float(np.mean([(differences < threshold).mean() for threshold in (0.5, 1, 2, 4)]))


def structure_metrics(reference: str, prediction: str, *, reference_chain: str | None = None,
                      prediction_chain: str | None = None, input_sequence: str | None = None) -> dict:
    ref = parse_chain(reference, reference_chain)
    pred = parse_chain(prediction, prediction_chain)
    pairs = sequence_pairs(ref["sequence"], pred["sequence"])
    identical = [(a, b) for a, b in pairs if ref["sequence"][a] == pred["sequence"][b]]
    if len(identical) < 3:
        raise ValueError("Fewer than three sequence-matched C-alpha atoms; structure comparison is undefined.")
    ref_xyz = ref["coordinates"][[a for a, _ in identical]]
    pred_xyz = pred["coordinates"][[b for _, b in identical]]
    fitted = fit_coordinates(ref_xyz, pred_xyz)
    distances = np.linalg.norm(ref_xyz - fitted, axis=1)
    ref_len = len(ref["sequence"])
    d0 = max(0.5, 1.24 * np.cbrt(ref_len - 15) - 1.8)
    input_sequence = input_sequence or ref["sequence"]
    input_pairs = sequence_pairs(input_sequence, pred["sequence"])
    input_identical = sum(input_sequence[a] == pred["sequence"][b] for a, b in input_pairs)
    metrics = {
        "reference_chain": ref["chain"], "prediction_chain": pred["chain"],
        "reference_residues": ref_len, "prediction_residues": len(pred["sequence"]),
        "input_residues": len(input_sequence), "aligned_identical_residues": len(identical),
        "reference_coverage": len(identical) / ref_len,
        "input_coverage": input_identical / len(input_sequence),
        "sequence_identity": input_identical / max(len(input_pairs), 1),
        "prediction_sequence_exact": pred["sequence"] == input_sequence,
        "ca_rmsd_angstrom": float(np.sqrt(np.mean(distances ** 2))),
        "ca_distance_median_angstrom": float(np.median(distances)),
        "ca_lddt_15A": ca_lddt(ref_xyz, pred_xyz),
        "gdt_ts_kabsch": float(np.mean([(distances < t).sum() / ref_len for t in (1, 2, 4, 8)])),
        "tm_score_kabsch": float(np.sum(1 / (1 + (distances / d0) ** 2)) / ref_len),
        "tm_score_method": "fixed sequence mapping, one Kabsch fit; not optimized TM-align",
        "ca_lddt_method": "C-alpha pair distances under 15 A; thresholds 0.5,1,2,4 A; not all-atom lDDT",
    }
    if len(pred["coordinates"]) > 1:
        bonds = np.linalg.norm(np.diff(pred["coordinates"], axis=0), axis=1)
        metrics["adjacent_ca_distance_median_angstrom"] = float(np.median(bonds))
        metrics["adjacent_ca_distance_outside_2_5_to_4_5_fraction"] = float(np.mean((bonds < 2.5) | (bonds > 4.5)))
    return metrics


def backbone_recovery_metrics(reference: str, prediction: str, *, designed_sequence: str,
                              reference_chain: str | None = None) -> dict:
    """Inverse-design recovery uses known residue-position correspondence.

    The designed sequence intentionally differs from the original protein.
    Aligning only identical amino acids would hide redesigned positions and
    inflate recovery. This protocol admits complete equal-length backbones.
    """
    ref, pred = parse_chain(reference, reference_chain), parse_chain(prediction)
    if len(ref["sequence"]) != len(designed_sequence) or len(pred["sequence"]) != len(designed_sequence):
        raise ValueError("Backbone-recovery protocol requires complete equal-length positional coverage.")
    fitted = fit_coordinates(ref["coordinates"], pred["coordinates"])
    distances = np.linalg.norm(ref["coordinates"] - fitted, axis=1)
    size = len(designed_sequence)
    d0 = max(0.5, 1.24 * np.cbrt(size - 15) - 1.8)
    return {"prediction_sequence_exact": pred["sequence"] == designed_sequence,
            "residues": size, "positional_coverage": 1.0,
            "designed_sequence_identity_to_original": sum(a == b for a, b in zip(ref["sequence"], designed_sequence)) / size,
            "ca_rmsd_angstrom": float(np.sqrt(np.mean(distances ** 2))),
            "ca_lddt_15A": ca_lddt(ref["coordinates"], pred["coordinates"]),
            "tm_score_kabsch": float(np.mean(1 / (1 + (distances / d0) ** 2))),
            "gdt_ts_kabsch": float(np.mean([(distances < t).mean() for t in (1, 2, 4, 8)])),
            "mapping": "all residue positions, including redesigned amino acids; not sequence-identity alignment",
            "score_scope": "fixed Kabsch CA metrics, not optimized TM-align or experimental design validation"}


def unwrap(value: Any) -> Any:
    """Decode common MCP/result envelopes without inventing missing artifacts."""
    for _ in range(8):
        if not isinstance(value, dict):
            break
        if value.get("isError"):
            raise ValueError("Result contains an MCP error.")
        if value.get("structuredContent") is not None:
            value = value["structuredContent"]
        elif isinstance(value.get("result"), dict):
            value = value["result"]
        elif isinstance(value.get("response"), dict):
            value = value["response"]
        elif isinstance(value.get("content"), list) and len(value["content"]) == 1 and value["content"][0].get("type") == "text":
            value = json.loads(value["content"][0]["text"])
        else:
            break
    return value


def extract_structures(value: Any) -> list[str]:
    value = unwrap(value)
    found = []
    if isinstance(value, str) and ("ATOM  " in value or is_coordinate_cif(value)):
        return [value]
    if isinstance(value, dict):
        for key in ("structure", "pdb", "mmcif", "cif", "pdb_string", "pdb_text", "cif_text"):
            if isinstance(value.get(key), str):
                found.extend(extract_structures(value[key]))
        for key in ("structures_in_ranked_order", "structures_with_scores", "structures", "predictions", "outputs", "data"):
            if isinstance(value.get(key), (dict, list)):
                found.extend(extract_structures(value[key]))
    elif isinstance(value, list):
        for item in value:
            found.extend(extract_structures(item))
    return list(dict.fromkeys(found))


def design_metrics(prediction: str, expected: dict) -> dict:
    chains, coordinates = [], {}
    for chain in protein_chain_ids(prediction):
        parsed = parse_chain(prediction, chain)
        coords = parsed["coordinates"]
        coordinates[chain] = coords
        step_lengths = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        distances = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=-1)
        nonlocal_pairs = np.triu(np.ones(distances.shape, dtype=bool), k=3)
        length = len(parsed["sequence"])
        chain_metrics = {"chain": chain, "residues": length,
            "sequence_sha256": sha256(parsed["sequence"].encode()),
            "radius_of_gyration_angstrom": float(np.sqrt(np.mean(np.sum((coords - coords.mean(axis=0)) ** 2, axis=1)))),
            "adjacent_ca_min_angstrom": float(step_lengths.min()) if len(step_lengths) else None,
            "adjacent_ca_max_angstrom": float(step_lengths.max()) if len(step_lengths) else None,
            "adjacent_ca_median_angstrom": float(np.median(step_lengths)) if len(step_lengths) else None,
            "nonlocal_ca_pairs_below_2A": int(np.sum(nonlocal_pairs & (distances < 2))),
            "nonlocal_ca_scope": "C-alpha pairs separated by at least three sequence positions; not an all-atom clash score",
            "ca_step_outside_2_5_to_4_5_fraction": float(np.mean((step_lengths < 2.5) | (step_lengths > 4.5))) if len(step_lengths) else 1.0,
            "within_requested_length": expected.get("binder_length_min", 1) <= length <= expected.get("binder_length_max", 100000)}
        chains.append(chain_metrics)
    if not chains:
        raise ValueError("Design artifact contains no protein chain.")
    candidates = [chain for chain in chains if chain["within_requested_length"]]
    if expected.get("binder_chain"):
        candidates = [chain for chain in candidates if chain["chain"] == expected["binder_chain"]]
    interfaces = []
    for i, first in enumerate(chains):
        for second in chains[i + 1:]:
            distances = np.linalg.norm(coordinates[first["chain"]][:, None, :] -
                                       coordinates[second["chain"]][None, :, :], axis=-1)
            interfaces.append({"chains": [first["chain"], second["chain"]],
                "ca_contact_pairs_below_8A": int(np.sum(distances < 8)),
                "ca_pairs_below_2A": int(np.sum(distances < 2)),
                "minimum_interchain_ca_distance_angstrom": float(distances.min()),
                "scope": "geometric C-alpha proximity only; not binding affinity, all-atom clashes or experimentally validated interface"})
    return {"chains": chains, "candidate_binder_chains": [chain["chain"] for chain in candidates],
            "constraint_pass": bool(candidates) and all(chain["ca_step_outside_2_5_to_4_5_fraction"] < 0.1 for chain in candidates),
            "interfaces": interfaces,
            "interface_coordinate_coverage": "multiple_chain_coordinates_available" if interfaces else "single_chain_only_no_interface_coordinates",
            "binding_efficacy": "not_evaluated", "downstream_refolding": "required_for_design_quality_claim"}


def proteina_design_metrics(result: dict, expected: dict) -> dict:
    """Independently join coordinate roles and reproduce the published CA RMSD.

    Raw generation may have poor geometry; retain that measurement without
    falsely substituting it for the scored self-refolded prediction.
    """
    outputs = unwrap(result).get("outputs", [])
    provenance = [item for item in outputs if isinstance(item, dict) and
                  item.get("schema_version") == "fs2-serve.nebius.ai/proteina-complexa-design-provenance/v1"]
    if len(provenance) != 1:
        raise ValueError("Proteina result needs one generated/refolded design provenance artifact.")
    named = {item["artifact_name"]: item for item in outputs if isinstance(item, dict) and item.get("artifact_name")}
    rows = provenance[0].get("designs", [])
    if not rows:
        raise ValueError("Proteina provenance contains no designs.")
    measured, seen_ids, seen_artifacts = [], set(), set()
    for design in rows:
        identity = design["id_gen"]
        if identity in seen_ids:
            raise ValueError("Duplicate Proteina design identity.")
        seen_ids.add(identity)
        csv_output = named[design["results_artifact"]]
        matching = [row for row in csv_output["csv_rows"] if row.get("id_gen") == identity]
        if len(matching) != 1:
            raise ValueError("Proteina design does not identify exactly one CSV row.")
        row = matching[0]
        digest = sha256(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        if digest != design["results_row_sha256"] or sha256(row["self_sequence"].encode()) != design["sequence_sha256"]:
            raise ValueError("Proteina CSV/sequence provenance digest mismatch.")
        structures, chains = {}, {}
        for role, column in (("generated", "generated_structure_artifact"),
                             ("self_refolded", "self_refolded_structure_artifact")):
            link = design[role]
            name = link["artifact_name"]
            if name in seen_artifacts or row[column] != name:
                raise ValueError("Proteina reuses or mismatches a role artifact.")
            seen_artifacts.add(name)
            structure = named[name]["structure"]
            if sha256(structure.encode()) != link["sha256"]:
                raise ValueError("Proteina role coordinate hash mismatch.")
            parsed = parse_chain(structure, link["binder_chain"])
            if parsed["sequence"] != row["self_sequence"]:
                raise ValueError("Proteina coordinate binder does not match the CSV sequence.")
            structures[role], chains[role] = structure, parsed
        raw, refold = chains["generated"]["coordinates"], chains["self_refolded"]["coordinates"]
        fitted = fit_coordinates(raw, refold)
        rmsd = float(np.sqrt(np.mean(np.sum((raw - fitted) ** 2, axis=1))))
        published = float(row["self_binder_scRMSD_ca"])
        if not math.isfinite(published):
            raise ValueError("Proteina published CA RMSD is non-finite.")
        # PDB coordinates are rounded to 0.001 A; tolerate that representation,
        # not a changed design or a score from another sequence.
        agreement = abs(rmsd - published) <= 0.01
        raw_geometry = design_metrics(structures["generated"], {**expected, "binder_chain": chains["generated"]["chain"]})
        refold_geometry = design_metrics(structures["self_refolded"], {**expected, "binder_chain": chains["self_refolded"]["chain"]})
        measured.append({"id_gen": identity, "sequence_sha256": design["sequence_sha256"],
            "generated_artifact": design["generated"]["artifact_name"],
            "self_refolded_artifact": design["self_refolded"]["artifact_name"],
            "generated_geometry": raw_geometry, "self_refolded_geometry": refold_geometry,
            "independent_binder_ca_rmsd_angstrom": rmsd, "csv_binder_ca_rmsd_angstrom": published,
            "rmsd_absolute_difference_angstrom": abs(rmsd - published), "csv_rmsd_agrees": agreement,
            "ca_lddt_raw_vs_refolded": ca_lddt(raw, refold),
            "refolding_model": design["refolding_model"], "relaxation": design["relaxation"]})
    return {"service_semantic_pass": len(measured) >= expected.get("minimum_structures", 1) and
                all(row["csv_rmsd_agrees"] and row["self_refolded_geometry"]["constraint_pass"] for row in measured),
            "design_count": len(measured), "coordinate_artifact_count": 2 * len(measured), "predictions": measured,
            "generated_geometry_pass_count": sum(row["generated_geometry"]["constraint_pass"] for row in measured),
            "self_refolded_geometry_pass_count": sum(row["self_refolded_geometry"]["constraint_pass"] for row in measured),
            "qualification_scope": "generated/refolded sequence and coordinate linkage, independently reproduced self-consistency; not experimental binding efficacy"}


def complex_metrics(reference: str, prediction: str, expected: dict) -> dict:
    """Sequence-mapped heteromer geometry, with explicit C-alpha contacts.

    This is not DockQ: all-atom native contacts and CAPRI interface definitions
    are not substituted by these coarse C-alpha measurements.
    """
    predicted_ids = protein_chain_ids(prediction)
    if len(predicted_ids) != len(expected["chains"]):
        raise ValueError("Complex output protein-chain count differs from the request.")
    predicted = {chain: parse_chain(prediction, chain) for chain in predicted_ids}
    mapped, used = [], set()
    for chain in expected["chains"]:
        matches = [chain_id for chain_id, parsed in predicted.items()
                   if chain_id not in used and parsed["sequence"] == chain["input_sequence"]]
        if len(matches) != 1:
            raise ValueError("Heteromer chain sequence missing or ambiguous; do not infer a convenient chain mapping.")
        selected = matches[0]
        used.add(selected)
        ref = parse_chain(reference, chain["reference_chain"])
        pred = predicted[selected]
        indexes = [(a, b) for a, b in sequence_pairs(ref["sequence"], pred["sequence"])
                   if ref["sequence"][a] == pred["sequence"][b]]
        if len(indexes) < 3:
            raise ValueError("Complex chain lacks three reference-matched residues.")
        mapped.append({"reference_chain": ref["chain"], "prediction_chain": selected,
                       "reference": ref["coordinates"][[a for a, _ in indexes]],
                       "prediction": pred["coordinates"][[b for _, b in indexes]],
                       "reference_coverage": len(indexes) / len(ref["sequence"])})
    if len(mapped) != 2:
        raise ValueError("Current independent heteromer interface evaluator requires two chains.")
    ref_a, ref_b = [chain["reference"] for chain in mapped]
    pred_a, pred_b = [chain["prediction"] for chain in mapped]
    reference_all, predicted_all = np.concatenate([ref_a, ref_b]), np.concatenate([pred_a, pred_b])
    fitted = fit_coordinates(reference_all, predicted_all)
    ref_contacts = np.linalg.norm(ref_a[:, None, :] - ref_b[None, :, :], axis=-1) < 8.0
    pred_contacts = np.linalg.norm(pred_a[:, None, :] - pred_b[None, :, :], axis=-1) < 8.0
    if not ref_contacts.any():
        raise ValueError("Selected reference chains have no C-alpha interface contacts below 8 A.")
    interface_mask = np.concatenate([ref_contacts.any(axis=1), ref_contacts.any(axis=0)])
    interface_fitted = fit_coordinates(reference_all[interface_mask], predicted_all[interface_mask])
    centered_ref, centered_pred = ref_a - ref_a.mean(axis=0), pred_a - pred_a.mean(axis=0)
    u, _, vt = np.linalg.svd(centered_pred.T @ centered_ref)
    proper = np.diag([1.0, 1.0, np.linalg.det(u @ vt)])
    ligand_fitted = (pred_b - pred_a.mean(axis=0)) @ (u @ proper @ vt) + ref_a.mean(axis=0)
    correct = int((ref_contacts & pred_contacts).sum())
    return {"chains": [{key: value for key, value in chain.items() if key not in {"reference", "prediction"}}
                       for chain in mapped],
            "complex_ca_rmsd_angstrom": float(np.sqrt(np.mean(np.sum((fitted - reference_all) ** 2, axis=1)))),
            "interface_ca_rmsd_angstrom": float(np.sqrt(np.mean(np.sum((interface_fitted - reference_all[interface_mask]) ** 2, axis=1)))),
            "partner_ca_rmsd_after_receptor_fit_angstrom": float(np.sqrt(np.mean(np.sum((ligand_fitted - ref_b) ** 2, axis=1)))),
            "native_ca_contacts": int(ref_contacts.sum()), "predicted_ca_contacts": int(pred_contacts.sum()),
            "native_ca_contact_recall": correct / int(ref_contacts.sum()),
            "ca_contact_precision": correct / int(pred_contacts.sum()) if pred_contacts.any() else 0.0,
            "interface_residues": int(interface_mask.sum()), "all_input_chain_sequences_exact": True,
            "method": "Sequence-mapped heterodimer; C-alpha contacts under 8 A. Not DockQ/CAPRI or all-atom interface scoring."}


def docking_metrics(reference_sdf: str, prediction_sdf: str) -> dict:
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
    ref = Chem.MolFromMolBlock(reference_sdf.split("$$$$")[0], removeHs=True)
    pred = Chem.MolFromMolBlock(prediction_sdf.split("$$$$")[0], removeHs=True)
    if ref is None or pred is None:
        raise ValueError("Reference or predicted SDF is chemically unparsable.")
    if ref.GetNumConformers() != 1 or pred.GetNumConformers() != 1:
        raise ValueError("Each docking pose must have exactly one conformer.")
    if not np.isfinite(pred.GetConformer().GetPositions()).all():
        raise ValueError("Docked ligand contains non-finite coordinates.")
    ref_smiles = Chem.MolToSmiles(ref, isomericSmiles=False)
    pred_smiles = Chem.MolToSmiles(pred, isomericSmiles=False)
    if ref_smiles != pred_smiles:
        raise ValueError("Ligand topology/charge differs from reference; RMSD would be misleading.")
    rmsd = rdMolAlign.CalcRMS(pred, ref, maxMatches=100000, symmetrizeConjugatedTerminalGroups=True)
    centroid = float(np.linalg.norm(pred.GetConformer().GetPositions().mean(axis=0) -
                                    ref.GetConformer().GetPositions().mean(axis=0)))
    return {"heavy_atom_count": ref.GetNumHeavyAtoms(), "heavy_atom_rmsd_angstrom": float(rmsd),
            "centroid_distance_angstrom": centroid, "within_2_angstrom": bool(rmsd < 2),
            "rmsd_method": "RDKit symmetry-aware CalcRMS in receptor frame; no ligand alignment",
            "same_ligand_topology": True}


def fasta_records(text: str) -> list[tuple[str, str]]:
    records = []
    header, sequence = None, []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(sequence)))
            header, sequence = line[1:], []
        elif header is None:
            raise ValueError("FASTA/A3M sequence precedes its header.")
        else:
            sequence.append(line)
    if header is not None:
        records.append((header, "".join(sequence)))
    return records


def molecular_metrics(result: dict, expected: dict) -> dict:
    from rdkit import Chem, DataStructs
    from rdkit.Chem import Crippen, QED, rdFingerprintGenerator
    molecules = result.get("molecules", result.get("generated", []))
    source = Chem.MolFromSmiles(expected["source_smiles"]) if expected.get("source_smiles") else None
    fingerprinter = rdFingerprintGenerator.GetMorganGenerator(radius=2)
    measured = []
    for item in molecules:
        smiles = item.get("smiles", item.get("sample"))
        molecule = Chem.MolFromSmiles(smiles or "")
        if molecule is None or not molecule.GetNumAtoms():
            raise ValueError("Generated molecule is empty or chemically unparsable.")
        value = QED.qed(molecule) if expected.get("scoring", "QED").upper() == "QED" else Crippen.MolLogP(molecule)
        reported = float(item["score"])
        metric = {"canonical_smiles": Chem.MolToSmiles(molecule), "heavy_atoms": molecule.GetNumHeavyAtoms(),
            "recomputed_score": value, "reported_score": reported, "score_absolute_error": abs(value - reported),
            "model_decoded": item.get("model_decoded")}
        if source is not None:
            similarity = DataStructs.TanimotoSimilarity(fingerprinter.GetFingerprint(source), fingerprinter.GetFingerprint(molecule))
            metric.update(similarity=similarity,
                similarity_absolute_error=abs(similarity - float(item.get("similarity", similarity))),
                changed_from_input=Chem.MolToSmiles(source) != Chem.MolToSmiles(molecule),
                property_change_from_input=value - QED.qed(source))
        measured.append(metric)
    count = len(measured)
    valid = count == expected["num_molecules"] and all(m["score_absolute_error"] < 1e-5 for m in measured)
    if source is not None:
        valid = valid and all(m["similarity"] + 1e-8 >= expected.get("min_similarity", 0) and
                              m["similarity_absolute_error"] < 1e-5 for m in measured)
    return {"service_semantic_pass": valid, "molecules": measured, "requested_molecules": expected["num_molecules"],
        "returned_molecules": count, "unique_molecules": len({m["canonical_smiles"] for m in measured}),
        "scientific_accuracy": "chemical validity and independent QED/LogP/similarity; no efficacy or synthesizability claim"}


def phenoage_reference(sample: dict) -> float:
    """Published rounded coefficients, evaluated independently at 60 digits.

    Source: Levine2018 Supplement1 pp1–2/TableS1. Use the survival/cumulative
    hazard equations rather than importing the serving implementation.
    """
    coefficients = {"age_years": "0.0804", "albumin_g_l": "-0.0336", "creatinine_umol_l": "0.0095",
        "glucose_mmol_l": "0.1953", "c_reactive_protein_mg_dl": "0.0954", "lymphocyte_percent": "-0.0120",
        "mean_cell_volume_fl": "0.0268", "red_cell_distribution_width_percent": "0.3306",
        "alkaline_phosphatase_u_l": "0.0019", "white_blood_cell_count_10e3_per_ul": "0.0554"}
    with localcontext() as context:
        context.prec = 60
        linear = Decimal("-19.9067")
        for field, coefficient in coefficients.items():
            value = Decimal(str(sample[field]))
            if field == "c_reactive_protein_mg_dl":
                value = value.ln()
            linear += Decimal(coefficient) * value
        gamma = Decimal("0.0076927")
        cumulative_hazard = linear.exp() * ((gamma * 120).exp() - 1) / gamma
        age = Decimal("141.50225") + (Decimal("0.00553") * cumulative_hazard).ln() / Decimal("0.090165")
        return float(age)


def altumage_reference(h5_path: Path, values: np.ndarray) -> np.ndarray:
    """Independent NumPy inference from the original Keras artifact.

    This deliberately does not reuse the hosted PyTorch architecture or weights
    conversion. Dropout/activity regularization are inactive at inference.
    """
    import h5py
    value = np.asarray(values, dtype=np.float64)
    with h5py.File(h5_path) as model:
        config = json.loads(model.attrs["model_config"])
        for layer in config["config"]["layers"]:
            kind, options = layer["class_name"], layer["config"]
            if kind in {"InputLayer", "GaussianDropout", "ActivityRegularization", "Dropout"}:
                continue
            if kind in {"Dense", "BatchNormalization"}:
                group = model["model_weights"][options["name"]]
                weights = {name.rsplit("/", 1)[-1].split(":")[0]: np.asarray(group[name]) for name in group.attrs["weight_names"]}
            if kind == "BatchNormalization":
                value = (value - weights["moving_mean"]) / np.sqrt(weights["moving_variance"] + options["epsilon"])
                value = value * weights["gamma"] + weights["beta"]
            elif kind == "Dense":
                if options.get("activation", "linear") != "linear":
                    raise ValueError("Unimplemented non-linear Dense reference layer.")
                value = value @ weights["kernel"] + weights["bias"]
            elif kind == "Activation" and options["activation"] == "selu":
                negative = value < 0
                value = value.copy()
                value[negative] = 1.6732632423543772 * np.expm1(value[negative])
                value *= 1.0507009873554805
            else:
                raise ValueError(f"Unsupported original AltumAge reference layer: {kind}")
    if not np.isfinite(value).all():
        raise ValueError("Original model reference produced non-finite predictions.")
    return value.reshape(-1)


def segmentation_metrics(reference, prediction, expected: dict) -> dict:
    """Measure the declared label in physical-image geometry, not filenames."""
    ref = np.asanyarray(reference.dataobj)
    pred = np.asanyarray(prediction.dataobj)
    if pred.shape != ref.shape:
        raise ValueError("Segmentation shape differs from the expert reference.")
    if not np.allclose(reference.affine, prediction.affine, atol=1e-5, rtol=1e-6):
        raise ValueError("Segmentation affine/orientation differs from the expert reference.")
    if not np.isfinite(pred).all() or not np.array_equal(pred, np.rint(pred)):
        raise ValueError("Segmentation contains non-finite or non-integer class labels.")
    labels = np.unique(pred)
    allowed = {0, expected["prediction_foreground_label"], 255}
    if set(labels.tolist()) - allowed:
        raise ValueError("Single-class segmentation returned unexpected label IDs.")
    actual, gold = pred == expected["prediction_foreground_label"], ref == expected["reference_foreground_label"]
    predicted_voxels, reference_voxels = int(actual.sum()), int(gold.sum())
    if not reference_voxels:
        raise ValueError("Expert reference has no foreground; study preparation is invalid.")
    intersection = int(np.logical_and(actual, gold).sum())
    union = predicted_voxels + reference_voxels - intersection
    voxel_mm3 = abs(float(np.linalg.det(reference.affine[:3, :3])))
    return {"shape": list(pred.shape), "affine_preserved": True,
            "labels": [int(label) for label in labels], "unknown_voxel_fraction": float(np.mean(pred == 255)),
            "predicted_voxels": predicted_voxels, "reference_voxels": reference_voxels,
            "dice": 2 * intersection / (predicted_voxels + reference_voxels), "iou": intersection / union,
            "recall": intersection / reference_voxels,
            "precision": intersection / predicted_voxels if predicted_voxels else 0.0,
            "predicted_volume_ml": predicted_voxels * voxel_mm3 / 1000,
            "reference_volume_ml": reference_voxels * voxel_mm3 / 1000,
            "foreground_returned": predicted_voxels > 0}


def evaluate(case: dict, result: Any, base: Path = Path(".")) -> dict:
    expected = case["expected"]
    kind = expected["evaluator"]
    receipt = {"evaluator": kind, "case_id": case["case_id"], "service_semantic_pass": False,
               "paper_reproduction": "not_claimed"}
    try:
        if kind == "protein_structure":
            structures = extract_structures(result)
            if not structures:
                raise ValueError("No structure bytes found; fetch the result artifact before evaluation.")
            reference = (base / expected["reference_path"]).read_text()
            metrics = [structure_metrics(reference, structure,
                        reference_chain=expected.get("reference_chain"),
                        prediction_chain=expected.get("prediction_chain"),
                        input_sequence=expected.get("input_sequence")) for structure in structures]
            thresholds = expected.get("thresholds", {})
            valid = all(m["input_coverage"] >= thresholds.get("input_coverage_min", 1) and
                        m["sequence_identity"] >= thresholds.get("sequence_identity_min", 1) and
                        m["prediction_sequence_exact"] for m in metrics)
            receipt.update(service_semantic_pass=valid, predictions=metrics,
                           scientific_accuracy="measured_against_experimental_reference",
                           reference_sha256=sha256(reference.encode()),
                           prediction_sha256=[sha256(item.encode()) for item in structures])
        elif kind == "protein_complex":
            structures = extract_structures(result)
            if not structures:
                raise ValueError("No materialized complex structure returned.")
            reference = (base / expected["reference_path"]).read_text()
            metrics = [complex_metrics(reference, structure, expected) for structure in structures]
            receipt.update(service_semantic_pass=all(item["all_input_chain_sequences_exact"] for item in metrics),
                           predictions=metrics, scientific_accuracy="measured_against_experimental_complex",
                           reference_sha256=sha256(reference.encode()))
        elif kind == "backbone_recovery":
            structures = extract_structures(result)
            if not structures:
                raise ValueError("No materialized refolded structure returned.")
            reference = (base / expected["reference_path"]).read_text()
            metrics = [backbone_recovery_metrics(reference, structure,
                       designed_sequence=expected["input_sequence"], reference_chain=expected.get("reference_chain"))
                       for structure in structures]
            receipt.update(service_semantic_pass=all(item["prediction_sequence_exact"] for item in metrics),
                           predictions=metrics, scientific_accuracy="independent_refolding_backbone_recovery",
                           experimental_binding="not_evaluated", reference_sha256=sha256(reference.encode()))
        elif kind == "scalar_predictions":
            data = unwrap(result)
            predictions = data["predictions"]
            reference = expected["reference_predictions"]
            field = expected["prediction_field"]
            measured = []
            seen = set()
            for prediction in predictions:
                sample_id = prediction["sample_id"]
                if sample_id in seen or sample_id not in reference:
                    raise ValueError("Prediction has a duplicate or unknown sample ID.")
                seen.add(sample_id)
                value = float(prediction[field])
                if not math.isfinite(value):
                    raise ValueError("Non-finite scalar prediction.")
                item = {"sample_id": sample_id, "predicted": value, "reference": reference[sample_id],
                        "absolute_reference_error": abs(value - reference[sample_id])}
                if "true_ages" in expected:
                    item["chronological_age"] = expected["true_ages"][sample_id]
                    item["age_absolute_error"] = abs(value - item["chronological_age"])
                if "imputed_counts" in expected:
                    item["imputed_count_correct"] = prediction.get("imputed_cpg_count") == expected["imputed_counts"][sample_id]
                measured.append(item)
            receipt.update(service_semantic_pass=seen == set(reference) and all(
                item["absolute_reference_error"] <= expected["absolute_tolerance"] and item.get("imputed_count_correct", True)
                for item in measured), samples=measured, samples_returned=len(predictions),
                max_reference_error=max((item["absolute_reference_error"] for item in measured), default=None))
            if measured and "true_ages" in expected:
                receipt["mean_absolute_age_error"] = float(np.mean([item["age_absolute_error"] for item in measured]))
        elif kind == "ct_segmentation":
            import nibabel as nib
            data = unwrap(result)
            raw = base64.b64decode(data["output_nifti_base64"], validate=True)
            if raw.startswith(b"\x1f\x8b"):
                raw = gzip.decompress(raw)
            predicted = nib.Nifti1Image.from_bytes(raw)
            reference = nib.load(base / expected["reference_path"])
            measured = segmentation_metrics(reference, predicted, expected)
            receipt.update(service_semantic_pass=measured["foreground_returned"], segmentation=measured,
                           scientific_accuracy="measured_against_expert_mask",
                           clinical_use="not_qualified", prompt_mode=expected["prompt_mode"])
        elif kind == "dna_continuation":
            data = unwrap(result)
            sequence = data["sequence"].upper()
            timings = data["elapsed_ms_per_token"]
            truth = expected["reference_continuation"]
            valid = (len(sequence) == expected["num_tokens"] and not (set(sequence) - set("ACGTN"))
                     and len(timings) == len(sequence) and all(math.isfinite(value) and value >= 0 for value in timings))
            receipt.update(service_semantic_pass=valid, generated_bases=len(sequence),
                gc_fraction=sum(letter in "GC" for letter in sequence) / max(len(sequence), 1),
                reference_gc_fraction=sum(letter in "GC" for letter in truth) / len(truth),
                positional_reference_identity=sum(a == b for a, b in zip(sequence, truth)) / len(truth),
                mean_decode_ms=float(np.mean(timings)) if timings else None,
                scientific_scope="Benign plant-reference continuation; positional identity is descriptive, not functional validity, variant-effect scoring or paper reproduction.")
        elif kind in {"chat_json", "cxr_findings", "chat_tool_call"}:
            data = unwrap(result)
            choice = data["choices"][0]
            message = choice["message"]
            if kind == "chat_tool_call":
                calls = message.get("tool_calls", [])
                if len(calls) != 1 or calls[0]["function"]["name"] != expected["tool_name"]:
                    raise ValueError("Expected exactly one named function call.")
                answer = json.loads(calls[0]["function"]["arguments"])
            else:
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("No visible assistant answer; reasoning-only output is not an answer.")
                answer = json.loads(content)
            if not isinstance(answer, dict):
                raise ValueError("Requested JSON object was not returned.")
            if choice.get("finish_reason") == "length":
                raise ValueError("Completion was truncated at the output budget.")
            if kind == "cxr_findings":
                found = answer.get("findings")
                allowed = set(expected["allowed_findings"])
                if not isinstance(found, list) or any(label not in allowed for label in found):
                    raise ValueError("CXR answer does not follow the requested finding-label contract.")
                predicted, gold = set(found), set(expected["reference_findings"])
                correct = len(predicted & gold)
                receipt.update(service_semantic_pass=True, predicted_findings=sorted(predicted),
                    reference_findings=sorted(gold), weak_label_precision=correct / len(predicted) if predicted else None,
                    weak_label_recall=correct / len(gold) if gold else None, exact_weak_label_match=predicted == gold,
                    clinical_use="not_qualified", label_quality="NIH report-mined weak labels, not expert adjudication")
            else:
                comparison = {key: answer.get(key) == value for key, value in expected["reference_answer"].items()}
                receipt.update(service_semantic_pass=set(expected["reference_answer"]) <= set(answer),
                    scientific_checks=comparison, scientific_checks_pass=all(comparison.values()), answer=answer)
            receipt["usage"] = data.get("usage")
        elif kind == "generated_image":
            from PIL import Image
            data = unwrap(result)
            images = data.get("data", [])
            if len(images) != 1:
                raise ValueError("Expected one generated image.")
            raw = base64.b64decode(images[0]["b64_json"], validate=True)
            with Image.open(BytesIO(raw)) as image:
                image.load()
                pixels = np.asarray(image.convert("RGB"))
                measured = {"format": image.format, "size": list(image.size),
                            "pixel_standard_deviation": float(pixels.std()), "sha256": sha256(raw)}
            receipt.update(service_semantic_pass=measured["format"] == "PNG" and
                           measured["size"] == expected["size"] and measured["pixel_standard_deviation"] > 1,
                           image=measured, scientific_use="Illustration only, not observation or anatomy reference.",
                           visual_prompt_adherence="requires_independent_visual_review")
        elif kind == "msa_alignment":
            data = unwrap(result)
            alignment = data["alignments"]["pdb70_220313"]["a3m"]["alignment"]
            rows = fasta_records(alignment)
            if not rows:
                raise ValueError("MSA search returned no alignment rows.")
            aligned = ["".join(letter for letter in sequence if not letter.islower() and letter != ".") for _, sequence in rows]
            query = aligned[0].replace("-", "")
            valid = (query == expected["input_sequence"] and all(len(row) == len(aligned[0]) for row in aligned)
                     and len(rows) <= expected.get("max_sequences", len(rows)))
            receipt.update(service_semantic_pass=valid, alignment_rows=len(rows), unique_sequences=len(set(aligned)),
                alignment_columns=len(aligned[0]), query_exact=query == expected["input_sequence"],
                alignment_sha256=sha256(alignment.encode()), can_support_downstream_comparison=valid and len(set(aligned)) > 1)
        elif kind == "protein_sequence_design":
            data = unwrap(result)
            rows = [(header, sequence.replace("/", "")) for header, sequence in fasta_records(data["mfasta"]) if not header.startswith("input ")]
            native = expected["input_sequence"]
            input_chains = [{"chain_id": "A", "sequence": native, "incomplete_backbone_positions_1based": []}]
            if isinstance(case.get("arguments", {}).get("input_pdb"), str):
                input_chains = design_input_chains(case["arguments"]["input_pdb"], case["arguments"].get("input_pdb_chains"))
                native = "".join(chain["sequence"] for chain in input_chains)
            unresolved = {index for index, residue in enumerate(native) if residue == "X"}
            incomplete, offsets, cursor = set(), {}, 0
            for chain in input_chains:
                offsets[chain["chain_id"]] = cursor
                incomplete.update(cursor + position - 1 for position in chain["incomplete_backbone_positions_1based"])
                cursor += len(chain["sequence"])
            incomplete.update(unresolved)
            designable = set(range(len(native))) - incomplete
            measured = []
            for header, sequence in rows:
                measured.append({"header": header, "sequence": sequence, "length": len(sequence),
                    "sequence_recovery": sum(index < len(sequence) and native[index] == sequence[index]
                                             for index in designable) / len(designable) if designable else None,
                    "sequence_recovery_basis": "resolved N/CA/C/O backbone positions only; fixed/missing positions excluded",
                    "valid_alphabet": all(letter in "ACDEFGHIKLMNPQRSTVWY" or (letter == "X" and index in unresolved)
                                          for index, letter in enumerate(sequence)),
                    "unresolved_input_positions_preserved": {index for index, letter in enumerate(sequence) if letter == "X"} == unresolved,
                    "nondesignable_native_positions_preserved": all(index < len(sequence) and sequence[index] == native[index]
                                                                  for index in incomplete),
                    "omitted_residues_absent": not ({letter for index, letter in enumerate(sequence) if index in designable}
                                                    & set(expected.get("omit_AAs", [])))})
            valid = len(measured) == expected["num_sequences"] and all(m["length"] == len(native) and
                    m["valid_alphabet"] and m["omitted_residues_absent"] and m["unresolved_input_positions_preserved"]
                    and m["nondesignable_native_positions_preserved"] for m in measured)
            coverage = data.get("backbone_coverage", {})
            if unresolved:
                reported = {offsets.get(chain.get("chain_id"), len(native)) + position - 1
                            for chain in coverage.get("chains", [])
                            for position in chain.get("unresolved_sequence_positions_1based", [])}
                valid = valid and coverage.get("complete") is False and reported == unresolved
            receipt.update(service_semantic_pass=valid, sequences=measured,
                input_residues=len(native), input_sequence_basis="all ATOM residues, not CA-only",
                scientifically_designable_residues=len(designable),
                incomplete_backbone_residues=len(incomplete), unresolved_sequence_residues=len(unresolved),
                backbone_design_coverage=len(designable) / len(native),
                scientific_coverage="partial_incomplete_backbone" if incomplete else "complete_backbone",
                downstream_gap_policy="required_before_refolding; X is not a designed amino acid" if unresolved else None,
                unresolved_input_positions_1based=[index + 1 for index in sorted(unresolved)],
                machine_readable_backbone_coverage=coverage or None,
                downstream_refolding="required_for_structure_recovery", unique_sequences=len({m["sequence"] for m in measured}))
        elif kind == "molecule_generation":
            receipt.update(molecular_metrics(unwrap(result), expected))
        elif kind == "design_constraints":
            if case.get("model_id") == "proteina-complexa":
                receipt.update(proteina_design_metrics(result, expected))
                return receipt
            structures = extract_structures(result)
            if not structures:
                raise ValueError("No materialized design structure found; terminal artifact envelopes are insufficient.")
            metrics = [design_metrics(structure, expected) for structure in structures]
            receipt.update(service_semantic_pass=len(structures) >= expected.get("minimum_structures", 1) and
                           all(item["constraint_pass"] for item in metrics),
                           predictions=metrics, unique_structure_count=len(structures),
                           qualification_scope="sequence/geometry/count constraints only; contact/refolding/experimental binding remain separate")
        elif kind == "docking_pose":
            data = unwrap(result)
            poses = data.get("ligand_positions", [])
            if not poses and isinstance(data.get("poses"), list):
                poses = [pose["sdf"] for pose in data["poses"]]
            if not poses:
                raise ValueError("No docked SDF poses found in result.")
            reference = (base / expected["reference_path"]).read_text()
            metrics = [docking_metrics(reference, pose) for pose in poses]
            receipt.update(service_semantic_pass=len(poses) == expected.get("num_poses", len(poses)),
                           predictions=metrics, top1_within_2_angstrom=metrics[0]["within_2_angstrom"],
                           topN_within_2_angstrom=any(m["within_2_angstrom"] for m in metrics),
                           best_heavy_atom_rmsd_angstrom=min(m["heavy_atom_rmsd_angstrom"] for m in metrics),
                           reference_sha256=sha256(reference.encode()))
        else:
            raise ValueError(f"Evaluator {kind!r} is not implemented; missing coverage is not success.")
    except (ValueError, KeyError, IndexError, OSError, RuntimeError) as error:
        receipt["error"] = str(error)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    case = next(item for item in manifest["cases"] if item["case_id"] == args.case_id)
    receipt = evaluate(case, json.loads(args.result.read_text()), args.manifest.parent)
    encoded = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end="")
    raise SystemExit(0 if receipt["service_semantic_pass"] else 1)


if __name__ == "__main__":
    main()
