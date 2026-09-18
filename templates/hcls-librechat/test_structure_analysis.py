import importlib.util
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
