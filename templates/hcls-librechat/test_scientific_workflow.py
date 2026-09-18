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
                                     clock=iter((0, 2)).__next__))
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
                                     clock=iter((0, 2)).__next__))
    assert result['state'] == 'waiting_admission'
    assert result['completed_steps'] == []
