"""Compare docking poses in a shared receptor coordinate frame, without fitting.

No inference, coordinate generation, ligand alignment or chemical repair occurs.
Full heavy-atom graph/stereochemistry identity is required. Confidence scores are
reported separately; they are not experimental affinity or reference accuracy.
"""
from __future__ import annotations

import argparse
import csv
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


def rank_facts(rows, threshold_queries=()):
    """Descriptive facts only: no correlation, success cutoff or efficacy claim."""
    valid = [row for row in rows if row['status'] == 'comparable']
    scored = [row for row in valid if 'model_confidence_not_reference_accuracy' in row]
    def extrema(candidates, field, choose):
        if not candidates:
            return {'value': None, 'ranks': []}
        value = choose(row[field] for row in candidates)
        return {'value': value, 'ranks': [row['rank'] for row in candidates if row[field] == value]}
    facts = {
        'best_rmsd': extrema(valid, 'pose_rmsd_angstrom', min),
        'worst_rmsd': extrema(valid, 'pose_rmsd_angstrom', max),
        'highest_confidence': extrema(scored, 'model_confidence_not_reference_accuracy', max),
        'lowest_confidence': extrema(scored, 'model_confidence_not_reference_accuracy', min),
        'supplied_top_rank': rows[0]['rank'], 'comparable_pose_count': len(valid),
        'confidence_scored_comparable_pose_count': len(scored),
    }
    facts['best_rmsd_also_lowest_confidence_ranks'] = sorted(set(facts['best_rmsd']['ranks']) & set(facts['lowest_confidence']['ranks']))
    facts['best_rmsd_also_highest_confidence_ranks'] = sorted(set(facts['best_rmsd']['ranks']) & set(facts['highest_confidence']['ranks']))
    if len(threshold_queries) > 20:
        raise ValueError('At most20 explicit descriptive threshold queries are supported.')
    counts = []
    for confidence, rmsd in threshold_queries:
        if not np.isfinite(confidence) or not np.isfinite(rmsd) or rmsd <= 0:
            raise ValueError('Thresholds must be finite and rmsd_below must be positive.')
        eligible = [row for row in scored if row['model_confidence_not_reference_accuracy'] > confidence]
        matched = [row for row in eligible if row['pose_rmsd_angstrom'] < rmsd]
        counts.append({'confidence_above': confidence, 'rmsd_below_angstrom': rmsd,
            'operators': 'strict confidence > threshold AND RMSD < threshold',
            'eligible_comparable_pose_count': len(eligible), 'matching_pose_count': len(matched),
            'eligible_ranks': [row['rank'] for row in eligible], 'matching_ranks': [row['rank'] for row in matched],
            'descriptive_only': True})
    return facts, counts


def compare(reference, predictions, confidences=None, max_matches=10000, threshold_queries=()):
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
    facts, threshold_counts = rank_facts(rows, threshold_queries)
    return {'schema': 'scientific-ai/docking-pose-comparison/v1', 'poses': rows,
            'requested_pose_count': len(rows), 'comparable_pose_count': len(valid),
            'all_poses_comparable': len(valid) == len(rows),
            'top_rank_pose_rmsd_angstrom': rows[0].get('pose_rmsd_angstrom'),
            'best_comparable_pose_rmsd_angstrom': min((row['pose_rmsd_angstrom'] for row in valid), default=None),
            'rank_facts': facts, 'threshold_counts': threshold_counts,
            'method': 'Minimum unfitted heavy-atom RMSD across exact stereochemistry-preserving graph mappings.',
            'limitations': ['Requires a shared receptor coordinate frame confirmed by the caller.',
                            'Does not align the ligand, normalize tautomers/protonation or repair chemistry.',
                            'No default success threshold, experimental affinity or biological efficacy claim.',
                            'Extrema are descriptive ranks, not a correlation estimate or proof that confidence ranks accuracy.',
                            'Threshold counts use only explicit caller thresholds and strict comparisons before rounding.'],
            'rdkit_version': rdBase.rdkitVersion, 'numpy_version': np.__version__}


def write_report(report, output):
    """Reuse exact computed rows and extrema in a ready-to-download report."""
    directory = output.parent
    prefix = '' if output.name == 'metrics.json' else output.stem + '.'
    facts = report['rank_facts']
    fields = ['rank', 'status', 'pose_rmsd_angstrom', 'model_confidence_not_reference_accuracy', 'reason']
    with (directory / (prefix + 'rows.csv')).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(report['poses'])
    lines = ['# Docking pose comparison', '', report['method'], '',
        f"Comparable poses: {report['comparable_pose_count']} / {report['requested_pose_count']}",
        'The supplied order is retained; confidence is not reference accuracy.', '',
        '| Rank | Status | Unfitted heavy-atom RMSD (Å) | Model confidence |', '|---:|---|---:|---:|']
    for row in report['poses']:
        lines.append(f"| {row['rank']} | {row['status']} | {row.get('pose_rmsd_angstrom', 'unavailable')} | {row.get('model_confidence_not_reference_accuracy', 'unavailable')} |")
        if row.get('reason'):
            lines.append(f"\nRank {row['rank']} is not comparable: {row['reason']}\n")
    lines += ['', '## Descriptive comparisons', '']
    for field, label in [('best_rmsd', 'Lowest RMSD'), ('worst_rmsd', 'Highest RMSD'),
                         ('highest_confidence', 'Highest confidence'), ('lowest_confidence', 'Lowest confidence')]:
        lines.append(f"- {label}: {facts[field]['value']}; rank(s) {facts[field]['ranks']}.")
    lines += [f"- Best-RMSD and lowest-confidence overlap: {facts['best_rmsd_also_lowest_confidence_ranks']}.",
              f"- Best-RMSD and highest-confidence overlap: {facts['best_rmsd_also_highest_confidence_ranks']}.",
              'These lists alone do not establish monotonicity, correlation or calibration.']
    for query in report['threshold_counts']:
        lines += ['', f"Explicit descriptive query: among {query['eligible_comparable_pose_count']} comparable poses with confidence > {query['confidence_above']}, {query['matching_pose_count']} have RMSD < {query['rmsd_below_angstrom']} Å. Matching ranks: {query['matching_ranks']}. Strict comparisons use unrounded values; this is not a scientific pass threshold."]
    lines += ['', '## Method and provenance', '',
              'Exact heavy-atom graph/stereochemistry identity; exhaustive bounded symmetry mapping. No ligand alignment, tautomer or protonation repair.',
              f"Reference SHA-256: {report['provenance']['reference_sha256']}",
              f"Prediction source SHA-256: {report['provenance']['prediction_source_sha256']}",
              f"RDKit: {report['rdkit_version']}; NumPy: {report['numpy_version']}", '', *report['limitations']]
    (directory / (prefix + 'report.md')).write_text('\n'.join(lines) + '\n')


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
    parser.add_argument('--threshold-query', type=float, nargs=2, action='append', default=[],
                        metavar=('CONFIDENCE_ABOVE', 'RMSD_BELOW'), help='Explicit strict descriptive threshold count; never a default success criterion.')
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
    report = compare(reference[0], predictions, confidences, args.max_matches, args.threshold_query)
    report['provenance'] = {'reference_file': str(args.reference), 'prediction_source': str(source),
                            'reference_sha256': hashlib.sha256(reference_bytes).hexdigest(),
                            'prediction_source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                            'shared_receptor_frame': 'explicitly_confirmed_by_caller'}
    save(args.output, report)
    write_report(report, args.output)
    print(json.dumps(report, allow_nan=False))
    if not report['all_poses_comparable']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
