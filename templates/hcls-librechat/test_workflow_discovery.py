"""Compact discovery is the real launcher contract, not another plan dialect."""
import asyncio
import importlib.util
import json
from pathlib import Path
import re
import sys
import subprocess

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent))
import scientific_study as study
from scientific_study_schema import PHASE_OUTPUTS, STEPS, STUDY_SCHEMA, describe_workflow

SPEC = importlib.util.spec_from_file_location('workflow_discovery_execution', Path(__file__).with_name('execution-mcp.py'))
execution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution)


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-private')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'discovery@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('CPU study must not load model transport'))
    return tmp_path


def test_selected_contracts_are_exact_validation_schemas_not_expanded_catalog():
    summary = describe_workflow()
    assert set(summary['methods']) == set(PHASE_OUTPUTS)
    selected = describe_workflow(['mindeval', 'report'])
    assert list(selected['phases']) == ['mindeval', 'report']
    for value in selected['phases'].values():
        assert value['step_schema'] in STEPS
    Draft202012Validator(STUDY_SCHEMA).validate(selected['plan_file_example'])
    assert len(json.dumps(selected)) < len(json.dumps(describe_workflow(list(PHASE_OUTPUTS))))
    for names in ([], ['not-a-method'], ['report', 'report']):
        with pytest.raises(ValueError):
            describe_workflow(names)


def test_discovery_works_over_actual_stdio_without_execution(tmp_path):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
        'name': 'describe_scientific_workflow', 'arguments': {'methods': ['native', 'batch', 'report']}}}
    completed = subprocess.run([sys.executable, SPEC.origin], input=json.dumps(request) + '\n',
                               text=True, capture_output=True, check=True, cwd=tmp_path)
    response = json.loads(completed.stdout)['result']
    assert response['isError'] is False
    result = json.loads(response['content'][0]['text'])
    assert result['phases']['native']['always_on_success'] == ['result.json']
    assert 'output-manifest.json' in result['phases']['batch']['always_on_success']
    assert list(tmp_path.iterdir()) == []


def test_file_backed_v2_uses_same_frozen_receipt_and_guaranteed_outputs(mounted):
    rows = mounted / 'rows.csv'
    rows.write_text('measurement,value\nexact,7\n')
    plan = describe_workflow(['report'])['plan_file_example']
    plan['steps'][0]['arguments']['sections'][0]['file'] = str(rows)
    plan_file = mounted / 'study.json'
    plan_file.write_text(json.dumps(plan))
    args = {'plan_file': str(plan_file), 'output_directory': str(mounted / 'final')}
    schema = next(item['inputSchema'] for item in execution.TOOLS if item['name'] == 'run_scientific_workflow')
    Draft202012Validator(schema).validate(args)
    first = execution.run_scientific_workflow(args)
    assert execution.run_scientific_workflow(args)['id'] == first['id']
    assert execution.run_scientific_workflow({'study': plan, 'output_directory': args['output_directory']})['id'] == first['id']
    # The source plan is copied, not executed as a mutable plan-file pointer.
    plan_file.write_text('broken later edit')
    assert json.loads((study.directory(first['id']) / 'plan.json').read_bytes()) == plan
    result = asyncio.run(study.advance(first['id']))
    result = asyncio.run(study.advance(first['id']))
    assert result['state'] == 'completed'
    record = json.loads((study.directory(first['id']) / 'receipt.json').read_bytes())
    assert set(PHASE_OUTPUTS['report'][0]) <= record['steps']['report']['files'].keys()
    assert len(study.list_studies()) == 1
    assert 'test-private' not in (study.directory(first['id']) / 'receipt.json').read_text()


def test_file_backed_v2_freezes_input_and_rejects_manual_resume(mounted):
    rows = mounted / 'rows.csv'
    rows.write_text('measurement,value\na,1\n')
    plan = describe_workflow(['report'])['plan_file_example']
    plan['steps'][0]['arguments']['sections'][0]['file'] = str(rows)
    path = mounted / 'plan.json'
    path.write_text(json.dumps(plan))
    args = {'plan_file': str(path), 'output_directory': str(mounted / 'final')}
    with pytest.raises(ValueError, match='resume automatically'):
        execution.run_scientific_workflow({**args, 'resume': True})
    assert study.list_studies() == []
    saved = execution.run_scientific_workflow(args)
    rows.write_text('measurement,value\na,2\n')
    assert asyncio.run(study.advance(saved['id']))['state'] == 'failed'
    assert not (mounted / 'final' / 'completion-manifest.json').exists()


def test_mindeval_phase_freezes_all_separate_record_files(mounted):
    source = mounted / 'full.json'
    source.write_text(json.dumps({'id': 'one', 'status': 'completed', 'state': {
        'config': {'profile_id': 'profile-a', 'clinician_model': 'clinician'},
        'transcript': [{'role': 'patient', 'content': 'Untruncated source.'}],
        'judgment': {'judgment': {'observed criterion': 4}}}}))
    plan = {'schema': study.SCHEMA, 'title': 'Reused records', 'steps': [
        {'id': 'analysis', 'kind': 'analysis', 'method': 'mindeval', 'arguments': {'title': 'Reused records', 'records': [str(source)]}}],
        'deliverables': [{'name': 'report', 'role': 'report', 'source': {'step': 'analysis', 'file': 'report.md'}}]}
    saved = study.submit(plan, mounted / 'final')
    record = json.loads((study.directory(saved['id']) / 'receipt.json').read_bytes())
    assert str(source) in record['inputs']
    asyncio.run(study.advance(saved['id']))
    assert asyncio.run(study.advance(saved['id']))['state'] == 'completed'


def test_seed_and_general_guidance_use_exact_registered_execution_names():
    root = Path(__file__).parent
    instructions = (root.parents[1] / 'life-science/bionemo-librechat/scientific-agent-instructions.md').read_text()
    seed = (root / 'seed-workbench.js').read_text()
    for text in (instructions, seed):
        for name in ('execute_command', 'read_execution', 'run_scientific_workflow', 'upload_workspace_files', 'recover_scientific_results'):
            assert not re.search(r'\b' + name + r'\b', text)
        assert 'describe_scientific_workflow_mcp_environment-execution' in text
        assert 'bounded logical' in text and 'plan_file' in text
    assert 'For reuse-only analysis, do not query that catalog' in instructions
    assert 'Begin with `workshop_catalog' not in instructions
