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
