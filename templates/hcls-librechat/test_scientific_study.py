import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import scientific_study as study
from scientific_receipts import load, save


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'private-test-key')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'first@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    return tmp_path


def plan():
    return {'schema': study.SCHEMA, 'title': 'An ordinary saved study', 'steps': [
        {'id': 'prepare', 'kind': 'preparation', 'method': 'write-json',
         'arguments': {'filename': 'input.json', 'value': {'sequence': 'ACD'}}},
        {'id': 'model', 'kind': 'native', 'model': 'example-model',
         'input': {'step': 'prepare', 'file': 'input.json'}, 'idempotency_key': 'unchanged-study-input'},
        {'id': 'report', 'kind': 'analysis', 'method': 'write-json',
         'arguments': {'filename': 'report.json', 'value': {'result': {'step': 'model', 'file': 'result.json'}}}},
    ], 'deliverables': [{'name': 'report', 'role': 'report', 'source': {'step': 'report', 'file': 'report.json'}}]}


def advance(identifier, **kwargs):
    return asyncio.run(study.advance(identifier, **kwargs))


def test_whole_study_reuses_plan_and_finishes_after_disconnect(mounted):
    started = study.submit(plan(), mounted / 'output')
    assert study.submit(plan(), mounted / 'output')['id'] == started['id']
    assert 'private-test-key' not in (study.directory(started['id']) / 'receipt.json').read_text()
    seen = []

    async def model(step, record):
        seen.append(step['idempotency_key'])
        source = mounted / 'result.json'
        source.write_text('{"value":42}')
        return {'state': 'completed', 'operation_id': 'operation-one',
                'files': {'result.json': study.measure(source)}}

    for _ in range(4):
        result = advance(started['id'], model_runner=model)
    assert result['state'] == 'completed'
    assert seen == ['unchanged-study-input']
    assert json.loads(Path(result['artifacts'][0]['path']).read_bytes())['result'] == str(mounted / 'result.json')
    assert json.loads(Path(result['manifest']['path']).read_bytes())['operations'] == ['operation-one']
    assert advance(started['id'], model_runner=model)['state'] == 'completed'
    assert len(seen) == 1


def test_process_death_after_admission_recovers_exact_receipt(mounted):
    started = study.submit(plan(), mounted / 'output')
    advance(started['id'])
    calls = []

    async def interrupted(step, record):
        target = Path(record['output_directory']) / 'steps' / step['id'] / 'operation' / 'receipt.json'
        saved = load(target)
        if not saved:
            calls.append('admit')
            save(target, {'state': 'running', 'operation_id': 'exact-operation'})
            raise SystemExit('simulate container death after accepted response')
        assert saved['operation_id'] == 'exact-operation'
        calls.append('observe')
        source = mounted / 'result.json'
        source.write_text('{}')
        return {'state': 'completed', 'operation_id': saved['operation_id'], 'files': {'result.json': study.measure(source)}}

    with pytest.raises(SystemExit):
        advance(started['id'], model_runner=interrupted)
    assert study.get(started['id'])['state'] == 'running'
    for _ in range(3):
        result = advance(started['id'], model_runner=interrupted)
    assert result['state'] == 'completed'
    assert calls == ['admit', 'observe']


def test_ambiguous_admission_is_preserved_and_blocks_next_study(mounted):
    first = study.submit(plan(), mounted / 'first')
    second = study.submit(plan(), mounted / 'second')
    advance(first['id'])

    async def unknown(step, record):
        save(Path(record['output_directory']) / 'steps' / step['id'] / 'operation' / 'receipt.json', {'state': 'submitting'})
        raise ConnectionError('connection lost without admission response')

    result = advance(first['id'], model_runner=unknown)
    assert result['state'] == 'needs_attention' and result['admission_unknown'] and result['queue_blocked']
    spec = importlib.util.spec_from_file_location('study_worker_test', Path(__file__).with_name('scientific-study-worker.py'))
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    assert worker.next_study(study.list_studies()) == (None, first['id'])
    assert study.get(second['id'])['completed_steps'] == []


def test_known_active_failure_can_cancel_without_admitting_next_phase(mounted):
    started = study.submit(plan(), mounted / 'output')
    advance(started['id'])

    async def broken(step, record):
        save(Path(record['output_directory']) / 'steps' / step['id'] / 'operation' / 'receipt.json', {'state': 'running', 'operation_id': 'known'})
        raise TimeoutError('bounded read budget exhausted')

    assert advance(started['id'], model_runner=broken)['queue_blocked']
    study.request_cancel(started['id'])

    async def cancelled(step, record):
        assert step['id'] == 'model'
        return {'state': 'cancelled', 'operation_id': 'known'}

    result = advance(started['id'], cancel_runner=cancelled)
    assert result['state'] == 'cancelled' and not result['queue_blocked']
    assert result['completed_steps'] == ['prepare']


