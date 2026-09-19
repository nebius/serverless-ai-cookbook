"""The typed GenMol phase reuses the deterministic saved-result helper."""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow, known_output_files


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'genmol-test-only')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'genmol-analysis@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('Saved-result analysis submits no inference'))
    return tmp_path


def test_genmol_dependent_files_complete_without_custom_analysis_program(mounted):
    request = {'smiles': 'C[MASK]', 'num_molecules': 4, 'scoring': 'QED', 'unique': True}
    result = {'molecules': [{'smiles': 'CCO'}, {'smiles': 'OCC'}, {'smiles': 'not-a-molecule'}]}
    value = {'schema': study.SCHEMA, 'title': 'Recorded GenMol outcomes', 'steps': [
        {'id': 'request', 'kind': 'preparation', 'method': 'write-json',
         'arguments': {'filename': 'request.json', 'value': request}},
        {'id': 'result', 'kind': 'preparation', 'method': 'write-json',
         'arguments': {'filename': 'result.json', 'value': result}},
        {'id': 'measure', 'kind': 'analysis', 'method': 'genmol', 'arguments': {
            'input_file': {'step': 'request', 'file': 'request.json'},
            'result_file': {'step': 'result', 'file': 'result.json'}}}],
        'deliverables': [{'name': name, 'role': role, 'source': {'step': 'measure', 'file': name}}
            for name, role in [('report.md', 'report'), ('metrics.json', 'metrics'),
                               ('rows.csv', 'data'), ('completion-manifest.json', 'provenance')]]}
    accepted = study.submit(value, mounted / 'complete')
    assert study.submit(value, mounted / 'complete')['id'] == accepted['id']
    for _ in range(4):
        completed = asyncio.run(study.advance(accepted['id']))
    assert completed['state'] == 'completed', completed
    outputs = completed['steps']['measure']['files']
    phase = describe_workflow(['genmol'])['phases']['genmol']
    assert set(outputs) == set(phase['always_on_success']) == known_output_files(value['steps'][-1])
    measured = json.loads(Path(outputs['metrics.json']['path']).read_bytes())
    assert measured['requested_count'] == 4 and measured['returned_count'] == 3
    assert measured['valid_count'] == 2 and measured['invalid_count'] == 1
    assert measured['underfilled'] and measured['canonical_duplicate_valid_count'] == 1
    assert measured['score_compared_count'] == 0 and measured['inference_submitted'] is False
    assert [row['raw_smiles'] for row in measured['rows']] == [row['smiles'] for row in result['molecules']]
    for name, source_step, source_file in [('request', 'request', 'request.json'), ('result', 'result', 'result.json')]:
        source = Path(completed['steps'][source_step]['files'][source_file]['path']).read_bytes()
        assert measured['provenance'][name + '_sha256'] == hashlib.sha256(source).hexdigest()
    assert json.loads(Path(completed['manifest']['path']).read_bytes())['operations'] == []


def test_genmol_cli_binding_preserves_literal_request_and_result_paths(tmp_path):
    args = {'input_file': '/workspace/request.json', 'result_file': '/workspace/result.json'}
    command = study.local_command('genmol', args, tmp_path)
    assert command[2:] == ['--request', args['input_file'], '--genmol-result', args['result_file'],
                           '--output', str(tmp_path / 'metrics.json')]
    assert study.input_references({'kind': 'analysis', 'method': 'genmol', 'arguments': args}) == list(args.values())
