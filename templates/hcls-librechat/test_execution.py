"""Exercise actual shell jobs and reconnects over the stdio protocol."""
import json
import os
from pathlib import Path
import subprocess
import sys
import importlib.util
import pytest

SCRIPT = Path(__file__).with_name('execution-mcp.py')


def call(tmp_path, name, args):
    env = dict(os.environ, SCIENTIFIC_EXECUTION_DIR=str(tmp_path / 'jobs'),
               SCIENTIFIC_WORKSPACE=str(tmp_path))
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': name, 'arguments': args}}
    proc = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(request) + '\n',
                          env=env, text=True, capture_output=True, check=True)
    result = json.loads(proc.stdout)['result']
    return result, json.loads(result['content'][0]['text'])


def test_actual_python_file_and_failed_exit(tmp_path):
    _, result = call(tmp_path, 'execute_command', {
        'command': "python3 -c \"from pathlib import Path; Path('result.txt').write_text(str(6 * 7))\""})
    assert result['status'] == 'completed'
    assert (tmp_path / 'result.txt').read_text() == '42'
    envelope, result = call(tmp_path, 'execute_command', {'command': 'echo failure; exit 7'})
    assert envelope['isError'] is True
    assert result['exit_code'] == 7
    assert result['output'] == 'failure\n'


def test_job_continues_after_mcp_disconnect_and_output_is_paged(tmp_path):
    _, started = call(tmp_path, 'execute_command', {
        'command': "sleep 0.3; python3 -c \"print('x' * 40000, end='')\"", 'wait_seconds': 0})
    _, result = call(tmp_path, 'read_execution', {'job_id': started['job_id'], 'wait_seconds': 3})
    assert result['status'] == 'completed'
    assert len(result['output']) == 4000
    assert result['output_size_bytes'] == 40000
    assert result['returned_bytes'] == 4000
    assert 'retained at output_path' in result['output_guidance']
    assert result['more_output'] is True
    _, rest = call(tmp_path, 'read_execution', {'job_id': started['job_id'],
        'offset': result['next_offset'], 'max_bytes': 32000})
    assert len(rest['output']) == 32000
    assert rest['more_output'] is True
    _, final = call(tmp_path, 'read_execution', {'job_id': started['job_id'],
        'offset': rest['next_offset']})
    assert len(final['output']) == 4000
    assert final['more_output'] is False


def test_command_deadline(tmp_path):
    envelope, result = call(tmp_path, 'execute_command', {
        'command': 'sleep 30', 'timeout_seconds': 1, 'wait_seconds': 3})
    assert envelope['isError'] is True
    assert result['status'] == 'timed_out'


def test_typed_workflow_reuses_execution_job_across_connections(tmp_path, monkeypatch):
    runner = tmp_path / 'fixture-runner.py'
    runner.write_text('import sys,json\nprint(json.dumps({"steps":1,"files":[{}]}) if "--validate-only" in sys.argv else "fixture complete")\n')
    (tmp_path / 'a plan.json').write_text('{"schema":"scientific-workflow/v1","steps":[]}')
    monkeypatch.setenv('SCIENTIFIC_CLIENT_PYTHON', sys.executable)
    monkeypatch.setenv('SCIENTIFIC_WORKFLOW_RUNNER', str(runner))
    args = {'plan_file': 'a plan.json', 'output_directory': 'study results'}
    _, first = call(tmp_path, 'run_scientific_workflow', args)
    assert first['preflight_steps'] == 1 and first['status'] == 'completed'
    _, second = call(tmp_path, 'run_scientific_workflow', args)
    assert first['job_id'] == second['job_id']
    assert second['reused_existing_job'] is True
    assert len(list((tmp_path / 'jobs').glob('*/request.json'))) == 1


def test_typed_workflow_missing_source_rejected_before_job(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    monkeypatch.setenv('SCIENTIFIC_CLIENT_PYTHON', sys.executable)
    monkeypatch.setenv('SCIENTIFIC_WORKFLOW_RUNNER', str(SCRIPT.with_name('scientific-workflow.py')))
    (tmp_path / 'plan.json').write_text(json.dumps({'schema':'scientific-workflow/v1','steps':[
        {'id':'one','kind':'native','model':'phenoage','input':str(tmp_path/'missing.json'),
         'output':str(tmp_path/'run'),'idempotency_key':'original-key'}]}))
    with pytest.raises(ValueError, match='not an existing file'):
        execution.run_scientific_workflow({'plan_file':'plan.json','output_directory':'flow'})
    assert not list((tmp_path / 'jobs').glob('*/request.json'))


def test_typed_workflow_interruption_requires_explicit_resume(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('execution_test', SCRIPT)
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    plan = tmp_path / 'plan.json'
    plan.write_text('{}')
    identity = execution.hashlib.sha256(plan.read_bytes()+b'\0'+str(tmp_path/'flow').encode()).hexdigest()
    index = tmp_path / 'jobs/workflow-index'
    index.mkdir(parents=True)
    (index / (identity+'.json')).write_text(json.dumps({'job_id':'original'}))
    monkeypatch.setattr(execution,'read_job',lambda args:{'job_id':'original','status':'interrupted'})
    monkeypatch.setattr(execution.subprocess,'run',lambda *a,**k:pytest.fail('No implicit retry/preflight'))
    result=execution.run_scientific_workflow({'plan_file':'plan.json','output_directory':'flow'})
    assert result['job_id']=='original' and result['resume_required'] is True