@pytest.mark.parametrize('terminal', [False, True])
def test_lost_cancellation_response_resolves_terminal_or_holds_queue(mounted, monkeypatch, terminal):
    class Context:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    calls = []

    async def call(client, tool, arguments):
        calls.append((tool, arguments))
        if tool.startswith('cancel'):
            raise ConnectionError('cancel response was lost')
        return {'status': 'cancelled' if terminal else 'running'}

    monkeypatch.setattr(study, 'workflow_module', lambda: SimpleNamespace(batch=SimpleNamespace(
        httpx2=SimpleNamespace(AsyncClient=Context), Client=Context,
        streamable_http_client=lambda *args, **kwargs: None, call=call)))
    intent = mounted / 'cancel.json'
    with pytest.raises(ConnectionError):
        asyncio.run(study.cancel_known_operation('known-op', False, intent))
    assert load(intent)['state'] == 'sending'
    result = asyncio.run(study.cancel_known_operation('known-op', False, intent))
    assert [tool for tool, _ in calls] == ['cancel_operation', 'get_operation']
    assert all(args == {'operation_id': 'known-op'} for _, args in calls)
    if terminal:
        assert result['state'] == 'cancelled'
    else:
        assert result['state'] == 'needs_attention' and result['queue_blocked'] and result['cancellation_unknown']
        spec = importlib.util.spec_from_file_location('study_cancel_worker', Path(__file__).with_name('scientific-study-worker.py'))
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        result.update(id='6d9242ea-5538-40c0-97df-c7a093de8a47', created_at=1)
        save(study.directory(result['id']) / 'cancel-request.json', {'requested': True})
        assert worker.next_study([result]) == (None, result['id'])


def test_owner_namespace_shared_bucket_isolated_and_key_change_fails_closed(mounted, monkeypatch):
    first = study.submit(plan(), mounted / 'one')
    first_namespace = study.registry()
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'second@example.test')
    assert study.registry() != first_namespace and study.list_studies() == []
    with pytest.raises(ValueError, match='Unknown study'):
        study.get(first['id'])
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'first@example.test')
    monkeypatch.setenv('ENDPOINT_ID', 'a-new-image-deployment')
    assert study.get(first['id'])['id'] == first['id']
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'another-key')
    assert study.list_studies() == []
    with pytest.raises(ValueError, match='different configured'):
        study.get(first['id'])


def test_mutated_inputs_or_completed_files_do_not_admit(mounted):
    source = mounted / 'input.json'
    source.write_text('{}')
    value = plan()
    value['steps'][1]['input'] = str(source)
    started = study.submit(value, mounted / 'output')
    source.write_text('{"changed":true}')
    assert advance(started['id'])['state'] == 'failed'
    other = study.submit(plan(), mounted / 'other')
    result = advance(other['id'])
    Path(result['steps']['prepare']['files']['input.json']['path']).write_text('changed')
    assert advance(other['id'])['state'] == 'failed'


def test_output_binding_refuses_changed_plan_and_paths_cannot_escape(mounted):
    study.submit(plan(), mounted / 'output')
    value = plan()
    value['title'] = 'Different question'
    with pytest.raises(ValueError, match='belongs to another study'):
        study.submit(value, mounted / 'output')
    value['steps'][1]['input'] = '/etc/passwd'
    with pytest.raises(ValueError, match='inside the mounted'):
        study.submit(value, mounted / 'escape')


def test_invalid_later_json_fails_before_preparation_or_any_model_admission(mounted):
    source = mounted / 'invalid.json'
    source.write_text('[1, 2, 3]')
    value = plan()
    value['steps'][1]['input'] = str(source)
    with pytest.raises(ValueError, match='JSON object'):
        study.submit(value, mounted / 'invalid-output')
    assert not (mounted / 'invalid-output').exists()


