"""Known helper filenames fail before admission, not final publication."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

import scientific_study as study
import scientific_workflow_draft as draft
from scientific_study_schema import PHASE_OUTPUTS, describe_workflow, known_output_files
from test_structure_analysis import COORDS, pdb


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'output-test-only')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'outputs@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model transport is needed'))
    return tmp_path


def comparison_plan(folder, filename='residue-mapping.json'):
    source = folder / 'reference.pdb'
    source.write_text(pdb({'A': COORDS}))
    return {'schema': study.SCHEMA, 'title': 'Retained structural comparison', 'steps': [
        {'id': 'compare', 'kind': 'analysis', 'method': 'structure', 'arguments': {
            'reference': str(source), 'prediction': str(source), 'chain_map': ['A:A']}}],
        'deliverables': [
            {'name': 'report.md', 'role': 'report', 'source': {'step': 'compare', 'file': 'report.md'}},
            {'name': 'mapping.json', 'role': 'data', 'source': {'step': 'compare', 'file': filename}}]}


@pytest.mark.parametrize('filename', ['residue-map.csv', 'residue-map.json', 'mapping.csv', './residue-mapping.json'])
def test_impossible_structure_filename_rejected_without_admission_or_rename(mounted, filename):
    value = comparison_plan(mounted, filename)
    original = copy.deepcopy(value)
    with pytest.raises(ValueError, match='cannot publish') as failed:
        study.submit(value, mounted / 'final')
    assert filename in str(failed.value) and 'residue-mapping.json' in str(failed.value)
    assert value == original and not (mounted / 'final').exists() and study.list_studies() == []
    composed = draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
                              'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    assert not composed['finalized'] and composed['validation_error'] == str(failed.value)
    assert json.loads(Path(composed['plan_file']).read_bytes()) == original
    assert study.list_studies() == []


def test_dependent_input_names_use_same_preflight(mounted):
    value = comparison_plan(mounted)
    value['steps'].append({'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
        'title': 'Final report', 'sections': [{'title': 'Mapping', 'format': 'csv',
            'file': {'step': 'compare', 'file': 'residue-map.csv'}}]}})
    with pytest.raises(ValueError, match='residue-mapping.json'):
        study.validate(value)
    assert study.list_studies() == []


def test_corrected_draft_completes_real_helper_and_preserves_failed_revision(mounted):
    value = comparison_plan(mounted, 'residue-map.csv')
    first = draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
                           'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    before = Path(first['plan_file']).read_bytes()
    value['deliverables'][1]['source']['file'] = 'residue-mapping.json'
    fixed = draft.compose({'draft_directory': str(mounted / 'draft'), 'expected_sha256': first['sha256'],
                           'deliverables': value['deliverables'], 'finalize': True})
    assert fixed['finalized'] and Path(first['plan_file']).read_bytes() == before
    accepted = study.submit(json.loads(Path(fixed['plan_file']).read_bytes()), mounted / 'final')
    assert study.submit(value, mounted / 'final')['id'] == accepted['id']
    asyncio.run(study.advance(accepted['id']))
    complete = asyncio.run(study.advance(accepted['id']))
    assert complete['state'] == 'completed', complete
    actual = set(complete['steps']['compare']['files'])
    descriptor = describe_workflow(['structure'])['phases']['structure']
    assert actual == set(descriptor['always_on_success']) | {'prediction.pdb'}
    assert actual <= set(descriptor['possible_exact_files']) == known_output_files(value['steps'][0])
    assert 'prediction.cif' in descriptor['possible_exact_files'] and 'prediction.cif' not in actual
    mapping = next(item for item in complete['artifacts'] if item['name'] == 'mapping.json')
    assert len(json.loads(Path(mapping['path']).read_bytes())) == len(COORDS)


@pytest.mark.parametrize('kind', ['npz', 'hdf5', 'zip', 'sqlite'])
def test_export_contract_only_contains_requested_formats(kind):
    step = {'method': 'parquet-export', 'arguments': {'formats': [kind]}}
    expected = 'data.' + {'hdf5': 'h5'}.get(kind, kind)
    assert known_output_files(step) == {'comparison.json', 'report.md', expected}
    study.known_output_reference({'step': 'export', 'file': expected}, {'export': step})
    with pytest.raises(ValueError, match='cannot publish'):
        study.known_output_reference({'step': 'export', 'file': 'wrong.csv'}, {'export': step})


@pytest.mark.parametrize('method', ['proteinmpnn-input', 'esmfold2-fast-input', 'design-refold-correspondence'])
def test_fixed_preparation_outputs_reuse_discovery_contract(method):
    assert known_output_files({'method': method}) == set(PHASE_OUTPUTS[method][0])


def test_saved_script_names_are_not_guessed_from_standard_helpers(mounted):
    script = mounted / 'analysis.py'
    script.write_text('# Frozen scientific code; not executed during preflight.\n')
    step = {'id': 'script', 'kind': 'analysis', 'method': 'python-script', 'arguments': {
        'script': str(script), 'inputs': [], 'parameters': {}, 'outputs': ['custom/report.md', 'records']}}
    assert known_output_files(step) == set(PHASE_OUTPUTS['python-script'][0]) | {'custom/report.md', 'records'}
    value = {'schema': study.SCHEMA, 'title': 'Custom analysis', 'steps': [step], 'deliverables': [
        {'name': 'report.md', 'role': 'report', 'source': {'step': 'script', 'file': 'custom/report.md'}}]}
    assert set(study.validate(value)) == {str(script)}
    value['deliverables'][0]['source']['file'] = 'report.md'
    with pytest.raises(ValueError, match='custom/report.md'):
        study.validate(value)


def test_write_json_uses_exact_plan_declared_filename(mounted):
    step = {'id': 'write', 'kind': 'preparation', 'method': 'write-json',
            'arguments': {'filename': 'measurement.json', 'value': {'measured': 7}}}
    assert known_output_files(step) == {'measurement.json'}
    study.known_output_reference({'step': 'write', 'file': 'measurement.json'}, {'write': step})
    with pytest.raises(ValueError, match='measurement.json'):
        study.known_output_reference({'step': 'write', 'file': 'data.json'}, {'write': step})


@pytest.mark.parametrize('directory_exists', [False, True])
def test_future_worker_path_or_directory_has_actionable_named_reference_hint(mounted, directory_exists):
    future = mounted / 'outputs' / 'steps'
    if directory_exists:
        future.mkdir(parents=True)
    with pytest.raises(ValueError, match='Input file does not exist before admission') as failed:
        study.file_reference(str(future), {'predict-a'})
    message = str(failed.value)
    assert '{"step":"predict-a","file":"result.json"}' in message
    assert 'one named input' in message and 'composer' in message and 'immutable admitted plans' in message
    assert 'never predict worker paths' in describe_workflow(['python-script'])['phases']['python-script'][
        'step_schema']['properties']['arguments']['properties']['inputs']['items']['properties']['file']['description']


@pytest.mark.parametrize('step', [{'kind': 'native'}, {'kind': 'batch'}, {'kind': 'clinical'},
    {'method': 'mindeval'}, {'method': 'report'}, {'method': 'clinical-study'}, {'method': 'aging'}])
def test_dynamic_output_contracts_remain_deferred_not_forbidden(step):
    assert known_output_files(step) is None
    study.known_output_reference({'step': 'dynamic', 'file': 'contract-dependent.ext'}, {'dynamic': step})
