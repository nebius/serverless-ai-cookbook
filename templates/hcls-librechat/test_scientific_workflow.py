import asyncio
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('workflow', ROOT / 'scientific-workflow.py')
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


def plan(tmp_path):
    return {'schema': 'scientific-workflow/v1', 'steps': [
        {'id': name, 'model': name, 'tool': 'submit_' + name, 'operation': 'design',
         'source': str(tmp_path / 'input'), 'parameters': str(tmp_path / 'parameters'),
         'output': str(tmp_path / name), 'media_type': 'text/plain', 'entry_name': 'input',
         'semantic_type': 'fixture/v1', 'idempotency_key': name, 'display_name': name}
        for name in ('a', 'b')]}


def test_observation_is_not_completion_and_resume_does_not_advance(tmp_path):
    calls = []
    async def step(args):
        calls.append(args.model)
        return {'state': 'running', 'operation_id': 'original-a'}
    args = plan(tmp_path)
    result = asyncio.run(workflow.run(args, tmp_path / 'flow', 1, run_step=step,
                                     clock=iter((0, 0, 2)).__next__))
    assert calls == ['a']
    assert result['completed_steps'] == []
    async def finish(args):
        calls.append(args.model)
        return {'state': 'verified', 'operation_id': 'original-' + args.model}
    result = asyncio.run(workflow.run(args, tmp_path / 'flow', run_step=finish))
    assert calls == ['a', 'a', 'b']
    assert result['state'] == 'completed'
    asyncio.run(workflow.run(args, tmp_path / 'flow', run_step=finish))
    assert calls == ['a', 'a', 'b']


def test_preflight_reports_all_missing_and_invalid_files_before_admission(tmp_path):
    (tmp_path / 'bad.json').write_text('not JSON')
    prepared = {'schema': 'scientific-workflow/v1', 'steps': [
        {'id': name, 'kind': 'native', 'model': 'fixture', 'input': str(tmp_path / filename),
         'output': str(tmp_path / name), 'idempotency_key': 'original-' + name}
        for name, filename in [('first', 'missing.json'), ('second', 'bad.json'), ('third', 'also-missing.json')]]}
    with pytest.raises(ValueError) as error:
        workflow.validate_files(prepared)
    message = str(error.value)
    assert 'first input is not an existing file' in message
    assert 'second input is not valid JSON' in message
    assert 'third input is not an existing file' in message
    assert 'before any admission' in message


def test_explicit_concurrency_rejection_waits_but_does_not_admit_next_step(tmp_path):
    calls = []
    async def step(args):
        calls.append(args.model)
        if len(calls) == 1:
            raise workflow.batch.ExplicitRejection({'code': 'concurrency_exceeded',
                'durable_admission': False, 'retry_after_seconds': 15})
        return {'state': 'verified', 'operation_id': 'same-' + args.model}
    delays = []
    async def sleep(delay):
        delays.append(delay)
    result = asyncio.run(workflow.run(plan(tmp_path), tmp_path / 'flow', run_step=step, sleep=sleep))
    assert calls == ['a', 'a', 'b'] and delays == [15]
    assert result['state'] == 'completed'


def test_ambiguous_admission_and_application_errors_are_preserved(tmp_path):
    async def step(args):
        workflow.save(args.output / 'receipt.json', {'state': 'admission_unknown'})
        raise ConnectionError('lost response')
    args = plan(tmp_path)
    with pytest.raises(ConnectionError):
        asyncio.run(workflow.run(args, tmp_path / 'flow', run_step=step))
    assert workflow.load(tmp_path / 'flow/receipt.json')['state'] == 'admission_unknown'
    with pytest.raises(RuntimeError, match='inspection'):
        asyncio.run(workflow.run(args, tmp_path / 'flow', run_step=step))


def test_changed_plan_refuses_resume(tmp_path):
    async def step(args):
        return {'state': 'verified'}
    args = plan(tmp_path)
    asyncio.run(workflow.run(args, tmp_path / 'flow', run_step=step))
    args['steps'][0]['idempotency_key'] = 'different'
    with pytest.raises(ValueError, match='changed'):
        asyncio.run(workflow.run(args, tmp_path / 'flow', run_step=step))


def test_optional_self_route_has_older_server_fallback(monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-only')
    class HTTP:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args, **kwargs):
            return type('Response', (), {'status_code': 404})()
    monkeypatch.setattr(workflow.httpx2, 'AsyncClient', lambda **kwargs: HTTP())
    assert asyncio.run(workflow.caller_policy())['available'] is False


def test_single_wrapped_explicit_rejection_is_waiting_not_unknown(tmp_path):
    async def step(args):
        raise ExceptionGroup('transport cleanup', [workflow.batch.ExplicitRejection({
            'code': 'concurrency_exceeded', 'durable_admission': False})])
    result = asyncio.run(workflow.run(plan(tmp_path), tmp_path / 'flow', 1, run_step=step,
                                     clock=iter((0, 0, 2)).__next__))
    assert result['state'] == 'waiting_admission'
    assert result['completed_steps'] == []