def test_preparation_retry_after_partial_publication_uses_new_generation(mounted, monkeypatch):
    value = plan()
    value['steps'] = [value['steps'][0]]
    value['deliverables'][0]['source'] = {'step': 'prepare', 'file': 'input.json'}
    started = study.submit(value, mounted / 'output')
    original = study.persist_local_file

    def crash(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('partial')
        raise SystemExit('killed mid-copy')

    monkeypatch.setattr(study, 'persist_local_file', crash)
    with pytest.raises(SystemExit):
        advance(started['id'])
    monkeypatch.setattr(study, 'persist_local_file', original)
    advance(started['id'])
    result = advance(started['id'])
    assert result['state'] == 'completed'
    assert len(list((mounted / 'output/steps/prepare').glob('generation-*'))) == 2
    assert Path(result['artifacts'][0]['path']).read_text() != 'partial'


def test_final_manifest_copy_interruption_does_not_overwrite_or_block_recovery(mounted, monkeypatch):
    value = plan()
    value['steps'] = [value['steps'][0]]
    value['deliverables'][0]['source'] = {'step': 'prepare', 'file': 'input.json'}
    started = study.submit(value, mounted / 'output')
    advance(started['id'])
    original = study.persist_local_file

    def crash(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('partial publication')
        raise SystemExit('killed during final copy')

    monkeypatch.setattr(study, 'persist_local_file', crash)
    with pytest.raises(SystemExit):
        advance(started['id'])
    monkeypatch.setattr(study, 'persist_local_file', original)
    assert advance(started['id'])['state'] == 'completed'
    assert len(list((mounted / 'output').glob('publication-*'))) == 2


def test_real_worker_process_kill_and_restart_finishes_without_another_launch(mounted):
    value = plan()
    value['steps'] = [value['steps'][0], {'id': 'report', 'kind': 'analysis', 'method': 'write-json',
        'arguments': {'filename': 'report.json', 'value': {'input': {'step': 'prepare', 'file': 'input.json'}}}}]
    started = study.submit(value, mounted / 'output')
    environment = {**os.environ, 'SCIENTIFIC_EXECUTION_DIR': str(mounted / 'local-jobs')}
    command = [sys.executable, str(Path(__file__).with_name('scientific-study-worker.py')), '--worker']
    first = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not study.get(started['id'])['completed_steps']:
            time.sleep(0.05)
        assert study.get(started['id'])['completed_steps'] == ['prepare']
    finally:
        first.kill()
        first.wait(timeout=3)
    second = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and study.get(started['id'])['state'] != 'completed':
            time.sleep(0.05)
        assert study.get(started['id'])['state'] == 'completed'
        assert len(list((mounted / 'output/steps/prepare').glob('generation-*'))) == 1
    finally:
        second.terminate()
        second.wait(timeout=3)


def test_existing_stdio_tool_launch_and_reconnect_use_same_durable_identity(mounted):
    value = plan()
    value['steps'] = [value['steps'][0]]
    value['deliverables'][0]['source'] = {'step': 'prepare', 'file': 'input.json'}
    execution = Path(__file__).with_name('execution-mcp.py')

    def call(name, args):
        body = {'jsonrpc':'2.0', 'id':1, 'method':'tools/call', 'params':{'name':name, 'arguments':args}}
        result = subprocess.run([sys.executable, str(execution)], input=json.dumps(body)+'\n',
                                capture_output=True, text=True, check=True, env=os.environ)
        envelope = json.loads(result.stdout)['result']
        assert not envelope['isError']
        return json.loads(envelope['content'][0]['text'])

    args = {'study':value,'output_directory':str(mounted/'stdio')}
    first = call('run_scientific_workflow', args)
    assert call('run_scientific_workflow', args)['id'] == first['id']
    assert call('read_execution', {'job_id':first['id'], 'wait_seconds':0})['state'] == 'queued'
    advance(first['id'])
    advance(first['id'])
    done = call('read_execution', {'job_id':first['id'], 'wait_seconds':0})
    assert done['state'] == 'completed' and done['artifacts'][0]['download_url'].startswith('/demos?')


def test_regular_deployment_fails_before_cloud_call_without_single_owner_preflight(mounted):
    environment = {**os.environ, **{name:'fixture-only' for name in ('NEBIUS_PROJECT_ID','NEBIUS_SUBNET_ID',
        'SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR','TOKEN_FACTORY_SECRET_SELECTOR','TAVILY_SECRET_SELECTOR','IMAGE')}}
    environment.pop('SCIENTIFIC_STUDY_OWNER_MODE', None)
    result = subprocess.run(['bash', str(Path(__file__).parent/'scripts/deploy.sh')],
                            capture_output=True, text=True, env=environment)
    assert result.returncode == 2
    assert 'Overlapping same-user supervisors are unsupported' in result.stderr
    assert not result.stdout
