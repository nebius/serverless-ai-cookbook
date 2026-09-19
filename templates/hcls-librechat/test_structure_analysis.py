import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('structure_analysis', Path(__file__).with_name('structure-analysis.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def pdb(chains, transform=None):
    rows, serial = [], 0
    for chain_id, coordinates in chains.items():
        for index, xyz in enumerate(coordinates, 1):
            xyz = transform(np.array(xyz, dtype=float)) if transform else xyz
            serial += 1
            rows.append(f'ATOM  {serial:5d}  CA  ALA {chain_id}{index:4d}    '
                        f'{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 90.00           C  ')
        rows.append('TER')
    return '\n'.join(rows) + '\nEND\n'


COORDS = [(0, 0, 0), (3.8, 0, 0), (3.8, 3.8, 0), (0, 3.8, 1)]


def test_rigid_transform_aligns_and_confidence_remains_separate():
    reference = pdb({'A': COORDS})
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    prediction = pdb({'B': COORDS}, lambda xyz: xyz @ rotation + [10, -4, 3])
    metrics, mapping = analysis.compare(reference, prediction, [('A', 'B')])
    assert metrics['global_ca_rmsd_angstrom'] < 1e-5
    assert metrics['chains'][0]['reference_coverage'] == 1
    assert len(mapping) == 4
    assert analysis.confidence_fields({'structures': [{'confidence': 0.9, 'plddt': [60, 80]}]}) == {
        'structures[0].confidence': 0.9,
        'structures[0].plddt': {'count': 2, 'mean': 70.0, 'min': 60.0, 'max': 80.0}}


def test_complex_separation_cannot_hide_behind_independent_chain_fits():
    first = np.array(COORDS)
    second = first + [0, 0, 4]
    reference = pdb({'A': first, 'D': second})
    prediction = pdb({'B': first, 'C': second + [0, 0, 20]})
    with pytest.raises(ValueError, match='explicit'):
        analysis.compare(reference, prediction)
    metrics, _ = analysis.compare(reference, prediction, [('A', 'B'), ('D', 'C')])
    assert all(chain['independently_fitted_ca_rmsd_angstrom'] < 1e-5 for chain in metrics['chains'])
    assert metrics['global_ca_rmsd_angstrom'] > 9
    assert metrics['interface']['fraction_native_contacts_mapped_residues'] == 0
    assert metrics['interface']['native_contacts_mapped_residues'] > 0
    assert metrics['interface']['interface_ca_rmsd_angstrom'] > 9
    with pytest.raises(ValueError, match='one-to-one'):
        analysis.compare(reference, prediction, [('A', 'B'), ('A', 'C')])


def test_reflection_is_not_a_valid_rigid_rotation_and_missing_residues_are_visible():
    reference = pdb({'A': COORDS})
    prediction = pdb({'A': COORDS}, lambda xyz: xyz * [-1, 1, 1])
    assert analysis.compare(reference, prediction)[0]['global_ca_rmsd_angstrom'] > 0.1
    cropped = pdb({'A': COORDS[:3]})
    assert analysis.compare(reference, cropped)[0]['chains'][0]['reference_coverage'] == 0.75


def test_cli_saves_actual_metrics_methods_residue_mapping_and_extracted_coordinates(tmp_path):
    reference = tmp_path / 'reference.pdb'
    result = tmp_path / 'result.json'
    reference.write_text(pdb({'A': COORDS}))
    result.write_text(json.dumps({'structures_in_ranked_order': [{'structure': reference.read_text(), 'confidence': 0.8}]}))
    output = tmp_path / 'analysis'
    completed = subprocess.run([sys.executable, spec.origin, '--reference', str(reference), '--result', str(result),
                                '--output-dir', str(output)], text=True, capture_output=True, check=True)
    summary = json.loads(completed.stdout)
    assert summary['metrics']['global_ca_rmsd_angstrom'] < 1e-5
    assert (output / 'prediction.pdb').read_text() == reference.read_text()
    assert len(json.loads((output / 'residue-mapping.json').read_text())) == 4
    assert 'not DockQ' in (output / 'methods.md').read_text()
    assert summary['metrics']['provenance']['reference_sha256']


def test_no_coordinates_missing_chain_and_invalid_comparison_fail_explicitly():
    assert analysis.structures({'artifact': {'artifact_id': 'not-inline'}}) == []
    with pytest.raises(ValueError, match='Absent chain'):
        analysis.compare(pdb({'A': COORDS}), pdb({'B': COORDS}), [('D', 'B')])
    with pytest.raises(ValueError, match='Fewer than three'):
        analysis.compare(pdb({'A': COORDS[:2]}), pdb({'B': COORDS[:2]}))


def test_reversed_chain_map_reports_actual_ids_and_direction_without_swapping():
    reference = pdb({'E': COORDS, 'I': np.array(COORDS) + [0, 0, 4]})
    prediction = pdb({'A': COORDS, 'B': np.array(COORDS) + [0, 0, 4]})
    with pytest.raises(ValueError) as error:
        analysis.compare(reference, prediction, [('A', 'E'), ('B', 'I')])
    message = str(error.value)
    assert 'reference:prediction (REF:PRED)' in message
    assert 'Requested: A:E, B:I' in message
    assert "reference protein chains: ['E', 'I']" in message
    assert "prediction protein chains: ['A', 'B']" in message
    assert 'not automatically swapped' in message
    metrics, _ = analysis.compare(reference, prediction, [('E', 'A'), ('I', 'B')])
    assert metrics['global_ca_rmsd_angstrom'] < 1e-5


def correspondence(reference, prediction, count=4):
    return {'schema': 'scientific-residue-correspondence/v1',
            'description': 'Designed backbone was sequence-redesigned without deleting or inserting positions.',
            'reference_sha256': hashlib.sha256(reference.encode()).hexdigest(),
            'prediction_sha256': hashlib.sha256(prediction.encode()).hexdigest(),
            'pairs': [{'reference_chain': 'A', 'prediction_chain': 'B',
                       'reference_residue': [' ', i, ' '], 'prediction_residue': [' ', i, ' ']}
                      for i in range(1, count + 1)]}


def test_explicit_design_correspondence_does_not_require_unchanged_sequence():
    reference = pdb({'A': COORDS})
    prediction = pdb({'B': COORDS}, lambda xyz: xyz + [5, 4, 3]).replace('ALA', 'GLY')
    with pytest.raises(ValueError, match='identical aligned'):
        analysis.compare(reference, prediction)
    metrics, mapping = analysis.compare(reference, prediction,
        residue_correspondence=correspondence(reference, prediction))
    assert metrics['global_ca_rmsd_angstrom'] < 1e-5
    assert metrics['mapped_residues'] == 4 and metrics['matched_identical_residues'] == 0
    assert metrics['chains'][0]['reference_coverage'] == 1
    assert metrics['correspondence_method'] == 'explicit-provenance'
    assert len(mapping) == 4


@pytest.mark.parametrize('problem', ['hash', 'duplicate', 'absent', 'few', 'chain'])
def test_incorrect_design_correspondence_is_not_silently_accepted(problem):
    reference, prediction = pdb({'A': COORDS}), pdb({'B': COORDS})
    document = correspondence(reference, prediction)
    if problem == 'hash': document['reference_sha256'] = '0' * 64
    if problem == 'duplicate': document['pairs'].append(document['pairs'][0])
    if problem == 'absent': document['pairs'][0]['reference_residue'] = [' ', 999, ' ']
    if problem == 'few': document['pairs'] = document['pairs'][:2]
    if problem == 'chain': document['pairs'][0]['reference_chain'] = 'Z'
    with pytest.raises(ValueError):
        analysis.compare(reference, prediction, residue_correspondence=document)


def test_design_cli_saves_explicit_method_and_real_mapping(tmp_path):
    reference, prediction = pdb({'A': COORDS}), pdb({'B': COORDS}).replace('ALA', 'GLY')
    ref, pred, mapping = [tmp_path / name for name in ('ref.pdb', 'pred.pdb', 'map.json')]
    ref.write_text(reference)
    pred.write_text(prediction)
    mapping.write_text(json.dumps(correspondence(reference, prediction)))
    output = tmp_path / 'analysis'
    subprocess.run([sys.executable, spec.origin, '--reference', str(ref), '--prediction', str(pred),
                    '--residue-map', str(mapping), '--output-dir', str(output)], check=True, capture_output=True)
    metrics = json.loads((output / 'metrics.json').read_text())
    assert metrics['mapped_residues'] == 4 and metrics['matched_identical_residues'] == 0
    assert metrics['provenance']['residue_map_sha256']
    assert 'Explicit provenance-backed' in (output / 'methods.md').read_text()
