"""Deterministic saved-result analysis for docking poses and GenMol molecules.

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
from rdkit.Chem import Crippen, QED

from scientific_receipts import save, staged_output


def analyze_genmol(request, result):
    """Measure every retained GenMol row; never filter, pad or generate molecules.

    The hosted result contract is exactly ``molecules:[{smiles,score}]``. Missing
    or malformed envelopes are not recursively searched for plausible strings.
    Chemical invalidity, duplicates and underfill remain measured outcomes.
    """
    if not isinstance(request, dict) or not isinstance(request.get('smiles'), str) or not request['smiles']:
        raise ValueError('GenMol request must contain its original nonempty smiles mask.')
    requested = request.get('num_molecules', 1)
    unique = request.get('unique', False)
    scoring = request.get('scoring', 'QED')
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError('num_molecules must be a positive integer.')
    if not isinstance(unique, bool) or not isinstance(scoring, str) or scoring.upper() not in {'QED', 'LOGP'}:
        raise ValueError('GenMol requires boolean unique and scoring QED or LogP.')
    scoring = scoring.upper()
    if not isinstance(result, dict) or not isinstance(result.get('molecules'), list):
        raise ValueError('Use the saved raw GenMol result with molecules:[{smiles,score}], not a compact summary or operation envelope.')
    runtime_metrics = result.get('metrics', {})
    if not isinstance(runtime_metrics, dict):
        raise ValueError('GenMol result metrics must be an object when supplied.')
    rows, first_canonical = [], {}
    for index, item in enumerate(result['molecules']):
        if not isinstance(item, dict) or not isinstance(item.get('smiles'), str):
            raise ValueError(f'GenMol molecule row{index + 1} must contain a literal smiles string.')
        score = item.get('score')
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not np.isfinite(score)):
            raise ValueError(f'GenMol molecule row{index + 1} score must be finite numeric or absent; no replacement value is inferred.')
        row = {'row': index + 1, 'raw_smiles': item['smiles'], 'valid': False,
               'canonical_smiles': None, 'canonical_duplicate_of_row': None,
               'heavy_atoms': None, 'independent_qed': None, 'independent_logp': None,
               'model_score': score, 'model_scoring': scoring, 'score_absolute_error': None,
               'score_comparison_state': 'invalid_molecule', 'reason': None}
        molecule = Chem.MolFromSmiles(item['smiles'])
        if molecule is None or molecule.GetNumAtoms() == 0:
            row['reason'] = 'RDKit could not sanitize a nonempty molecule; original row retained.'
        else:
            canonical = Chem.MolToSmiles(molecule, isomericSmiles=True)
            qed, logp = float(QED.qed(molecule)), float(Crippen.MolLogP(molecule))
            if not np.isfinite(qed) or not np.isfinite(logp):
                raise ValueError(f'Nonfinite RDKit descriptor at row{index + 1}; no numeric result fabricated.')
            row.update(valid=True, canonical_smiles=canonical, heavy_atoms=molecule.GetNumHeavyAtoms(),
                       independent_qed=qed, independent_logp=logp,
                       canonical_duplicate_of_row=first_canonical.get(canonical),
                       score_comparison_state='unavailable' if score is None else 'measured',
                       score_absolute_error=None if score is None else abs(score - (qed if scoring == 'QED' else logp)))
            first_canonical.setdefault(canonical, index + 1)
        rows.append(row)
    valid = [row for row in rows if row['valid']]
    def distribution(field):
        values = [row[field] for row in valid]
        return {'count': len(values), 'minimum': min(values) if values else None,
                'maximum': max(values) if values else None,
                'mean': float(np.mean(values)) if values else None}
    declared_counts = {key: {'declared': runtime_metrics[key], 'measured': measured,
        'matches': type(runtime_metrics[key]) is int and runtime_metrics[key] == measured}
        for key, measured in [('requested_molecules', requested), ('returned_molecules', len(rows)),
                              ('accepted_molecules', len(valid))] if key in runtime_metrics}
    flags = []
    if len(rows) < requested:
        flags.append('underfilled')
    if len(rows) > requested:
        flags.append('overfilled')
    if len(valid) != len(rows):
        flags.append('invalid_molecules_retained')
    if unique and len(first_canonical) != len(valid):
        flags.append('canonical_duplicates_despite_unique_request')
    if any(not row['matches'] for row in declared_counts.values()):
        flags.append('runtime_count_mismatch')
    return {'schema': 'scientific-ai/genmol-descriptors/v1', 'rows': rows,
        'requested_count': requested, 'returned_count': len(rows),
        'underfilled': len(rows) < requested, 'overfilled': len(rows) > requested,
        'valid_count': len(valid), 'invalid_count': len(rows) - len(valid),
        'canonical_unique_valid': len(first_canonical),
        'canonical_duplicate_valid_count': len(valid) - len(first_canonical),
        'unique_requested': unique, 'scoring': scoring, 'request': request,
        'runtime_status': result.get('status'), 'runtime_metrics': runtime_metrics,
        'runtime_count_comparisons': declared_counts, 'quality_flags': flags,
        'heavy_atom_distribution': distribution('heavy_atoms'),
        'qed_distribution': distribution('independent_qed'),
        'logp_distribution': distribution('independent_logp'),
        'score_compared_count': sum(row['score_comparison_state'] == 'measured' for row in rows),
        'score_comparison_tolerance': None,
        'rdkit_version': rdBase.rdkitVersion, 'inference_submitted': False,
        'scientific_claims_validated': False,
        'method': 'RDKit sanitization, canonical isomeric SMILES uniqueness, heavy-atom count, QED and Crippen MolLogP. Original rows and supplied scores remain separate.',
        'limitations': ['The GenMol mask is a token-generation control, not a heavy-atom bound.',
            'Invalid, duplicate, underfilled and overfilled results are retained without padding or filtering.',
            'QED and LogP are computed molecular descriptors, not measured affinity, efficacy or proof of drug suitability.',
            'No automatic score-agreement threshold or biological pass is inferred. Missing scores remain unavailable.',
            'Canonical uniqueness uses RDKit canonical isomeric SMILES; no tautomer, protonation or stereochemistry repair is performed.']}


def analyze_genmol_files(request_file, result_file):
    request_file, result_file = Path(request_file), Path(result_file)
    request_bytes, result_bytes = request_file.read_bytes(), result_file.read_bytes()
    def invalid_constant(value):
        raise ValueError(f'Nonfinite JSON token {value} is not a measured number.')
    report = analyze_genmol(json.loads(request_bytes, parse_constant=invalid_constant),
                            json.loads(result_bytes, parse_constant=invalid_constant))
    report['provenance'] = {'request_file': str(request_file), 'result_file': str(result_file),
        'request_sha256': hashlib.sha256(request_bytes).hexdigest(), 'request_size_bytes': len(request_bytes),
        'result_sha256': hashlib.sha256(result_bytes).hexdigest(), 'result_size_bytes': len(result_bytes)}
    return report


def write_genmol_report(report, output):
    """Publish three closed measured files, then their completion manifest."""
    output = Path(output)
    prefix = '' if output.name == 'metrics.json' else output.stem + '.'
    buffer = io.StringIO(newline='')
    fields = ['row', 'raw_smiles', 'valid', 'canonical_smiles', 'canonical_duplicate_of_row',
              'heavy_atoms', 'independent_qed', 'independent_logp', 'model_score',
              'model_scoring', 'score_absolute_error', 'score_comparison_state', 'reason']
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(report['rows'])
    def clean(value):
        return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    lines = ['# GenMol saved-result analysis', '', report['method'], '',
        f"Requested: {report['requested_count']}; returned: {report['returned_count']}; valid: {report['valid_count']}; canonical-unique valid: {report['canonical_unique_valid']}.",
        f"Underfilled: {report['underfilled']}; overfilled: {report['overfilled']}; unique requested: {report['unique_requested']}.",
        f"Measured flags: {', '.join(report['quality_flags']) or 'none detected by these descriptive checks'}.", '',
        '| Row | Raw SMILES | Valid | Canonical duplicate of row | Heavy atoms | Independent QED | Independent LogP | Supplied score | Score absolute error |',
        '|---:|---|---|---:|---:|---:|---:|---:|---:|']
    for row in report['rows']:
        lines.append('| ' + ' | '.join(clean(row[field]) if row[field] is not None else 'unavailable'
            for field in ['row', 'raw_smiles', 'valid', 'canonical_duplicate_of_row', 'heavy_atoms',
                          'independent_qed', 'independent_logp', 'model_score', 'score_absolute_error']) + ' |')
    lines += ['', 'All computed values above are unrounded; CSV and JSON contain the same values.',
              f"Supplied score method: {report['scoring']}. QED is dimensionless; LogP is the computed octanol/water partition coefficient on a log10 scale, not an experimental measurement.",
              '', '## Provenance and limits', '', f"Request SHA-256: {report['provenance']['request_sha256']}",
              f"Result SHA-256: {report['provenance']['result_sha256']}", f"RDKit: {report['rdkit_version']}", '', *report['limitations']]
    files = {output.name: (json.dumps(report, indent=2, allow_nan=False) + '\n').encode(),
             prefix + 'rows.csv': buffer.getvalue().encode(),
             prefix + 'report.md': ('\n'.join(lines) + '\n').encode()}
    completion = {'schema': 'scientific-ai/genmol-analysis-artifacts/v1', 'state': 'complete',
        'inference_submitted': False, 'scientific_claims_validated': False,
        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inputs': report['provenance'], 'artifacts': [{'path': name, 'size_bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in files.items()]}
    files[prefix + 'completion-manifest.json'] = (json.dumps(completion, indent=2) + '\n').encode()
    for name, raw in files.items():
        with staged_output(output.parent / name) as staged:
            staged.path.write_bytes(raw)
    return completion


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
        writer.writeheader()
        writer.writerows(report['poses'])
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


def compare_files(reference_file, result_file=None, prediction_file=None, max_matches=10000, threshold_queries=()):
    if bool(result_file) == bool(prediction_file):
        raise ValueError('Supply exactly one result_file or prediction_file.')
    reference_bytes = Path(reference_file).read_bytes()
    reference = parse_molecules(reference_bytes)
    if len(reference) != 1:
        raise ValueError('Select exactly one reference SDF record explicitly.')
    source = Path(result_file or prediction_file)
    source_bytes = source.read_bytes()
    confidences = None
    if result_file:
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
    report = compare(reference[0], predictions, confidences, max_matches, threshold_queries)
    report['provenance'] = {'reference_file': str(reference_file), 'prediction_source': str(source),
                            'reference_sha256': hashlib.sha256(reference_bytes).hexdigest(),
                            'prediction_source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                            'shared_receptor_frame': 'explicitly_confirmed_by_caller'}
    return report


def summarize_runs(runs, threshold_queries=()):
    """Count runs, top-ranked poses and all poses separately, with denominators."""
    rows = [{**pose, 'run_id': run['run_id']} for run in runs for pose in run['metrics']['poses']]
    top = [row for row in rows if row['rank'] == 1]
    def subset(selected):
        comparable = [row for row in selected if row['status'] == 'comparable']
        scored = [row for row in comparable if 'model_confidence_not_reference_accuracy' in row]
        counts = []
        for confidence, rmsd in threshold_queries:
            eligible = [row for row in comparable if row.get('model_confidence_not_reference_accuracy', -np.inf) > confidence]
            matches = [row for row in eligible if row['pose_rmsd_angstrom'] < rmsd]
            counts.append({'confidence_above': confidence, 'rmsd_below_angstrom': rmsd,
                'selected_pose_count': len(selected), 'eligible_pose_count': len(eligible),
                'matching_pose_count': len(matches),
                'matching_poses': [{'run_id': row['run_id'], 'rank': row['rank']} for row in matches],
                'operators': 'strict confidence > threshold AND RMSD < threshold', 'descriptive_only': True})
        return {'pose_count': len(selected), 'comparable_pose_count': len(comparable),
            'confidence_scored_comparable_pose_count': len(scored),
            'confidence_min': min((row['model_confidence_not_reference_accuracy'] for row in scored), default=None),
            'confidence_max': max((row['model_confidence_not_reference_accuracy'] for row in scored), default=None),
            'rmsd_min_angstrom': min((row['pose_rmsd_angstrom'] for row in comparable), default=None),
            'rmsd_max_angstrom': max((row['pose_rmsd_angstrom'] for row in comparable), default=None),
            'threshold_counts': counts}
    eligible = [run for run in runs if run['metrics']['all_poses_comparable']
        and run['metrics']['rank_facts']['confidence_scored_comparable_pose_count'] == run['metrics']['requested_pose_count']]
    overlap = [run['run_id'] for run in eligible if run['metrics']['rank_facts']['best_rmsd_also_highest_confidence_ranks']]
    return {'run_count': len(runs), 'run_ids': [run['run_id'] for run in runs],
        'all_poses': subset(rows), 'top_ranked_poses': subset(top),
        'highest_confidence_overlaps_best_rmsd': {'eligible_run_count': len(eligible),
            'matching_run_count': len(overlap), 'matching_run_ids': overlap,
            'definition': 'At least one highest-confidence pose is also minimum-RMSD; includes ties. Only fully comparable, fully confidence-scored runs qualify.'}}


def compare_batch(specifications, max_matches=10000, threshold_queries=()):
    if not isinstance(specifications, list) or not 1 <= len(specifications) <= 16:
        raise ValueError('Provide one to sixteen explicitly identified runs.')
    identifiers = [run.get('run_id') for run in specifications]
    if any(not isinstance(value, str) or not value.strip() or len(value) > 128 for value in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('run_id values must be distinct nonempty strings of at most128 characters.')
    runs = []
    for specification in specifications:
        metrics = compare_files(specification['reference_file'], specification.get('result_file'),
            specification.get('prediction_file'), max_matches, threshold_queries)
        group = specification.get('group_id') or metrics['provenance']['reference_sha256']
        if not isinstance(group, str) or not group.strip() or len(group) > 128:
            raise ValueError('group_id must be a nonempty string of at most128 characters.')
        runs.append({'run_id': specification['run_id'], 'group_id': group, 'metrics': metrics})
    groups = []
    for group in dict.fromkeys(run['group_id'] for run in runs):
        members = [run for run in runs if run['group_id'] == group]
        groups.append({'group_id': group, **summarize_runs(members, threshold_queries),
            'reference_sha256s': sorted({run['metrics']['provenance']['reference_sha256'] for run in members})})
    return {'schema': 'scientific-ai/docking-multi-run-comparison/v1', 'runs': runs,
        'summary': summarize_runs(runs, threshold_queries), 'groups': groups,
        'method': runs[0]['metrics']['method'],
        'grouping': 'Explicit caller group_id; omitted groups use exact reference-file SHA-256. Group labels do not establish biological comparability.',
        'all_poses_comparable': all(run['metrics']['all_poses_comparable'] for run in runs),
        'limitations': runs[0]['metrics']['limitations'], 'inference_submitted': False,
        'rdkit_version': rdBase.rdkitVersion, 'numpy_version': np.__version__}


def write_batch_report(report, output):
    directory = output.parent
    fields = ['group_id', 'run_id', 'rank', 'status', 'pose_rmsd_angstrom', 'model_confidence_not_reference_accuracy', 'reason']
    with (directory / 'rows.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for run in report['runs']:
            writer.writerows({'group_id': run['group_id'], 'run_id': run['run_id'], **pose} for pose in run['metrics']['poses'])
    def clean(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    lines = ['# Multi-run docking analysis', '', report['method'], '', report['grouping'], '',
        '| Scope | Runs | All poses (comparable / total) | Top-ranked poses (comparable / total) | Highest-confidence overlaps best RMSD (runs / eligible runs) |',
        '|---|---:|---:|---:|---:|']
    for group in [{'group_id': 'ALL RUNS', **report['summary']}, *report['groups']]:
        all_poses, top, overlap = group['all_poses'], group['top_ranked_poses'], group['highest_confidence_overlaps_best_rmsd']
        lines.append(f"| {clean(group['group_id'])} | {group['run_count']} | {all_poses['comparable_pose_count']} / {all_poses['pose_count']} | {top['comparable_pose_count']} / {top['pose_count']} | {overlap['matching_run_count']} / {overlap['eligible_run_count']} |")
        for name, selected in [('all poses', all_poses), ('top-ranked poses', top)]:
            for query in selected['threshold_counts']:
                lines.append(f"\n{clean(group['group_id'])}, {name}: {query['matching_pose_count']} matching / {query['eligible_pose_count']} eligible / {query['selected_pose_count']} selected; confidence > {query['confidence_above']}, RMSD < {query['rmsd_below_angstrom']} Å (unrounded strict comparisons).\n")
    lines += ['', '## Per-run extrema', '', '| Run | Group | Best RMSD ranks | Worst RMSD ranks | Highest confidence ranks | Lowest confidence ranks |', '|---|---|---|---|---|---|']
    for run in report['runs']:
        facts = run['metrics']['rank_facts']
        lines.append(f"| {clean(run['run_id'])} | {clean(run['group_id'])} | {facts['best_rmsd']['ranks']} | {facts['worst_rmsd']['ranks']} | {facts['highest_confidence']['ranks']} | {facts['lowest_confidence']['ranks']} |")
    lines += ['', '## Every returned pose', '', '| Run | Rank | Status | Unfitted RMSD (Å) | Confidence |', '|---|---:|---|---:|---:|']
    for run in report['runs']:
        for pose in run['metrics']['poses']:
            lines.append(f"| {clean(run['run_id'])} | {pose['rank']} | {pose['status']} | {pose.get('pose_rmsd_angstrom', 'unavailable')} | {pose.get('model_confidence_not_reference_accuracy', 'unavailable')} |")
    lines += ['', '## Provenance and limits', '', 'Confidence is not reference accuracy, affinity or evidence of binding. A run has one supplied top-ranked pose; all-pose counts must not be described as top-ranked counts. Ties are explicitly retained. No general correlation or biological validation is inferred.',
        f"RDKit: {report['rdkit_version']}; NumPy: {report['numpy_version']}.", '', *report['limitations']]
    for run in report['runs']:
        provenance = run['metrics']['provenance']
        lines.append(f"\n{clean(run['run_id'])}: reference SHA-256 {provenance['reference_sha256']}; prediction SHA-256 {provenance['prediction_source_sha256']}.")
    (directory / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, help='One experimental/reference ligand SDF record.')
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--prediction', type=Path, help='Predicted SDF records in retained rank order.')
    sources.add_argument('--result', type=Path, help='Saved DiffDock JSON containing ligand_positions molblocks.')
    sources.add_argument('--runs', type=Path, help='JSON list of run_id, optional group_id, reference_file and exactly one result_file/prediction_file.')
    sources.add_argument('--genmol-result', type=Path, help='Raw saved GenMol JSON with molecules:[{smiles,score}]; no model call.')
    parser.add_argument('--request', type=Path, help='Original GenMol request JSON for --genmol-result.')
    parser.add_argument('--same-coordinate-frame', action='store_true',
                        help='Confirm input/output poses share the same receptor frame; do not ligand-fit.')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-matches', type=int, default=10000)
    parser.add_argument('--threshold-query', type=float, nargs=2, action='append', default=[],
                        metavar=('CONFIDENCE_ABOVE', 'RMSD_BELOW'), help='Explicit strict descriptive threshold count; never a default success criterion.')
    args = parser.parse_args()
    if args.genmol_result:
        if not args.request:
            parser.error('--genmol-result requires the original --request JSON file')
        if args.reference or args.same_coordinate_frame or args.threshold_query or args.max_matches != 10000:
            parser.error('Docking coordinate, reference and threshold options do not apply to GenMol descriptors')
        report = analyze_genmol_files(args.request, args.genmol_result)
        write_genmol_report(report, args.output)
        print(json.dumps({'schema': report['schema'], 'returned_count': report['returned_count'],
            'valid_count': report['valid_count'], 'canonical_unique_valid': report['canonical_unique_valid'],
            'quality_flags': report['quality_flags'], 'output': str(args.output)}, allow_nan=False))
        return
    if args.request:
        parser.error('--request is only used with --genmol-result')
    if not args.same_coordinate_frame:
        parser.error('--same-coordinate-frame is required for docking comparisons')
    if args.runs:
        if args.reference:
            parser.error('--runs provides each reference; do not also supply --reference')
        report = compare_batch(json.loads(args.runs.read_text()), args.max_matches, args.threshold_query)
    else:
        if not args.reference:
            parser.error('--reference is required for a single comparison')
        report = compare_files(args.reference, args.result, args.prediction, args.max_matches, args.threshold_query)
    save(args.output, report)
    (write_batch_report if args.runs else write_report)(report, args.output)
    print(json.dumps({'schema': report['schema'], 'summary': report['summary'], 'output': str(args.output)}
                     if args.runs else report, allow_nan=False))
    if not report['all_poses_comparable']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
