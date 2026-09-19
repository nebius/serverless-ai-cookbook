import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from rdkit import Chem

spec = importlib.util.spec_from_file_location('molecule_analysis', Path(__file__).with_name('molecule-analysis.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def molecule(smiles='CON'):
    mol = Chem.MolFromSmiles(smiles)
    conf = Chem.Conformer(mol.GetNumAtoms())
    conf.Set3D(True)
    for i in range(mol.GetNumAtoms()):
        conf.SetAtomPosition(i, (float(i * i), float(i % 2), float(i * 2)))
    mol.AddConformer(conf)
    return mol


def test_non_involutive_atom_permutation_does_not_reverse_mapping():
    reference = molecule()
    prediction = Chem.RenumberAtoms(reference, [1, 2, 0])
    result = analysis.pose_rmsd(reference, prediction)
    assert result['pose_rmsd_angstrom'] == pytest.approx(0)
    assert result['reference_to_prediction_heavy_atom_indices'] == [2, 0, 1]
    wrong = prediction.GetConformer().GetPositions() - reference.GetConformer().GetPositions()[[2, 0, 1]]
    assert np.sqrt(np.mean(np.sum(wrong ** 2, axis=1))) > 1


def test_translation_is_not_hidden_by_ligand_alignment():
    reference = molecule()
    prediction = Chem.Mol(reference)
    for i, xyz in enumerate(prediction.GetConformer().GetPositions()):
        prediction.GetConformer().SetAtomPosition(i, xyz + [3, 4, 0])
    assert analysis.pose_rmsd(reference, prediction)['pose_rmsd_angstrom'] == pytest.approx(5)


def test_symmetry_enumeration_and_incomplete_enumeration_are_explicit():
    reference = molecule('CC')
    prediction = Chem.RenumberAtoms(reference, [1, 0])
    result = analysis.pose_rmsd(reference, prediction)
    assert result['pose_rmsd_angstrom'] == 0
    assert result['symmetry_mappings_evaluated'] == 2
    with pytest.raises(ValueError, match='incomplete'):
        analysis.pose_rmsd(reference, prediction, max_matches=1)


def test_incompatible_graphs_and_stereochemistry_are_not_scored():
    with pytest.raises(ValueError, match='not comparable'):
        analysis.pose_rmsd(molecule('CON'), molecule('CCN'))
    with pytest.raises(ValueError, match='stereochemistry'):
        analysis.pose_rmsd(molecule('N[C@H](F)Cl'), molecule('N[C@@H](F)Cl'))


def test_rank_and_confidence_are_separate_from_reference_accuracy():
    reference = molecule()
    prediction = Chem.Mol(reference)
    for i, xyz in enumerate(prediction.GetConformer().GetPositions()):
        prediction.GetConformer().SetAtomPosition(i, xyz + [3, 4, 0])
    report = analysis.compare(reference, [prediction, reference], [9, -4])
    assert report['top_rank_pose_rmsd_angstrom'] == 5
    assert report['best_comparable_pose_rmsd_angstrom'] == 0
    assert report['poses'][0]['model_confidence_not_reference_accuracy'] == 9
    assert report['poses'][1]['rank'] == 2


def test_partial_graph_failure_keeps_denominator_and_no_guessed_value():
    report = analysis.compare(molecule(), [molecule(), molecule('CCN')])
    assert report['comparable_pose_count'] == 1
    assert report['requested_pose_count'] == 2
    assert not report['all_poses_comparable']
    assert 'pose_rmsd_angstrom' not in report['poses'][1]


def test_descriptive_extrema_do_not_conflate_best_geometry_and_lowest_confidence():
    rows = [{'rank': i + 1, 'status': 'comparable', 'pose_rmsd_angstrom': rmsd,
             'model_confidence_not_reference_accuracy': confidence}
            for i, (rmsd, confidence) in enumerate([(4, 0.9), (6, 0.8), (1, 0.7), (8, -1)])]
    facts, counts = analysis.rank_facts(rows)
    assert facts['best_rmsd']['ranks'] == [3]
    assert facts['worst_rmsd']['ranks'] == [4]
    assert facts['highest_confidence']['ranks'] == [1]
    assert facts['lowest_confidence']['ranks'] == [4]
    assert facts['best_rmsd_also_lowest_confidence_ranks'] == []
    assert counts == []  # No fabricated scientific cutoff.


def test_thresholds_use_unrounded_values_exact_denominators_and_strict_operators():
    rows = [{'rank': i + 1, 'status': 'comparable', 'pose_rmsd_angstrom': rmsd,
             'model_confidence_not_reference_accuracy': confidence}
            for i, (rmsd, confidence) in enumerate([(1.2109, 0.8), (1.1, 0.9), (1.2, 0.85), (0.1, 0.7)])]
    rows.append({'rank': 5, 'status': 'not_comparable', 'model_confidence_not_reference_accuracy': 0.95})
    _, counts = analysis.rank_facts(rows, [(0.7, 1.2)])
    assert counts[0]['eligible_ranks'] == [1, 2, 3]
    assert counts[0]['matching_ranks'] == [2]
    assert counts[0]['eligible_comparable_pose_count'] == 3
    assert counts[0]['matching_pose_count'] == 1


def test_rank_ties_and_missing_confidence_remain_explicit():
    rows = [{'rank': i + 1, 'status': 'comparable', 'pose_rmsd_angstrom': value}
            for i, value in enumerate([1, 1, 3])]
    facts, _ = analysis.rank_facts(rows)
    assert facts['best_rmsd']['ranks'] == [1, 2]
    assert facts['lowest_confidence'] == {'value': None, 'ranks': []}


def test_nonfinite_and_missing_coordinates_fail_explicitly():
    with pytest.raises(ValueError, match='conformer'):
        analysis.pose_rmsd(molecule(), Chem.MolFromSmiles('CON'))
    bad = molecule()
    bad.GetConformer().SetAtomPosition(0, (float('nan'), 0, 0))
    with pytest.raises(ValueError, match='non-finite'):
        analysis.pose_rmsd(molecule(), bad)


def test_cli_retains_source_hashes_and_refuses_unconfirmed_coordinate_frame(tmp_path):
    reference = tmp_path / 'reference.sdf'
    result = tmp_path / 'result.json'
    output = tmp_path / 'comparison.json'
    reference.write_text(Chem.MolToMolBlock(molecule()) + '\n$$$$\n')
    result.write_text(json.dumps({'ligand_positions': [Chem.MolToMolBlock(Chem.RenumberAtoms(molecule(), [1, 2, 0]))],
                                  'position_confidence': [-1]}))
    command = [sys.executable, spec.origin, '--reference', str(reference), '--result', str(result), '--output', str(output)]
    assert subprocess.run(command, capture_output=True).returncode != 0
    subprocess.run(command + ['--same-coordinate-frame'], capture_output=True, check=True)
    report = json.loads(output.read_text())
    assert report['best_comparable_pose_rmsd_angstrom'] == 0
    assert len(report['provenance']['reference_sha256']) == 64
    assert (tmp_path / 'comparison.rows.csv').is_file()
    text = (tmp_path / 'comparison.report.md').read_text()
    assert 'Lowest RMSD: 0.0; rank(s) [1]' in text
    assert report['provenance']['reference_sha256'] in text
    assert 'not establish monotonicity, correlation or calibration' in text


def test_multirun_denominators_do_not_confuse_top_ranked_with_all_poses(monkeypatch):
    def metrics(rmsds, confidences):
        rows = [{'rank': index + 1, 'status': 'comparable', 'pose_rmsd_angstrom': value,
                 'model_confidence_not_reference_accuracy': confidences[index]} for index, value in enumerate(rmsds)]
        facts, counts = analysis.rank_facts(rows)
        return {'poses': rows, 'rank_facts': facts, 'threshold_counts': counts,
            'all_poses_comparable': True, 'requested_pose_count': len(rows), 'method': 'test method',
            'limitations': [], 'provenance': {'reference_sha256': 'test-ref', 'prediction_source_sha256': 'test-pred'}}
    sources = {'one': metrics([1.2109, 0.3, 1.2, 0.9], [.9, .8, .75, .7]),
               'two': metrics([1.1, 0.5, 0.8, 9], [.85, .83, .8, -.5]),
               'other': metrics([5, 6], [-1, -2])}
    monkeypatch.setattr(analysis, 'compare_files', lambda _, result, *rest: sources[result])
    report = analysis.compare_batch([{'run_id': name, 'group_id': 'target' if name != 'other' else 'separate',
        'reference_file': 'unused', 'result_file': name} for name in sources], threshold_queries=[(.7, 1.2)])
    group = report['groups'][0]
    assert group['run_count'] == 2
    assert group['all_poses']['pose_count'] == 8
    assert group['top_ranked_poses']['pose_count'] == 2
    assert group['top_ranked_poses']['threshold_counts'][0]['matching_pose_count'] == 1
    assert group['top_ranked_poses']['threshold_counts'][0]['eligible_pose_count'] == 2
    assert group['all_poses']['threshold_counts'][0]['matching_pose_count'] == 4
    assert group['all_poses']['confidence_min'] == -.5
    assert report['summary']['run_count'] == 3
    assert report['summary']['all_poses']['pose_count'] == 10
    assert group['highest_confidence_overlaps_best_rmsd']['matching_run_count'] == 0


def test_multirun_partial_comparability_missing_confidence_and_ties():
    reference = molecule()
    complete = analysis.compare(reference, [reference, reference], [1, 1])
    missing_score = analysis.compare(reference, [reference])
    partial = analysis.compare(reference, [reference, molecule('CCN')], [1, 4])
    summary = analysis.summarize_runs([{'run_id': str(index), 'metrics': metrics}
        for index, metrics in enumerate([complete, missing_score, partial])])
    assert summary['all_poses']['pose_count'] == 5
    assert summary['all_poses']['comparable_pose_count'] == 4
    assert summary['top_ranked_poses']['pose_count'] == 3
    overlap = summary['highest_confidence_overlaps_best_rmsd']
    assert overlap['eligible_run_count'] == overlap['matching_run_count'] == 1
    assert overlap['matching_run_ids'] == ['0']


def test_multirun_cli_retains_original_hashes_and_complete_report(tmp_path):
    reference = tmp_path / 'reference.sdf'
    prediction = tmp_path / 'prediction.sdf'
    reference.write_text(Chem.MolToMolBlock(molecule()) + '\n$$$$\n')
    prediction.write_bytes(reference.read_bytes())
    specifications = [{'run_id': f'run-{index}', 'reference_file': str(reference),
                        'prediction_file': str(prediction)} for index in range(2)]
    source = tmp_path / 'runs.json'; source.write_text(json.dumps(specifications))
    output = tmp_path / 'metrics.json'
    subprocess.run([sys.executable, spec.origin, '--runs', str(source), '--same-coordinate-frame',
                    '--output', str(output)], capture_output=True, check=True)
    report = json.loads(output.read_text())
    assert report['summary']['run_count'] == 2
    assert len(report['groups']) == 1  # Default exact-reference-hash grouping.
    assert report['groups'][0]['group_id'] == report['runs'][0]['metrics']['provenance']['reference_sha256']
    assert '| ALL RUNS | 2 | 2 / 2 | 2 / 2 | 0 / 0 |' in (tmp_path / 'report.md').read_text()
    assert len((tmp_path / 'rows.csv').read_text().splitlines()) == 3
    with pytest.raises(ValueError, match='distinct'):
        analysis.compare_batch([specifications[0], specifications[0]])
