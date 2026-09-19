"""A worker's long phase lock must not turn accepted replay into rejection."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import scientific_study as study  # noqa: E402
from scientific_receipts import load, receipt_lock, save  # noqa: E402

SPEC = importlib.util.spec_from_file_location('submission_replay_execution', HERE / 'execution-mcp.py')
execution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution)


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    for name, value in {
        'SCIENTIFIC_WORKSPACE': str(tmp_path),
        'SCIENTIFIC_RECEIPT_LOCK_DIR': str(tmp_path / 'locks'),
        'SCIENTIFIC_EXECUTION_DIR': str(tmp_path / 'jobs'),
        'SCIENTIFIC_MODELS_MCP_URL': 'https://platform.test/mcp',
        'SCIENTIFIC_MODELS_API_KEY': 'synthetic-replay-key',
        'SEED_DEFAULT_USER_EMAIL': 'replay@example.test',
        'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    return tmp_path


def plan():
    return {'schema': 'scientific-workflow/v2', 'title': 'Replay preserves admission',
            'steps': [{'id': 'data', 'kind': 'analysis', 'method': 'write-json',
                       'arguments': {'filename': 'data.json', 'value': {'measured': 7}}}],
            'deliverables': [{'name': 'data.json', 'role': 'report',
                              'source': {'step': 'data', 'file': 'data.json'}}]}


def test_replay_of_saved_study_does_not_acquire_active_phase_lock(mounted, monkeypatch):
    first = study.submit(plan(), mounted / 'result')
    folder = study.directory(first['id'])
    original = (folder / 'receipt.json').read_bytes()
    versions = sorted((folder / '.receipt-history/receipt.json').glob('*.json'))
    monkeypatch.setattr(study, 'validate', lambda *args: pytest.fail('Replay must not rerun preflight'))
    with receipt_lock(folder):
        replay = study.submit(plan(), mounted / 'result')
    assert replay['id'] == first['id'] and replay['state'] == 'queued'
    assert replay['study_admission'] == 'accepted'
    assert replay['reused_existing_study'] is True
    assert replay['new_study_admitted'] is False
    assert (folder / 'receipt.json').read_bytes() == original
    assert sorted((folder / '.receipt-history/receipt.json').glob('*.json')) == versions


def test_actual_running_phase_and_replay_complete_only_once(mounted):
    first = study.submit(plan(), mounted / 'running')
    entered, release = threading.Event(), threading.Event()
    calls = []

    def local(step, record):
        calls.append(step['id'])
        entered.set()
        assert release.wait(10), 'Test must release its worker'
        return study.run_local(step, record)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: asyncio.run(study.advance(first['id'], local_runner=local)))
        try:
            assert entered.wait(5)
            replay = execution.run_scientific_workflow({
                'study': plan(), 'output_directory': str(mounted / 'running')})
            assert replay['id'] == first['id'] and replay['state'] == 'running'
            assert replay['study_admission'] == 'accepted'
        finally:
            release.set()
        future.result(timeout=5)
    final = asyncio.run(study.advance(first['id']))
    assert final['state'] == 'completed' and calls == ['data']
    assert len(study.list_studies()) == 1
    assert json.loads(Path(final['artifacts'][0]['path']).read_bytes()) == {'measured': 7}


def test_busy_first_submission_is_unknown_not_false_rejection(mounted, monkeypatch):
    import hashlib
    import uuid
    output = mounted / 'not-yet-persisted'
    fingerprint = hashlib.sha256(study.canonical({
        'plan': plan(), 'output': str(output), 'owner': study.owner_identity()})).hexdigest()
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, fingerprint))
    folder = study.directory(identifier)
    folder.mkdir(parents=True)
    monkeypatch.setattr(study, 'validate', lambda *args: pytest.fail('Lock loser must not admit work'))
    with receipt_lock(folder):
        result = study.submit(plan(), output)
    assert result['id'] == identifier and result['study_admission'] == 'unknown'
    assert result['status'] == 'admission_pending'
    assert result['new_study_admitted'] is False
    assert result['next_observation']['tool_name'] == 'read_execution'
    assert 'Do not resubmit' in result['guidance']
    assert not (folder / 'receipt.json').exists() and not output.exists()


def test_existing_caller_and_identity_checks_are_not_bypassed(mounted, monkeypatch):
    first = study.submit(plan(), mounted / 'bound')
    folder = study.directory(first['id'])
    with receipt_lock(folder):
        monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'different-synthetic-key')
        with pytest.raises(ValueError, match='identity/caller changed'):
            study.submit(plan(), mounted / 'bound')
        monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-replay-key')
        record = load(folder / 'receipt.json')
        record['identity'] = 'different-plan-fingerprint'
        save(folder / 'receipt.json', record)
        with pytest.raises(ValueError, match='identity/caller changed'):
            study.submit(plan(), mounted / 'bound')


def test_unreadable_latest_receipt_is_not_replaced(mounted):
    first = study.submit(plan(), mounted / 'damaged')
    folder = study.directory(first['id'])
    latest = sorted((folder / '.receipt-history/receipt.json').glob('*.json'))[-1]
    latest.write_bytes(b'{')
    with receipt_lock(folder), pytest.raises(RuntimeError, match='Admission may be unknown'):
        study.submit(plan(), mounted / 'damaged')
    assert latest.read_bytes() == b'{'


@pytest.mark.parametrize('transport', ['inline', 'plan_file'])
def test_real_stdio_sdk_returns_saved_admission_during_worker_lock(mounted, transport):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    first = study.submit(plan(), mounted / 'sdk')
    plan_file = mounted / 'same-plan.json'
    plan_file.write_text(json.dumps(plan()))
    arguments = {'study': plan()} if transport == 'inline' else {'plan_file': str(plan_file)}
    arguments['output_directory'] = str(mounted / 'sdk')

    async def check():
        server = StdioServerParameters(command=sys.executable,
            args=[str(HERE / 'execution-mcp.py')], env=dict(os.environ))
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                with receipt_lock(study.directory(first['id'])):
                    result = await session.call_tool('run_scientific_workflow', arguments)
                assert not result.model_dump(by_alias=True)['isError']
                record = json.loads(result.content[0].text)
                assert record['id'] == first['id']
                assert record['study_admission'] == 'accepted'
                assert record['reused_existing_study'] is True

    asyncio.run(check())


def test_racing_publication_is_read_after_a_busy_admission_lock(mounted, monkeypatch):
    first = study.submit(plan(), mounted / 'race')
    target = study.directory(first['id']) / 'receipt.json'
    observed = []

    def first_read_precedes_publication(path):
        if path == target:
            observed.append(path)
            if len(observed) == 1:
                return None
        return load(path)

    monkeypatch.setattr(study, 'load', first_read_precedes_publication)
    with receipt_lock(target.parent):
        result = study.submit(plan(), mounted / 'race')
    assert len(observed) == 2
    assert result['study_admission'] == 'accepted' and result['id'] == first['id']
    assert result['reused_existing_study'] is True


def test_non_lock_storage_error_is_not_mislabelled_as_busy_replay(mounted, monkeypatch):
    def fail_storage(*args):
        raise BlockingIOError(11, 'Synthetic storage failure')

    monkeypatch.setattr(study, 'save', fail_storage)
    with pytest.raises(BlockingIOError, match='Synthetic storage failure'):
        study.submit(plan(), mounted / 'storage-error')
    assert not study.list_studies()