def native_plan(tmp_path):
    return {'schema': 'scientific-workflow/v1', 'steps': [
        {'id': name, 'kind': 'native', 'model': name,
         'input': str(tmp_path / (name + '.json')), 'output': str(tmp_path / name),
         'idempotency_key': 'original-key-' + name} for name in ('speech-a', 'speech-b')]}


def test_native_observation_resumes_original_before_next_native(tmp_path):
    calls = []
    async def pending(args):
        calls.append((args.model, args.idempotency_key, args.output_dir))
        assert args.wait_seconds == 1
        return {'state': 'running', 'operation_id': 'original-speech-a'}
    prepared = native_plan(tmp_path)
    result = asyncio.run(workflow.run(prepared, tmp_path / 'flow', 1,
        native_run_step=pending, clock=iter((0, 0, 2)).__next__))
    assert result['state'] == 'running' and result['completed_steps'] == []
    assert [call[0] for call in calls] == ['speech-a']
    async def complete(args):
        calls.append((args.model, args.idempotency_key, args.output_dir))
        return {'state': 'succeeded', 'operation_id': 'original-' + args.model,
                'result_path': str(args.output_dir / 'result.json')}
    result = asyncio.run(workflow.run(prepared, tmp_path / 'flow', native_run_step=complete))
    assert [call[0] for call in calls] == ['speech-a', 'speech-a', 'speech-b']
    assert calls[0] == calls[1]
    assert result['state'] == 'completed'
    assert result['step_states']['speech-a']['native_state'] == 'succeeded'
    asyncio.run(workflow.run(prepared, tmp_path / 'flow', native_run_step=complete))
    assert len(calls) == 3


def test_mixed_batch_native_plan_uses_existing_clients_in_order(tmp_path):
    prepared = plan(tmp_path)
    prepared['steps'].insert(1, native_plan(tmp_path)['steps'][0])
    calls = []
    async def batch(args):
        calls.append(('batch', args.model))
        return {'state': 'verified'}
    async def native(args):
        calls.append(('native', args.model))
        return {'state': 'succeeded'}
    result = asyncio.run(workflow.run(prepared, tmp_path / 'flow',
        run_step=batch, native_run_step=native))
    assert result['state'] == 'completed'
    assert calls == [('batch', 'a'), ('native', 'speech-a'), ('batch', 'b')]


@pytest.mark.parametrize('code', ['concurrency_exceeded', 'admission_limit_reached'])
def test_native_explicit_nonadmission_waits_with_exact_key(tmp_path, code):
    calls, delays = [], []
    async def native(args):
        calls.append((args.model, args.idempotency_key))
        if len(calls) == 1:
            workflow.save(args.output_dir / 'receipt.json', {'state': 'rejected',
                'last_rejection': {'code': code,
                    'durable_admission': False, 'retry_after_seconds': 17}})
            raise RuntimeError('MCP isError')
        return {'state': 'succeeded'}
    async def sleep(delay):
        delays.append(delay)
    result = asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow',
        native_run_step=native, sleep=sleep))
    assert calls[0] == calls[1]
    assert calls[2][0] == 'speech-b' and delays == [17]
    assert result['state'] == 'completed'


@pytest.mark.parametrize('state', ['failed', 'cancelled', 'expired', 'preempted'])
def test_native_terminal_failure_stops_workflow(tmp_path, state):
    calls = []
    async def native(args):
        calls.append(args.model)
        receipt = {'state': state, 'operation_id': 'original-failed'}
        workflow.save(args.output_dir / 'receipt.json', receipt)
        return receipt
    with pytest.raises(RuntimeError, match='Native operation ended'):
        asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow', native_run_step=native))
    assert calls == ['speech-a']
    saved = workflow.load(tmp_path / 'flow/receipt.json')
    assert saved['state'] == 'failed' and saved['step_states']['speech-a']['operation_id'] == 'original-failed'


def test_stale_concurrency_error_cannot_retry_unknown_native_admission(tmp_path):
    calls = []
    async def native(args):
        calls.append(args.model)
        workflow.save(args.output_dir / 'receipt.json', {'state': 'admission_unknown',
            'last_rejection': {'code': 'concurrency_exceeded', 'durable_admission': False}})
        raise ConnectionError('current response lost')
    with pytest.raises(ConnectionError):
        asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow', native_run_step=native))
    assert calls == ['speech-a']
    assert workflow.load(tmp_path / 'flow/receipt.json')['state'] == 'admission_unknown'


def test_native_application_rejection_does_not_wait_or_retry(tmp_path):
    async def native(args):
        workflow.save(args.output_dir / 'receipt.json', {'state': 'rejected',
            'last_rejection': {'code': 'invalid_input', 'durable_admission': False}})
        raise RuntimeError('invalid input')
    with pytest.raises(RuntimeError, match='invalid input'):
        asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow', native_run_step=native))
    assert workflow.load(tmp_path / 'flow/receipt.json')['state'] == 'failed'


