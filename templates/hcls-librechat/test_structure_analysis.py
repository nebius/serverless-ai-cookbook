import importlib.util
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from Bio.PDB import MMCIFIO, PDBParser

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
    if problem == 'hash':
        document['reference_sha256'] = '0' * 64
    if problem == 'duplicate':
        document['pairs'].append(document['pairs'][0])
    if problem == 'absent':
        document['pairs'][0]['reference_residue'] = [' ', 999, ' ']
    if problem == 'few':
        document['pairs'] = document['pairs'][:2]
    if problem == 'chain':
        document['pairs'][0]['reference_chain'] = 'Z'
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


def test_commented_cif_and_openfold_nested_results_preserve_repeated_structures(tmp_path):
    text = pdb({'A': COORDS})
    writer = MMCIFIO()
    writer.set_structure(PDBParser(QUIET=True).get_structure('reference', io.StringIO(text)))
    stream = io.StringIO()
    writer.save(stream)
    cif = '# generated coordinate file\n\n' + stream.getvalue()
    result = {'outputs': [{'structures_with_scores': [
        {'structure': cif, 'confidence': 0.8}, {'structure': cif, 'confidence': 0.7}]}]}
    assert analysis.structures(result) == [cif, cif]
    reference, source, output = tmp_path / 'ref.pdb', tmp_path / 'result.json', tmp_path / 'analysis'
    reference.write_text(text)
    source.write_text(json.dumps(result))
    subprocess.run([sys.executable, spec.origin, '--reference', str(reference), '--result', str(source),
        '--structure-index', '1', '--output-dir', str(output)], check=True, capture_output=True)
    metrics = json.loads((output / 'metrics.json').read_text())
    assert (output / 'prediction.cif').read_text() == cif
    assert metrics['global_ca_rmsd_angstrom'] < 1e-5
    assert metrics['sampling_provenance']['extracted_structure_index'] == 1
    assert metrics['sampling_provenance']['structure_index_is_seed'] is False


def test_cli_records_exact_bytes_and_declared_request_not_filename_seed(tmp_path):
    original = pdb({'A': COORDS}).replace('\n', '\r\n').encode()
    reference, prediction, request = [tmp_path / name for name in ('ref.pdb', 'seed7.pdb', 'request.json')]
    reference.write_bytes(original)
    prediction.write_bytes(original)
    request.write_bytes(b'{"arguments":{"model_seeds":[42],"num_samples":4},"sequence":"PRIVATE"}\n')
    output = tmp_path / 'output'
    subprocess.run([sys.executable, spec.origin, '--reference', str(reference), '--prediction', str(prediction),
        '--request-file', str(request), '--output-dir', str(output)], check=True, capture_output=True)
    metrics = json.loads((output / 'metrics.json').read_text())
    assert metrics['provenance']['reference_sha256'] == hashlib.sha256(original).hexdigest()
    assert metrics['provenance']['prediction_sha256'] == hashlib.sha256(original).hexdigest()
    assert metrics['provenance']['request_sha256'] == hashlib.sha256(request.read_bytes()).hexdigest()
    assert (output / 'prediction.pdb').read_bytes() == original
    sampling = metrics['sampling_provenance']
    assert sampling['request_fields'] == [
        {'json_pointer': '/arguments/model_seeds', 'value': [42], 'status': 'recorded'},
        {'json_pointer': '/arguments/num_samples', 'value': 4, 'status': 'recorded'}]
    assert sampling['determinism_established'] is False
    report = (output / 'report.md').read_text()
    assert 'PRIVATE' not in report and 'seed7' not in report
    assert '**not a seed**' in report and '| A | A | 4 / 4 | 4 / 4 |' in report
    assert metrics['units']['rmsd'] == 'angstrom'


def test_sampling_unknown_and_invalid_values_are_not_invented():
    assert 'unknown' in analysis.sampling_provenance(None, 3)['request_status']
    value = analysis.sampling_provenance(b'{"seed":true,"nested/~":[{"random_seeds":[1,2]}]}', 0)
    assert value['request_fields'] == [
        {'json_pointer': '/seed', 'value': None, 'status': 'unsupported_sampling_value_not_interpreted'},
        {'json_pointer': '/nested~1~0/0/random_seeds', 'value': [1, 2], 'status': 'recorded'}]
    with pytest.raises(ValueError, match='JSON object'):
        analysis.sampling_provenance(b'[42]', 0)


