"""Dedicated-instance publication concurrency; no network/model calls."""
import asyncio
from contextlib import contextmanager
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import stat
import types

import pytest

import scientific_receipts as receipts


CTX = multiprocessing.get_context('fork')
ROOT = Path(__file__).parent


@pytest.fixture(autouse=True)
def local_locks(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_RECEIPT_LOCK_DIR', str(tmp_path / 'local-locks'))


@contextmanager
def process(target, *args):
    child = CTX.Process(target=target, args=args)
    child.start()
    try:
        yield child
    finally:
        child.join(3)
        if child.is_alive():
            child.kill()
            child.join(3)


def paused_writer(path, value, location, partial, release, crash=False):
    original = receipts._write_verified

    def write(target, data):
        selected = target == path if location == 'canonical' else target.parent == receipts._journal(path)
        if selected:
            # Reproduce visibility of the final filename before its full JSON.
            with target.open('wb') as stream:
                stream.write(data[:max(1, len(data) // 2)])
                stream.flush()
                os.fsync(stream.fileno())
                partial.set()
                if not release.wait(5):
                    raise TimeoutError('Test did not release writer')
                if crash:
                    os._exit(42)
        original(target, data)

    receipts._write_verified = write
    receipts.save(path, value)


def reader(path, started, result):
    started.set()
    try:
        result.send(('record', receipts.load(path)))
    except Exception as error:
        result.send(('error', type(error).__name__, str(error)))


@pytest.mark.parametrize('filename,location', [
    ('receipt.json', 'journal'), ('receipt.json', 'canonical'), ('study-worker.json', 'canonical'),
])
def test_reader_waits_for_entire_publication(tmp_path, filename, location):
    path = tmp_path / 'bucket' / filename
    receipts.save(path, {'state': 'prepared'})
    partial, release, started = CTX.Event(), CTX.Event(), CTX.Event()
    result, sender = CTX.Pipe(duplex=False)
    expected = {'state': 'running', 'operation_id': 'retained-operation'}
    with process(paused_writer, path, expected, location, partial, release) as writer:
        assert partial.wait(3)
        with process(reader, path, started, sender) as observer:
            assert started.wait(3)
            assert not result.poll(0.15), 'Observer read a partially published generation'
            release.set()
            assert result.poll(3)
            assert result.recv() == ('record', expected)
        assert observer.exitcode == 0
    assert writer.exitcode == 0
    assert receipts.load(path) == expected


def paused_reader(path, reading, release, result):
    original = Path.read_text

    def read(target, *args, **kwargs):
        if target == path:
            reading.set()
            if not release.wait(5):
                raise TimeoutError('Test did not release reader')
        return original(target, *args, **kwargs)

    Path.read_text = read
    result.send(receipts.load(path))


def writer(path, value, started, finished):
    started.set()
    receipts.save(path, value)
    finished.set()


def test_load_holds_shared_lock_during_read_not_only_selection(tmp_path):
    # Non-journal health records are mutable; locking only glob/selection is insufficient.
    path = tmp_path / 'study-worker.json'
    before, after = {'state': 'before'}, {'state': 'after'}
    receipts.save(path, before)
    reading, release, started, finished = (CTX.Event() for _ in range(4))
    result, sender = CTX.Pipe(duplex=False)
    with process(paused_reader, path, reading, release, sender) as observer:
        assert reading.wait(3)
        with process(writer, path, after, started, finished) as publisher:
            assert started.wait(3)
            assert not finished.wait(0.15)
            release.set()
            assert result.poll(3)
            assert result.recv() == before
            assert finished.wait(3)
        assert publisher.exitcode == 0
    assert observer.exitcode == 0
    assert receipts.load(path) == after


@pytest.mark.parametrize('location', ['journal', 'canonical'])
def test_writer_crash_releases_lock_but_does_not_skip_latest_journal(tmp_path, location):
    path = tmp_path / 'receipt.json'
    receipts.save(path, {'state': 'prepared'})
    expected = {'state': 'running', 'operation_id': 'retained-operation'}
    partial, release, started = CTX.Event(), CTX.Event(), CTX.Event()
    result, sender = CTX.Pipe(duplex=False)
    with process(paused_writer, path, expected, location, partial, release, True) as publisher:
        assert partial.wait(3)
        with process(reader, path, started, sender) as observer:
            assert started.wait(3)
            assert not result.poll(0.15)
            release.set()
            assert result.poll(3), 'Writer crash left a permanently held lock'
            observed = result.recv()
        assert observer.exitcode == 0
    assert publisher.exitcode == 42
    if location == 'journal':
        assert observed[:2] == ('error', 'RuntimeError')
        assert 'Admission may be unknown' in observed[2]
        assert json.loads(path.read_text()) == {'state': 'prepared'}
        with pytest.raises(RuntimeError, match='Admission may be unknown'):
            receipts.load(path)
    else:
        # A fully published journal remains authoritative after canonical failure.
        assert observed == ('record', expected)
        assert receipts.load(path) == expected


def test_publication_namespace_is_distinct_from_operation_lock_and_other_paths(tmp_path):
    first = tmp_path / 'bucket' / 'one' / 'receipt.json'
    second = tmp_path / 'bucket' / 'two' / 'receipt.json'
    with receipts.receipt_lock(first.parent):
        receipts.save(first, {'state': 'prepared'})
        assert receipts.load(first) == {'state': 'prepared'}
        with receipts._publication_lock(first, writing=True):
            receipts.save(second, {'state': 'independent'})
            assert receipts.load(second) == {'state': 'independent'}
    files = list((tmp_path / 'local-locks').glob('*.lock'))
    assert len(files) == 3
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files)
    assert not list((tmp_path / 'bucket').rglob('*.lock'))


def native_client():
    spec = importlib.util.spec_from_file_location('publication_native_client', ROOT / 'invoke-native.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def crash_native_admission(args, phase, external_calls):
    """Exercise the real client's before-call and after-call persistence order."""
    client = native_client()
    original = receipts._write_verified

    def write(path, data):
        state = json.loads(data).get('state')
        interrupt = ((phase == 'before_external' and state == 'submitting')
                     or (phase == 'after_external_journal' and state == 'running'))
        if interrupt and path.parent == receipts._journal(args.output_dir / 'receipt.json'):
            with path.open('wb') as stream:
                stream.write(data[:len(data) // 2])
                stream.flush()
                os.fsync(stream.fileno())
            os._exit(42)
        original(path, data)

    receipts._write_verified = write

    class Response:
        def __init__(self, value):
            self.value = value

        def model_dump(self, **_kwargs):
            return {'structuredContent': self.value}

    class Context:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def call_tool(self, name, arguments):
            if name == 'get_model_schema':
                return Response({'contracts': [{'protocol': 'native', 'tool_name': 'infer_fixture_native',
                                                'input_schema': {'type': 'object'}}]})
            assert name == 'infer_fixture_native'
            external_calls.write_text('one simulated admission')
            if phase == 'after_external_before_response':
                os._exit(42)
            return Response({'id': 'retained-operation', 'status': 'running', 'model_id': args.model,
                             'idempotency_key': args.idempotency_key})

    client.httpx2.AsyncClient = lambda **_kwargs: Context()
    client.Client = lambda *_args, **_kwargs: Context()
    client.streamable_http_client = lambda *_args, **_kwargs: None
    with receipts.receipt_lock(args.output_dir):
        asyncio.run(client.run(args))
    raise AssertionError('Injected writer crash did not occur')


@pytest.mark.parametrize('phase', ['before_external', 'after_external_before_response', 'after_external_journal'])
def test_native_crash_around_admission_never_resubmits(tmp_path, monkeypatch, phase):
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    source = tmp_path / 'input.json'
    source.write_text('{}')
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / 'run', model='fixture',
                                 idempotency_key='unchanged-key', wait_seconds=30)
    calls = tmp_path / 'external-call.txt'
    with process(crash_native_admission, args, phase, calls) as child:
        child.join(5)
    assert child.exitcode == 42
    assert calls.exists() is (phase != 'before_external')
    before = {str(path): path.read_bytes() for path in args.output_dir.rglob('*') if path.is_file()}
    client = native_client()

    def forbidden(*_args, **_kwargs):
        pytest.fail('Ambiguous/crashed admission must not open a network session or resubmit')

    monkeypatch.setattr(client.httpx2, 'AsyncClient', forbidden)
    monkeypatch.setattr(client, 'Client', forbidden)
    # The dead process's long operation lock is released as well.
    with receipts.receipt_lock(args.output_dir):
        with pytest.raises(RuntimeError, match='[Aa]dmission.*unknown'):
            asyncio.run(client.run(args))
    for name, content in before.items():
        # A complete submitting receipt may get another immutable copy, but no old evidence is erased.
        assert Path(name).read_bytes() == content
    assert calls.exists() is (phase != 'before_external')
