"""Direct selected batch coordinates retain only their own recorded metadata."""
import copy
import json
from pathlib import Path

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow
from test_scientific_protein_preparation import correspondence_fixture
from test_structure_bound_confidence import fixture


def recorded_prediction(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    args = correspondence_fixture(tmp_path)
    prediction = json.loads(Path(args['prediction']).read_bytes())['structure'].encode()
    *_, manifest = fixture(tmp_path, prediction)
    files = {p.name: study.measure(p) for p in (manifest, tmp_path / 'output-00.artifact', tmp_path / 'output-01.artifact')}
    record = {'output_directory': str(tmp_path / 'study'), 'steps': {
        'refold': {'state': 'completed', 'operation_id': 'original-refold-operation', 'files': files}}}
    args['prediction'] = {'step': 'refold', 'file': 'output-00.artifact'}
    step = {'id': 'correspond', 'kind': 'preparation', 'method': 'design-refold-correspondence', 'arguments': args}
    return step, record


def test_recorded_direct_coordinate_gets_own_manifest_without_plan_mutation(tmp_path, monkeypatch):
    step, record = recorded_prediction(tmp_path, monkeypatch)
    original = copy.deepcopy((step, record))
    bound = study.paired_structure_arguments(step, record)
    assert bound['prediction'] == {'step': 'refold', 'file': 'output-00.artifact'}
    assert bound['confidence_result'] == {'step': 'refold', 'file': 'output-manifest.json'}
    assert (step, record) == original
    study.validate_local_arguments('design-refold-correspondence', bound)
    assert bound['confidence_result'] in study.input_references({**step, 'arguments': bound})
    assert 'confidence_result' in json.dumps(describe_workflow(['design-refold-correspondence']))


@pytest.mark.parametrize('defect', ['unfinished', 'no-operation', 'other-directory', 'tampered', 'duplicate-entry', 'wrong-coordinate', 'wrong-contract', 'wrong-file-position'])
def test_recorded_manifest_cannot_cross_operation_or_coordinate_identity(tmp_path, monkeypatch, defect):
    step, record = recorded_prediction(tmp_path, monkeypatch)
    producer = record['steps']['refold']
    files = producer['files']
    manifest = Path(files['output-manifest.json']['path'])
    if defect == 'unfinished':
        producer['state'] = 'running'
    elif defect == 'no-operation':
        del producer['operation_id']
    elif defect == 'other-directory':
        files['output-manifest.json']['path'] = str(tmp_path / 'other/output-manifest.json')
    elif defect == 'tampered':
        (tmp_path / 'output-00.artifact').write_bytes(b'changed')
    elif defect == 'wrong-file-position':
        alternate = tmp_path / 'output-09.artifact'
        alternate.write_bytes((tmp_path / 'output-00.artifact').read_bytes())
        files['output-09.artifact'] = study.measure(alternate)
        step['arguments']['prediction']['file'] = 'output-09.artifact'
    else:
        body = json.loads(manifest.read_bytes())
        if defect == 'duplicate-entry':
            body['entries'].append(copy.deepcopy(body['entries'][0]))
        elif defect == 'wrong-coordinate':
            body['entries'][0]['artifact']['sha256'] = 'f' * 64
        else:
            body['schema'] = 'unrelated/v1'
        manifest.write_text(json.dumps(body))
        files['output-manifest.json'] = study.measure(manifest)
    with pytest.raises(RuntimeError if defect == 'tampered' else ValueError):
        study.paired_structure_arguments(step, record)


def test_literal_paths_and_unrecorded_neighbors_are_not_metadata_bindings(tmp_path, monkeypatch):
    step, record = recorded_prediction(tmp_path, monkeypatch)
    direct = copy.deepcopy(step)
    direct['arguments']['prediction'] = str(tmp_path / 'output-00.artifact')
    assert study.paired_structure_arguments(direct, record) == direct['arguments']
    del record['steps']['refold']['files']['output-manifest.json']
    assert study.paired_structure_arguments(step, record) == step['arguments']
    explicit = {**step, 'arguments': {**step['arguments'], 'confidence_result': str(tmp_path / 'output-manifest.json')}}
    assert study.paired_structure_arguments(explicit, record) == explicit['arguments']


def test_direct_coordinate_correspondence_then_result_analysis_keeps_native_confidence(tmp_path, monkeypatch):
    step, record = recorded_prediction(tmp_path, monkeypatch)
    original_files = copy.deepcopy(record['steps']['refold']['files'])
    result = study.run_local(step, record)
    record['steps']['correspond'] = result
    assert 'prediction.structure' in result['structure_confidence_pairs']
    selected = Path(result['files']['prediction.structure']['path']).read_bytes()
    assert selected == (tmp_path / 'output-00.artifact').read_bytes()
    compared = study.run_local({'id': 'compare', 'kind': 'analysis', 'method': 'structure', 'arguments': {
        'reference': {'step': 'correspond', 'file': 'reference.pdb'},
        'result': {'step': 'correspond', 'file': 'prediction-result.json'},
        'residue_map': {'step': 'correspond', 'file': 'residue-map.json'}}}, record)
    metrics = json.loads(Path(compared['files']['metrics.json']['path']).read_bytes())
    assert metrics['confidence_binding']['status'] == 'exact_structure_sha256_and_size_match'
    assert metrics['confidence_binding']['seed'] == 1
    assert metrics['confidence_binding']['sample_index'] == 0
    assert metrics['model_confidence_not_reference_agreement']['confidence_artifacts[1].results[0].metrics.plddt_mean'] == 0.720092236995697
    for item in original_files.values():
        assert study.measure(Path(item['path'])) == item
