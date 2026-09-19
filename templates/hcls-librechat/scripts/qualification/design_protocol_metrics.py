"""Independent sequence/motif/ligand constraints, not efficacy or model scores."""
import re

import gemmi
import numpy as np


def aligned_rmsd(reference, prediction):
    from evaluators import fit_coordinates
    if reference.shape != prediction.shape or len(reference) < 3:
        raise ValueError("Complete corresponding coordinates are required")
    fitted = fit_coordinates(reference, prediction)
    return float(np.sqrt(np.mean(np.sum((reference - fitted) ** 2, axis=1))))


def distinct_pattern_assignment(chains, patterns):
    """Require distinct actual chains for every declared framework, not reuse."""
    options = [[c for c, value in chains.items() if re.fullmatch(pattern, value["sequence"])] for pattern in patterns]
    def assign(index, used):
        if index == len(options):
            return []
        for chain in options[index]:
            if chain not in used:
                rest = assign(index + 1, used | {chain})
                if rest is not None:
                    return [chain, *rest]
        return None
    return assign(0, set())


def measure_structure(text, expected, root):
    from evaluators import design_metrics, is_coordinate_cif, parse_chain, protein_chain_ids
    chains = {c: parse_chain(text, c) for c in protein_chain_ids(text)}
    geometry = design_metrics(text, {})
    measured = {"geometry": geometry, "protocol": expected["protocol"], "constraints_pass": True}
    if expected["protocol"] == "scaffold-motif":
        if len(chains) != 1:
            raise ValueError("Motif fixture expects exactly one generated protein chain")
        prediction = next(iter(chains.values()))
        reference = parse_chain((root / expected["reference_path"]).read_text(), expected["reference_chain"])
        positions = []
        for residue_id in expected["reference_residue_ids"]:
            matching = [i for i, residue in enumerate(reference["residue_ids"]) if residue[1] == residue_id and str(residue[2]).strip() == ""]
            if len(matching) != 1:
                raise ValueError("Motif reference residue mapping is not complete and unique")
            positions.append(matching[0])
        output_positions = [p - 1 for p in expected["output_motif_positions_1based"]]
        if len(prediction["sequence"]) != expected["total_residues"] or max(output_positions) >= len(prediction["sequence"]):
            measured.update(constraints_pass=False, error="output_length_does_not_match_declared_contig")
            return measured
        exact_sequence = "".join(reference["sequence"][i] for i in positions) == "".join(prediction["sequence"][i] for i in output_positions)
        rmsd = aligned_rmsd(reference["coordinates"][positions], prediction["coordinates"][output_positions])
        measured.update(motif_sequence_exact=exact_sequence, motif_ca_rmsd_angstrom=rmsd,
                        motif_mapping_basis="explicit fixed-length contig10-10/A23-34/10-10 and original residue IDs",
                        constraints_pass=exact_sequence and rmsd <= expected["motif_ca_rmsd_limit"])
        designed = list(chains)
    else:
        targets = [c for c, value in chains.items() if value["sequence"] == expected.get("target_sequence")]
        target_ok = "target_sequence" not in expected or len(targets) == 1
        designed = distinct_pattern_assignment({c: value for c, value in chains.items() if c not in targets}, expected["designed_patterns"])
        measured.update(target_sequence_exact=target_ok, assigned_designed_chains=designed,
                        fixed_framework_and_length_match=designed is not None,
                        constraints_pass=target_ok and designed is not None)
        if "target_sequence_coverage" in expected:
            measured["target_sequence_coverage"] = expected["target_sequence_coverage"]
        if expected.get("fixed_reference") and designed is not None:
            reference = parse_chain((root / expected["fixed_reference"]).read_text(), expected["fixed_chain"])
            positions = [p - 1 for p in expected["fixed_positions_1based"]]
            prediction = chains[designed[0]]
            if len(reference["sequence"]) != len(prediction["sequence"]):
                raise ValueError("Redesign without insertions must preserve positional correspondence")
            rmsd = aligned_rmsd(reference["coordinates"][positions], prediction["coordinates"][positions])
            measured.update(fixed_ca_rmsd_angstrom=rmsd)
            measured["constraints_pass"] &= rmsd <= expected["fixed_ca_rmsd_limit"]
        if expected.get("ligand_ccd"):
            structure = gemmi.make_structure_from_block(gemmi.cif.read_string(text).sole_block()) if is_coordinate_cif(text) else gemmi.read_pdb_string(text)
            residues = [r for c in structure[0] for r in c if r.name == expected["ligand_ccd"]]
            atoms = sorted([[a.name, a.element.name] for a in residues[0] if a.element.name != "H"]) if len(residues) == 1 else []
            valid = len(residues) == 1 and atoms == expected["ligand_heavy_atoms"]
            measured.update(ligand_ccd=expected["ligand_ccd"], ligand_count=len(residues), ligand_heavy_atom_identity_exact=valid,
                            chemical_scope="CCD residue label and complete atom-name/element identity; not independent stereochemistry or binding validation")
            measured["constraints_pass"] &= valid
    designed_geometry = [row for row in geometry["chains"] if row["chain"] in (designed or [])]
    geometry_ok = bool(designed_geometry) and all(row["ca_step_outside_2_5_to_4_5_fraction"] < 0.1 for row in designed_geometry)
    measured.update(designed_backbone_geometry_pass=geometry_ok)
    measured["constraints_pass"] = bool(measured["constraints_pass"] and geometry_ok)
    return measured


def evaluate_protocol(result, expected, root):
    from evaluators import extract_structures, unwrap
    structures = extract_structures(result)
    if not structures:
        raise ValueError("No materialized output structures for design protocol")
    measurements = [measure_structure(text, expected, root) for text in structures]
    rows = [row for item in unwrap(result).get("outputs", []) for row in item.get("csv_rows", [])]
    return {"service_semantic_pass": len(structures) >= expected["minimum_structures"] and all(m["constraints_pass"] for m in measurements),
            "predictions": measurements, "unique_structure_count": len(structures),
            "upstream_ranking_rows": rows,
            "qualification_scope": "Exact declared sequence/framework/motif/ligand and basic geometry checks only; no affinity, catalysis, clinical or experimental qualification"}
