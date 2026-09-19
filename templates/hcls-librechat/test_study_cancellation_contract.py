"""Retained v54 native-status shape and cancellation-only successor behavior."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scientific_study as study
from scientific_receipts import load, save


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_EXECUTION_DIR', str(tmp_path / 'local-executions'))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'private-test-key')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'first@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'stopped-predecessor')
    return tmp_path


def transport(monkeypatch, result):
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
        return result

    monkeypatch.setattr(study, 'workflow_module', lambda: SimpleNamespace(batch=SimpleNamespace(
        httpx2=SimpleNamespace(AsyncClient=Context), Client=Context,
        streamable_http_client=lambda *args, **kwargs: None, call=call)))
    return calls


@pytest.mark.parametrize('scientific,result', [
    (False, {'id': 'known-op', 'operation': 'generate-media', 'status': 'succeeded'}),
    (True, {'operation': {'id': 'known-op', 'status': 'failed'}}),
    (False, {'id': 'known-op', 'operation': 'generate-media', 'status': 'running'}),
])
def test_exact_native_flat_and_scientific_wrapped_status(mounted, monkeypatch, scientific, result):
    calls = transport(monkeypatch, result)
    intent = mounted / 'cancel.json'
    saved_result = json.dumps(result, sort_keys=True)
    first = asyncio.run(study.cancel_known_operation('known-op', scientific, intent))
    second = asyncio.run(study.cancel_known_operation('known-op', scientific, intent))
    status = result['operation']['status'] if scientific else result['status']
    assert first == second == {'state': 'cancelling' if status == 'running' else 'cancelled', 'operation_id': 'known-op'}
    assert [tool for tool, _ in calls] == ([
        'cancel_scientific_run', 'get_scientific_status', 'get_scientific_status'] if scientific else [
        'cancel_operation', 'get_operation', 'get_operation'])
    assert all(arguments == {'operation_id': 'known-op'} for _, arguments in calls)
    assert json.dumps(result, sort_keys=True) == saved_result  # terminal backend result is untouched


def blocked_study(mounted):
    source = mounted / 'input.json'
    source.write_text('{}')
    helper = mounted / 'old-analysis.py'
    helper.write_text('old implementation')
    plan = {'schema': study.SCHEMA, 'title': 'Recorded media study', 'steps': [
        {'id': 'native-transfer', 'kind': 'native', 'model': 'example-model',
         'input': str(source), 'idempotency_key': 'fixed-original-identity'},
        {'id': 'report', 'kind': 'analysis', 'method': 'write-json',
         'arguments': {'filename': 'report.json', 'value': {'done': True}}},
    ], 'deliverables': [{'name': 'report', 'role': 'report', 'source': {'step': 'report', 'file': 'report.json'}}]}
    accepted = study.submit(plan, mounted / 'output')
    root = study.directory(accepted['id'])
    original_failure = {'type': 'ExceptionGroup', 'message': 'unhandled errors in a TaskGroup (1 sub-exception)'}
    record = load(root / 'receipt.json')
    record.update(state='needs_attention', phase='failure', current_step='native-transfer',
                  queue_blocked=True, admission_unknown=False, failure=original_failure,
                  steps={'native-transfer': {'state': 'running', 'operation_id': 'known-op'}})
    record['implementations']['retained-test-helper'] = study.measure(helper)
    save(root / 'receipt.json', record)
    operation_path = Path(record['output_directory']) / 'steps/native-transfer/operation/receipt.json'
    save(operation_path, {'state': 'running', 'operation_id': 'known-op'})
    study.request_cancel(accepted['id'])
    return accepted['id'], root, source, helper, operation_path, original_failure


def test_successor_worker_processes_saved_cancel_after_inputs_and_helpers_change(mounted, monkeypatch):
    identifier, root, source, helper, operation_path, original_failure = blocked_study(mounted)
    source.write_text('{"changed after failure":true}')
    helper.write_text('new implementation')
    record = load(root / 'receipt.json')
    with pytest.raises(RuntimeError):
        study.verify_inputs(record)  # ordinary scientific resume remains strict
    save(root / 'cancel-sent.json', {'operation_id': 'known-op', 'state': 'sent'})
    calls = transport(monkeypatch, {'operation': 'generate-media', 'status': 'succeeded'})
    spec = importlib.util.spec_from_file_location('cancellation_worker', Path(study.__file__).with_name('scientific-study-worker.py'))
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    final = asyncio.run(worker.cycle())
    assert final['id'] == identifier and final['state'] == 'cancelled' and not final['queue_blocked']
    assert final['failure'] == original_failure and final['completed_steps'] == []
    assert calls == [('get_operation', {'operation_id': 'known-op'})]
    assert load(operation_path) == {'state': 'running', 'operation_id': 'known-op'}
    assert worker.next_study(study.list_studies()) == (None, None)
    assert len(list((root / '.receipt-history/receipt.json').glob('*.json'))) >= 3


@pytest.mark.parametrize('mutation', ['owner', 'caller', 'plan', 'operation', 'missing-operation', 'unknown'])
def test_cancellation_never_rebinds_or_invents_admission(mounted, monkeypatch, mutation):
    identifier, root, _, _, operation_path, original_failure = blocked_study(mounted)
    record = load(root / 'receipt.json')
    if mutation == 'owner':
        record['owner'] = 'different-owner'
    elif mutation == 'caller':
        record['caller_fingerprint'] = 'different-key'
    elif mutation == 'plan':
        plan = json.loads((root / 'plan.json').read_text())
        plan['steps'][0]['model'] = 'different-model'
        (root / 'plan.json').write_text(json.dumps(plan))
    elif mutation in {'operation', 'missing-operation'}:
        save(operation_path, {'state': 'running', **({'operation_id': 'different-op'} if mutation == 'operation' else {})})
    else:
        record['admission_unknown'] = True
        save(operation_path, {'state': 'submitting'})
    save(root / 'receipt.json', record)
    calls = transport(monkeypatch, {'operation': 'generate-media', 'status': 'succeeded'})
    result = asyncio.run(study.advance(identifier))
    assert result['state'] == 'needs_attention' and result['queue_blocked']
    assert result['failure'] == original_failure and result['cancellation_failure']
    assert calls == [] and result['completed_steps'] == []


@pytest.mark.parametrize('result', [{'operation': 'generate-media'}, {'operation': {'status': None}}])
def test_cancellation_observation_failure_preserves_original_failure(mounted, monkeypatch, result):
    identifier, root, _, _, _, original_failure = blocked_study(mounted)
    calls = transport(monkeypatch, result)
    final = asyncio.run(study.advance(identifier))
    assert final['state'] == 'needs_attention' and final['queue_blocked']
    assert final['failure'] == original_failure
    assert final['cancellation_failure']['type'] == 'ValueError'
    assert 'not confirmed' in final['cancellation_failure']['message']
    assert len(calls) == 2
    assert load(root / 'cancel-sent.json')['state'] == 'sent'
    asyncio.run(study.advance(identifier))
    assert [tool for tool, _ in calls] == ['cancel_operation', 'get_operation', 'get_operation']