def test_uploaded_complex_array_keeps_record_pointers_without_seed_association():
    source = b'[{"name":"complex-a","model_seeds":[7],"sequences":[{"proteinChain":{"sequence":"AAAA","count":1}}]}, {"name":"complex-b","seed":42}]\n'
    value = analysis.sampling_provenance(source, 1)
    assert value['request_document_shape'] == 'array-of-objects'
    assert value['request_record_count'] == 2
    assert value['request_fields'] == [
        {'json_pointer': '/0/model_seeds', 'value': [7], 'status': 'recorded'},
        {'json_pointer': '/1/seed', 'value': 42, 'status': 'recorded'}]
    assert value['request_sha256'] == hashlib.sha256(source).hexdigest()
    assert value['structure_index_is_seed'] is False
    assert value['determinism_established'] is False
    assert 'not established' in value['request_record_association']
    for invalid in (b'[]', b'[{} , null]', b'["request"]', b'null'):
        with pytest.raises(ValueError, match='array of request objects'):
            analysis.sampling_provenance(invalid, 0)


@pytest.mark.parametrize('request_bytes', [
    b'[{"name":"complex-a","sequences":[{"proteinChain":{"sequence":"AAAA","count":1}}]}]',
    b'[{"name":"complex-b","sequences":[{"proteinChain":{"sequence":"AAAA","count":1}}]}]',
])
def test_array_request_cli_publishes_all_measured_outputs(tmp_path, request_bytes):
    original = pdb({'A': COORDS}).encode()
    reference, prediction, source = [tmp_path / name for name in ('ref.pdb', 'prediction.pdb', 'request.json')]
    reference.write_bytes(original)
    prediction.write_bytes(original)
    source.write_bytes(request_bytes)
    output = tmp_path / 'comparison'
    subprocess.run([sys.executable, spec.origin, '--reference', str(reference), '--prediction', str(prediction),
                    '--request-file', str(source), '--output-dir', str(output)], check=True, capture_output=True)
    metrics = json.loads((output / 'metrics.json').read_bytes())
    assert metrics['global_ca_rmsd_angstrom'] < 1e-6
    assert metrics['mapped_residues'] == 4
    assert metrics['sampling_provenance']['request_fields'] == []  # No invented seed.
    assert metrics['provenance']['request_sha256'] == hashlib.sha256(request_bytes).hexdigest()
    assert {'metrics.json', 'report.md', 'methods.md', 'residue-mapping.json', 'prediction.pdb'} <= {p.name for p in output.iterdir()}
    assert 'Mapped residues: 4' in (output / 'report.md').read_text()


def test_report_preserves_bad_complex_geometry_and_actual_denominators():
    first = np.array(COORDS)
    metrics, _ = analysis.compare(pdb({'A': first, 'D': first + [0, 0, 4]}),
        pdb({'B': first, 'C': first + [0, 0, 24]}), [('A', 'B'), ('D', 'C')])
    report = analysis.report_markdown(metrics)
    assert metrics['global_ca_rmsd_angstrom'] > 9
    assert f"**{metrics['global_ca_rmsd_angstrom']:.12g} Å**" in report
    assert f"Recovered reference contacts: 0 / {metrics['interface']['native_contacts_mapped_residues']}" in report
    assert 'Mapped residues: 8; identical sequence matches: 8.' in report
    assert 'not experimental, functional or clinical validation' in report
    assert 'None (zero-based when supplied' in report  # No absent structure index invented.


@pytest.mark.parametrize('cutoff', [True, 0, -1, float('nan'), float('inf'), '5'])
def test_invalid_contact_units_rejected(cutoff):
    with pytest.raises(ValueError, match='finite positive distance'):
        analysis.compare(pdb({'A': COORDS}), pdb({'A': COORDS}), cutoff=cutoff)


def test_boolean_or_nonfinite_confidence_is_not_a_measurement():
    assert analysis.confidence_fields({'plddt': [True, False], 'confidence': float('nan')}) == {}


def test_repeated_chain_map_flags_never_silently_drop_prior_pairs(tmp_path):
    reference, prediction = tmp_path / 'ref.pdb', tmp_path / 'pred.pdb'
    reference.write_text(pdb({'E': COORDS, 'I': np.array(COORDS) + [0, 0, 4]}))
    prediction.write_text(pdb({'A': COORDS, 'B': np.array(COORDS) + [0, 0, 4]}))
    completed = subprocess.run([sys.executable, spec.origin, '--reference', str(reference),
        '--prediction', str(prediction), '--chain-map', 'E:A', '--chain-map', 'I:B',
        '--output-dir', str(tmp_path / 'output')], check=True, capture_output=True, text=True)
    metrics = json.loads(completed.stdout)['metrics']
    assert metrics['chain_mapping'] == [['E', 'A'], ['I', 'B']]
    assert metrics['mapped_residues'] == 8 and metrics['excluded_reference_chains'] == []
