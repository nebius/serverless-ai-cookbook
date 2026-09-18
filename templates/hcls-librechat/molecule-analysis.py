"""Compare docking poses in a shared receptor coordinate frame, without fitting.

No inference, coordinate generation, ligand alignment or chemical repair occurs.
Full heavy-atom graph/stereochemistry identity is required. Confidence scores are
reported separately; they are not experimental affinity or reference accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from rdkit import Chem, rdBase

from scientific_receipts import save


def parse_molecules(data):
    molecules = list(Chem.ForwardSDMolSupplier(io.BytesIO(data), removeHs=False))
    if not molecules or any(molecule is None for molecule in molecules):
        raise ValueError('Invalid or empty SDF/molblock; no chemical repair was attempted.')
    return molecules


def heavy_atoms(molecule):
    molecule = Chem.Mol(molecule)
    for atom in molecule.GetAtoms():
        atom.SetIntProp('_source_index', atom.GetIdx())
        atom.SetAtomMapNum(0)
    molecule = Chem.RemoveHs(molecule)
    if not molecule.GetNumAtoms() or any(atom.GetAtomicNum() <= 1 for atom in molecule.GetAtoms()):
        raise ValueError('Expected a nonempty heavy-atom molecule without query atoms or retained isotopic hydrogens.')
    if molecule.GetNumConformers() != 1:
        raise ValueError('Exactly one retained coordinate conformer is required per SDF record.')
    coordinates = np.asarray(molecule.GetConformer().GetPositions(), dtype=float)
    if not np.isfinite(coordinates).all():
        raise ValueError('Coordinates contain non-finite values.')
    return molecule, coordinates


def pose_rmsd(reference, prediction, max_matches=10000):
    if not isinstance(max_matches, int) or not 1 <= max_matches <= 100000:
        raise ValueError('max_matches must be between1 and100000; exhausted enumeration is never reported as exact.')
    reference, ref_xyz = heavy_atoms(reference)
    prediction, pred_xyz = heavy_atoms(prediction)
    if Chem.MolToSmiles(reference, isomericSmiles=True) != Chem.MolToSmiles(prediction, isomericSmiles=True):
        raise ValueError('Heavy-atom graph, charge, isotope or stereochemistry differs; pose RMSD is not comparable.')
    # The query is the reference: mapping[i] is a PREDICTION atom corresponding
    # to reference atom i. Reversing this direction produces plausible but wrong
    # RMSDs whenever atom order differs by a non-involutive permutation.
    mappings = prediction.GetSubstructMatches(reference, uniquify=False, useChirality=True,
                                              maxMatches=max_matches + 1)
    if not mappings:
        raise ValueError('No full stereochemistry-preserving atom correspondence.')
    if len(mappings) > max_matches:
        raise ValueError('Symmetry enumeration is incomplete; no exact minimum RMSD claimed.')
    rmsds = [float(np.sqrt(np.mean(np.sum((pred_xyz[list(mapping)] - ref_xyz) ** 2, axis=1))))
             for mapping in mappings]
    best = int(np.argmin(rmsds))
    return {
        'pose_rmsd_angstrom': rmsds[best], 'alignment': 'none',
        'heavy_atoms': reference.GetNumAtoms(), 'symmetry_mappings_evaluated': len(mappings),
        'symmetry_enumeration_complete': True,
        'reference_to_prediction_heavy_atom_indices': list(mappings[best]),
        'original_atom_correspondence': [
            {'reference_atom': reference.GetAtomWithIdx(i).GetIntProp('_source_index'),
             'prediction_atom': prediction.GetAtomWithIdx(j).GetIntProp('_source_index')}
            for i, j in enumerate(mappings[best])],
    }


def compare(reference, predictions, confidences=None, max_matches=10000):
    if not predictions or (confidences is not None and len(confidences) != len(predictions)):
        raise ValueError('Predictions must be nonempty and confidence count must match when supplied.')
    rows = []
    for index, prediction in enumerate(predictions):
        row = {'rank': index + 1}
        if confidences is not None:
            confidence = confidences[index]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not np.isfinite(confidence):
                raise ValueError('Confidence must be a finite numeric value; no guessed replacements.')
            row['model_confidence_not_reference_accuracy'] = confidence
        try:
            row.update(status='comparable', **pose_rmsd(reference, prediction, max_matches))
        except ValueError as error:
            row.update(status='not_comparable', reason=str(error))
        rows.append(row)
    valid = [row for row in rows if row['status'] == 'comparable']
    return {'schema': 'scientific-ai/docking-pose-comparison/v1', 'poses': rows,
            'requested_pose_count': len(rows), 'comparable_pose_count': len(valid),
            'all_poses_comparable': len(valid) == len(rows),
            'top_rank_pose_rmsd_angstrom': rows[0].get('pose_rmsd_angstrom'),
            'best_comparable_pose_rmsd_angstrom': min((row['pose_rmsd_angstrom'] for row in valid), default=None),
            'method': 'Minimum unfitted heavy-atom RMSD across exact stereochemistry-preserving graph mappings.',
            'limitations': ['Requires a shared receptor coordinate frame confirmed by the caller.',
                            'Does not align the ligand, normalize tautomers/protonation or repair chemistry.',
                            'No default success threshold, experimental affinity or biological efficacy claim.'],
            'rdkit_version': rdBase.rdkitVersion, 'numpy_version': np.__version__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path, help='One experimental/reference ligand SDF record.')
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--prediction', type=Path, help='Predicted SDF records in retained rank order.')
    sources.add_argument('--result', type=Path, help='Saved DiffDock JSON containing ligand_positions molblocks.')
    parser.add_argument('--same-coordinate-frame', action='store_true', required=True,
                        help='Confirm input/output poses share the same receptor frame; do not ligand-fit.')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-matches', type=int, default=10000)
    args = parser.parse_args()
    reference_bytes = args.reference.read_bytes()
    reference = parse_molecules(reference_bytes)
    if len(reference) != 1:
        raise ValueError('Select exactly one reference SDF record explicitly.')
    source = args.result or args.prediction
    source_bytes = source.read_bytes()
    confidences = None
    if args.result:
        result = json.loads(source_bytes)
        blocks = result.get('ligand_positions')
        if not isinstance(blocks, list) or not blocks or any(not isinstance(block, str) for block in blocks):
            raise ValueError('Saved result must contain nonempty ligand_positions molblocks.')
        predictions = []
        for block in blocks:
            molecules = parse_molecules(block.encode())
            if len(molecules) != 1:
                raise ValueError('Each ranked ligand_positions entry must contain exactly one molecule.')
            predictions.extend(molecules)
        confidences = result.get('position_confidence')
    else:
        predictions = parse_molecules(source_bytes)
    report = compare(reference[0], predictions, confidences, args.max_matches)
    report['provenance'] = {'reference_file': str(args.reference), 'prediction_source': str(source),
                            'reference_sha256': hashlib.sha256(reference_bytes).hexdigest(),
                            'prediction_source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                            'shared_receptor_frame': 'explicitly_confirmed_by_caller'}
    save(args.output, report)
    print(json.dumps(report, allow_nan=False))
    if not report['all_poses_comparable']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
