"""Only explicitly registered same-generation confidence may accompany coordinates."""
import copy
import json
from pathlib import Path

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow
from test_scientific_protein_preparation import correspondence_fixture
from test_structure_bound_confidence import fixture


def test_explicit_metadata_is_frozen_file_input_and_exact_cli_argument(tmp_path):
    args = {'reference': 'reference.pdb', 'prediction': 'prediction.pdb', 'chain_map': ['A:A'],
            'confidence_result': 'output-manifest.json'}
    study.validate_local_arguments('structure', args)
    assert 'output-manifest.json' in study.input_references({'kind': 'analysis', 'method': 'structure', 'arguments': args})
    command = study.local_command('structure', args, tmp_path)
    assert command[command.index('--confidence-result') + 1] == 'output-manifest.json'
    assert 'confidence_result' in json.dumps(describe_workflow(['structure']))


def test_registered_correspondence_pair_is_carried_and_matches_real_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    args = correspondence_fixture(tmp_path)
    prediction = json.loads(Path(args['prediction']).read_bytes())['structure'].encode()
    *_, manifest = fixture(tmp_path, prediction)
    args['prediction'] = str(manifest)
    record = {'output_directory': str(tmp_path / 'study'), 'steps': {}}
    prepared = study.run_local({'id': 'correspond', 'kind': 'preparation',
        'method': 'design-refold-correspondence', 'arguments': args}, record)
    record['steps']['correspond'] = prepared
    step = {'id': 'compare', 'kind': 'analysis', 'method': 'structure', 'arguments': {
        'reference': {'step': 'correspond', 'file': 'reference.pdb'},
        'prediction': {'step': 'correspond', 'file': 'prediction.structure'},
        'residue_map': {'step': 'correspond', 'file': 'residue-map.json'}}}
    carried = study.paired_structure_arguments(step, record)
    assert carried['confidence_result'] == {'step': 'correspond', 'file': 'prediction-result.json'}
    result = study.run_local(step, record)
    metrics = json.loads(Path(result['files']['metrics.json']['path']).read_bytes())
    assert metrics['confidence_binding']['seed'] == 1
    assert metrics['confidence_binding']['sample_index'] == 0
    assert metrics['model_confidence_not_reference_agreement']['confidence_artifacts[1].results[0].metrics.plddt_mean'] == 0.720092236995697
    assert 'confidence_result' not in step['arguments']  # no mutation of immutable plan
    # No arbitrary direct-file / neighboring-folder metadata discovery.
    direct = copy.deepcopy(step)
    direct['arguments']['prediction'] = prepared['files']['prediction.structure']['path']
    assert 'confidence_result' not in study.paired_structure_arguments(direct, record)
    # Explicit caller binding is not silently overwritten.
    explicit = copy.deepcopy(step)
    explicit['arguments']['confidence_result'] = str(manifest)
    assert study.paired_structure_arguments(explicit, record) == explicit['arguments']
    for defect in ('other-generation', 'wrong-hash', 'wrong-method', 'unfinished'):
        changed = copy.deepcopy(record)
        producer = changed['steps']['correspond']
        if defect == 'other-generation':
            producer['files']['prediction-result.json']['path'] = str(tmp_path / 'other/prediction-result.json')
        elif defect == 'wrong-hash':
            producer['structure_confidence_pairs']['prediction.structure']['sha256'] = '0' * 64
        elif defect == 'wrong-method':
            producer['method'] = 'python-script'
        else:
            producer['state'] = 'running'
        with pytest.raises(ValueError):
            study.paired_structure_arguments(step, changed)
    # An old unregistered producer is not retroactively guessed or rewritten.
    del record['steps']['correspond']['structure_confidence_pairs']
    assert 'confidence_result' not in study.paired_structure_arguments(step, record)
