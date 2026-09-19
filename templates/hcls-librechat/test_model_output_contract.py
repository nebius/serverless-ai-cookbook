"""Native input.json publication regression from the retained v56 complex study."""
import copy
import json
from pathlib import Path

import pytest

import scientific_study as study
import scientific_workflow_draft as draft
from scientific_study_schema import describe_workflow, known_output_files
import test_scientific_study as study_tests

mounted = study_tests.mounted


def native_plan(root, filename='input.json'):
    source = root / 'original-boltz-request.json'
    source.write_bytes(b'{"polymers": [{"id": "A", "sequence": "ACD"}]}\n')
    return {'schema': study.SCHEMA, 'title': 'Original complex output-contract regression',
        'steps': [{'id': 'boltz2-1acb', 'kind': 'native', 'model': 'boltz2',
                   'input': str(source), 'idempotency_key': 'retained-contract-test'}],
        'deliverables': [
            {'name': 'result.json', 'role': 'report', 'source': {'step': 'boltz2-1acb', 'file': 'result.json'}},
            {'name': 'boltz2-1acb-request.json', 'role': 'provenance',
             'source': {'step': 'boltz2-1acb', 'file': filename}}]}


def test_actual_native_input_alias_rejected_before_any_admission(mounted, monkeypatch):
    value = native_plan(mounted)
    original = copy.deepcopy(value)
    monkeypatch.setattr(study, 'run_model', lambda *args: pytest.fail('No inference permitted'))
    with pytest.raises(ValueError, match='cannot publish.*input.json') as failed:
        study.submit(value, mounted / 'final')
    assert 'original input file' in str(failed.value)
    assert value == original and not (mounted / 'final').exists()
    assert study.list_studies() == []
    composed = draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
        'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    assert not composed['finalized'] and composed['validation_error'] == str(failed.value)
    assert json.loads(Path(composed['plan_file']).read_bytes()) == original
    assert study.list_studies() == []


def test_exact_original_input_is_frozen_not_copied_or_rewritten(mounted):
    value = native_plan(mounted)
    original_input = Path(value['steps'][0]['input'])
    before = original_input.read_bytes()
    value['deliverables'][1]['source'] = str(original_input)
    assert study.validate(value)[str(original_input)] == study.measure(original_input)
    assert original_input.read_bytes() == before and not (mounted / 'input.json').exists()
    prepared = {'id': 'prepare', 'kind': 'preparation', 'method': 'write-json',
                'arguments': {'filename': 'exact-request.json', 'value': {'sequence': 'ACD'}}}
    value['steps'].insert(0, prepared)
    value['steps'][1]['input'] = {'step': 'prepare', 'file': 'exact-request.json'}
    value['deliverables'][1]['source'] = copy.deepcopy(value['steps'][1]['input'])
    assert study.validate(value) == {}


@pytest.mark.parametrize('kind,filename', [
    ('native', 'input.json'), ('native', 'request.json'), ('native', 'result.pdb'),
    ('native', './result.json'), ('batch', 'input.json'), ('batch', 'parameters.json'),
    ('batch', 'prediction.cif'), ('batch', 'output-0.artifact'),
    ('batch', 'output-000.artifact'), ('batch', 'output-00.artifact\n')])
def test_impossible_client_names_rejected(kind, filename):
    with pytest.raises(ValueError, match='cannot publish'):
        study.known_output_reference({'step': 'model', 'file': filename}, {'model': {'kind': kind}})


@pytest.mark.parametrize('kind,filename', [
    ('native', 'operation.json'), ('native', 'schema.json'), ('native', 'submission.json'),
    ('native', 'result.json'), ('native', 'result-envelope.json'), ('native', 'result-artifact.json'),
    *[('native', 'result.' + ext) for ext in ('mp4','webm','png','jpg','wav','mp3','ogg','bin')],
    ('batch', 'request.json'), ('batch', 'output-manifest.json'), ('batch', 'input-manifest.json'),
    ('batch', 'status.json'), ('batch', 'result.json'), ('batch', 'output-00.artifact'),
    ('batch', 'output-99.artifact'), ('batch', 'output-100.artifact')])
def test_published_client_names_remain_possible_not_guaranteed(kind, filename):
    study.known_output_reference({'step': 'model', 'file': filename}, {'model': {'kind': kind}})


def test_discovery_and_preflight_share_actual_contract():
    phases = describe_workflow(['native', 'batch'])['phases']
    for kind, descriptor in phases.items():
        assert set(descriptor['possible_exact_files']) == known_output_files({'kind': kind})
        assert 'input.json' not in descriptor['possible_exact_files']
        assert 'receipt.json' not in descriptor['possible_exact_files']
    assert 'original input file' in ' '.join(phases['native']['conditional'])
    assert phases['batch']['possible_filename_fullmatch_patterns']
    structure = describe_workflow(['structure'])['phases']['structure']['step_schema']
    assert 'original native input or batch request.json' in structure['properties']['arguments']['properties']['request_file']['description']
    assert 'original input reference' in phases['native']['step_schema']['properties']['input']['description']


def test_dependent_analysis_uses_same_model_output_preflight(mounted):
    value = native_plan(mounted, 'result.json')
    value['steps'].append({'id': 'report', 'kind': 'analysis', 'method': 'write-json',
        'arguments': {'filename': 'report.json', 'value': {'request': {'step': 'boltz2-1acb', 'file': 'input.json'}}}})
    with pytest.raises(ValueError, match='cannot publish.*input.json'):
        study.validate(value)


def test_possible_conditional_file_is_still_required_at_publication(mounted):
    value = native_plan(mounted, 'result.mp4')
    assert study.validate(value)
    # Preflight permits only the true conditional contract; it never aliases a
    # JSON result to media or manufactures its bytes after inference.
    with pytest.raises(ValueError, match='not verified and complete'):
        study.resolve(value['deliverables'][1]['source'], {'steps': {
            'boltz2-1acb': {'state': 'completed', 'files': {}}}})
