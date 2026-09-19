"""Future artifact indices are not coordinate semantics (actual v59 regression)."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

import scientific_study as study
import scientific_workflow_draft as draft
from scientific_study_schema import COORDINATE_INPUT_GUIDANCE, describe_workflow
import test_scientific_study as study_tests

mounted = study_tests.mounted


def batch(root):
    source = root / 'input.json'
    source.write_text('{}')
    return {'id': 'model', 'kind': 'batch', 'model': 'rfdiffusion', 'tool': 'submit_rfdiffusion',
        'operation': 'design-backbone', 'source': str(source), 'parameters': str(source),
        'media_type': 'application/json', 'semantic_type': 'rfdiffusion-design-constraint/v1',
        'entry_name': 'design_constraint', 'display_name': 'Coordinate contract test',
        'idempotency_key': 'coordinate-contract-test'}


def plan(root, method, filename):
    producer = batch(root)
    ref = {'step': 'model', 'file': filename}
    if method == 'proteinmpnn-input':
        args = {'backbone': ref, 'structure_index': 0, 'chain': {'selection': 'sole-protein-chain'},
            'num_sequences': 4, 'seed': 7, 'sampling_temp': 0.1, 'omit_aas': ['X']}
    else:
        args = {name: producer['source'] for name in
                ('design_input', 'design_result', 'refold_input', 'refold_parameters')}
        args.update(prediction=ref, structure_index=0, design_index=0,
                    prediction_chain={'selection': 'sole-protein-chain'})
    return {'schema': study.SCHEMA, 'title': 'Future coordinate type', 'steps': [producer,
        {'id': 'prepare', 'kind': 'preparation', 'method': method, 'arguments': args}],
        'deliverables': [{'name': 'report.md', 'role': 'report',
                          'source': {'step': 'prepare', 'file': 'report.md'}}]}


@pytest.mark.parametrize('method', ['proteinmpnn-input', 'design-refold-correspondence'])
@pytest.mark.parametrize('filename', ['output-00.artifact', 'output-01.artifact', 'output-100.artifact'])
def test_guessed_future_coordinate_rejected_before_admission(mounted, monkeypatch, method, filename):
    value = plan(mounted, method, filename)
    original = copy.deepcopy(value)
    monkeypatch.setattr(study, 'run_model', lambda *a: pytest.fail('No model admission'))
    with pytest.raises(ValueError, match='cannot select future batch coordinates') as failed:
        study.submit(value, mounted / 'final')
    assert filename in str(failed.value)
    assert 'output-manifest.json' in str(failed.value) and 'explicit structure_index' in str(failed.value)
    assert 'No file was substituted' in str(failed.value)
    assert value == original and not (mounted / 'final').exists() and study.list_studies() == []
    composed = draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
        'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    assert not composed['finalized'] and composed['validation_error'] == str(failed.value)
    assert json.loads(Path(composed['plan_file']).read_bytes()) == original


@pytest.mark.parametrize('method', ['proteinmpnn-input', 'design-refold-correspondence'])
def test_explicit_manifest_and_materialized_coordinates_remain_supported(mounted, method):
    value = plan(mounted, method, 'output-manifest.json')
    assert study.validate(value)
    argument = next(iter(COORDINATE_INPUT_GUIDANCE[method]))
    value['steps'][1]['arguments'][argument] = value['steps'][0]['source']
    assert study.validate(value)
    # Guaranteed earlier preparation outputs are not dynamic batch positions.
    study.coordinate_output_references({'id': 'local', 'method': method,
        'arguments': {argument: {'step': 'prep', 'file': 'backbone.pdb'}}},
        {'prep': {'kind': 'preparation', 'method': 'proteinmpnn-input'}})


def test_noncoordinate_uses_and_deliverables_keep_raw_artifact_contract(mounted):
    value = plan(mounted, 'proteinmpnn-input', 'output-manifest.json')
    raw = {'step': 'model', 'file': 'output-01.artifact'}
    value['steps'].append({'id': 'metadata', 'kind': 'preparation', 'method': 'write-json',
        'arguments': {'filename': 'path.json', 'value': {'raw_artifact': raw}}})
    value['deliverables'].append({'name': 'raw.artifact', 'role': 'data', 'source': raw})
    assert study.validate(value)
    # Structure's existing direct-coordinate contract is deliberately unchanged;
    # it has no generic manifest-to-reference preparation method today.
    study.coordinate_output_references({'id': 'compare', 'method': 'structure',
        'arguments': {'reference': raw, 'prediction': raw}}, {'model': {'kind': 'batch'}})


@pytest.mark.parametrize('method', ['proteinmpnn-input', 'design-refold-correspondence'])
def test_discovery_guidance_is_the_preflight_contract(method):
    args = describe_workflow([method])['phases'][method]['step_schema']['properties']['arguments']
    for name, guidance in COORDINATE_INPUT_GUIDANCE[method].items():
        assert guidance in args['properties'][name]['description']
    assert 'structure_index' in args['required']


@pytest.fixture
def retained_v59(mounted, monkeypatch):
    names = ['SCIENTIFIC_RETAINED_V59_04_PLAN', 'SCIENTIFIC_RETAINED_V59_04_SNAPSHOT',
             'SCIENTIFIC_RETAINED_V59_04_STUDY']
    if not all(os.environ.get(name) for name in names):
        pytest.skip('Explicit retained v59 plan/snapshot/terminal Study mounts not supplied')
    plan_path, snapshot, record_path = [Path(os.environ[name]) for name in names]
    original = plan_path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == '0a3f4b17c347533597b1ca26bf6819400867ec90ce318a4a0831217e15b2bb40'
    assert hashlib.sha256(record_path.read_bytes()).hexdigest() == '7b7121b0e2962f3928fbd657a8f270d6da05808a0d05f3c7033d82538c67fa2f'
    value, record = json.loads(original), json.loads(record_path.read_bytes())
    assert record['state'] == 'failed' and record['current_step'] == 'correspondence'
    workspace = snapshot / 'workspace'
    original_path = study.path_in_workspace

    def mapped_path(value):
        path = Path(value)
        if path.is_absolute() and path.is_relative_to('/workspace'):
            return workspace / path.relative_to('/workspace')
        if path.is_absolute() and path.is_relative_to(workspace):
            return path
        return original_path(value)

    monkeypatch.setattr(study, 'path_in_workspace', mapped_path)
    monkeypatch.setattr(study, 'run_model', lambda *a: pytest.fail('Retained replay cannot admit inference'))
    for completed in record['steps'].values():
        for item in completed['files'].values():
            path = mapped_path(item['path'])
            study.verify_file(path, item)
            item['path'] = str(path)
    record['output_directory'] = str(mounted / 'offline-only-replay')
    yield value, record, plan_path, original
    assert plan_path.read_bytes() == original


def test_actual_v59_plan_fails_before_admission_without_rewriting(retained_v59, mounted):
    value, _, _, _ = retained_v59
    before = copy.deepcopy(value)
    with pytest.raises(ValueError, match='prep-proteinmpnn argument backbone'):
        study.submit(value, mounted / 'bad-plan')
    assert value == before and study.list_studies() == [] and not (mounted / 'bad-plan').exists()
    # The actual failing correspondence still fails preflight independently
    # after only the first consumer's explicit manifest reference is corrected.
    selected = copy.deepcopy(value)
    selected['steps'][1]['arguments']['backbone']['file'] = 'output-manifest.json'
    with pytest.raises(ValueError, match='correspondence argument prediction'):
        study.submit(selected, mounted / 'still-bad-plan')
    assert study.list_studies() == [] and not (mounted / 'still-bad-plan').exists()


def test_actual_v59_explicit_manifests_replay_bytes_confidence_and_report(retained_v59):
    value, record, _, _ = retained_v59
    selected = copy.deepcopy(value)
    for step in selected['steps']:
        for name in COORDINATE_INPUT_GUIDANCE.get(step.get('method'), {}):
            step['arguments'][name]['file'] = 'output-manifest.json'
    assert study.validate(selected)
    original_steps = copy.deepcopy(record['steps'])
    for step in selected['steps']:
        if step['kind'] in study.MODEL_KINDS:
            continue  # Only the exact verified original successful operations.
        record['steps'][step['id']] = study.run_local(step, record)
    for step_id, filenames in [('prep-proteinmpnn', ['input.json', 'backbone.pdb']),
                               ('prep-esmfold2-fast', ['input.json', 'parameters.json', 'selected.fasta'])]:
        for filename in filenames:
            assert record['steps'][step_id]['files'][filename]['sha256'] == original_steps[step_id]['files'][filename]['sha256']
    esm = original_steps['esmfold2-fast']['files']
    manifest = json.loads(Path(esm['output-manifest.json']['path']).read_bytes())
    assert manifest['entries'][0]['semantic_type'] == 'protein-structure-mmcif/v1'
    assert manifest['entries'][1]['semantic_type'] == 'structure-confidence-json/v1'
    correspondence = record['steps']['correspondence']['files']
    assert correspondence['prediction.structure']['sha256'] == esm['output-00.artifact']['sha256']
    envelope = json.loads(Path(correspondence['prediction-result.json']['path']).read_bytes())
    confidence_bytes = Path(esm['output-01.artifact']['path']).read_bytes()
    assert envelope['retained_source_result']['confidence_artifact_sources'][0]['raw_json'].encode() == confidence_bytes
    from scientific_protein_preparation import structure_helper
    helper = structure_helper()
    fields, binding = helper.bound_confidence(envelope, Path(correspondence['prediction.structure']['path']).read_bytes())
    metrics = json.loads(Path(record['steps']['structure-compare']['files']['metrics.json']['path']).read_bytes())
    assert fields and all(metrics['model_confidence_not_reference_agreement'][name] == number for name, number in fields.items())
    assert metrics['confidence_binding'] == binding
    assert metrics['mapped_residues'] == 48 and metrics['correspondence_method'] == 'explicit-provenance'
    final = Path(record['steps']['report']['files']['report.md']['path']).read_text()
    for name, number in fields.items():
        assert name in final and str(number) in final
    assert all(record['steps'][name]['operation_id'] == original_steps[name]['operation_id']
               for name in ('rfd-backbone', 'proteinmpnn', 'esmfold2-fast'))