def test_native_schema_rejects_mixed_transport_arguments(tmp_path):
    prepared = native_plan(tmp_path)
    prepared['steps'][0]['source'] = str(tmp_path / 'extra')
    with pytest.raises(ValueError, match='documented client'):
        workflow.prepare(prepared)


def test_no_next_admission_after_completed_step_exhausts_deadline(tmp_path):
    calls = []
    async def complete(args):
        calls.append(args.model)
        return {'state': 'succeeded', 'operation_id': 'original-a'}
    result = asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow', 1,
        native_run_step=complete, clock=iter((0, 0, 2)).__next__))
    assert calls == ['speech-a']
    assert result['state'] == 'observation_expired'
    assert result['completed_steps'] == ['speech-a']


def test_native_wait_is_bounded_and_not_followed_by_duplicate_sleep(tmp_path):
    calls, delays = [], []
    async def step(args):
        calls.append(args.wait_seconds)
        return {'state': 'running' if len(calls) == 1 else 'succeeded', 'operation_id': 'original-a'}
    async def sleep(delay): delays.append(delay)
    prepared = native_plan(tmp_path)
    prepared['steps'] = prepared['steps'][:1]
    result = asyncio.run(workflow.run(prepared, tmp_path / 'flow', 40, poll_seconds=10,
        native_run_step=step, sleep=sleep, clock=iter((0, 0, 10, 10)).__next__))
    assert calls == [10, 10] and delays == []
    assert result['state'] == 'completed'


def test_native_wait_does_not_hold_session_for_long_batch_interval(tmp_path):
    async def step(args):
        assert args.wait_seconds == 30
        return {'state': 'succeeded'}
    result = asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow',
        poll_seconds=300, native_run_step=step))
    assert result['state'] == 'completed'


def test_known_native_disconnect_recovers_only_original_operation(tmp_path):
    calls = []
    async def step(args):
        calls.append((args.model, args.idempotency_key, args.output_dir, args.recover_only))
        if len(calls) == 1:
            workflow.save(args.output_dir / 'receipt.json', {
                'state': 'running', 'operation_id': 'original-operation'})
            raise ExceptionGroup('stream closed', [ConnectionError('disconnected')])
        return {'state': 'succeeded', 'operation_id': 'original-operation'}
    async def sleep(delay): pass
    result = asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow',
        native_run_step=step, sleep=sleep))
    assert calls[0][:3] == calls[1][:3]
    assert calls[0][3] is False and calls[1][3] is True
    assert calls[2][0] == 'speech-b' and calls[2][3] is False
    assert result['observation_errors'][0]['operation_id'] == 'original-operation'
    assert result['observation_errors'][0]['recovery'] == 'read_only'


def test_known_native_disconnect_recovery_is_bounded(tmp_path):
    calls = []
    async def step(args):
        calls.append(args.model)
        workflow.save(args.output_dir / 'receipt.json', {'state': 'running', 'operation_id': 'original'})
        raise ConnectionError('still disconnected')
    async def sleep(delay): pass
    with pytest.raises(ConnectionError):
        asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow',
            native_run_step=step, sleep=sleep))
    assert calls == ['speech-a'] * 4
    saved = workflow.load(tmp_path / 'flow/receipt.json')
    assert saved['state'] == 'failed' and len(saved['observation_errors']) == 3


def test_known_operation_does_not_retry_integrity_or_application_failure(tmp_path):
    async def step(args):
        workflow.save(args.output_dir / 'receipt.json', {'state': 'result_pending', 'operation_id': 'original'})
        raise ValueError('artifact hash mismatch')
    with pytest.raises(ValueError, match='hash mismatch'):
        asyncio.run(workflow.run(native_plan(tmp_path), tmp_path / 'flow', native_run_step=step))
    assert 'observation_errors' not in workflow.load(tmp_path / 'flow/receipt.json')


def test_file_preflight_checks_later_step_before_first_admission(tmp_path):
    prepared = native_plan(tmp_path)
    (tmp_path / 'speech-a.json').write_text('{"input":"first"}')
    with pytest.raises(ValueError, match='speech-b input is not an existing file'):
        workflow.validate_files(prepared)
    assert not (tmp_path / 'speech-a/receipt.json').exists()
    (tmp_path / 'speech-b.json').write_text('{"input":"second"}')
    result = workflow.validate_files(prepared)
    assert result['steps'] == 2 and len(result['files']) == 2
    assert result['files'][0]['sha256'] == workflow.hashlib.sha256(b'{"input":"first"}').hexdigest()


def test_file_preflight_does_not_invent_seed_capability_from_fixture(tmp_path):
    prepared = plan(tmp_path)
    (tmp_path / 'input').write_bytes(b'actual bundle')
    (tmp_path / 'parameters').write_text('{"seed":7}')
    assert workflow.validate_files(prepared)['steps'] == 2
    (tmp_path / 'parameters').write_text('not json')
    with pytest.raises(ValueError, match='not valid JSON'):
        workflow.validate_files(prepared)
