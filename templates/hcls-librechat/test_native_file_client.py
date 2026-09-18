import asyncio
import importlib.util
import json
import types
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('native_file_client', Path(__file__).with_name('invoke-native.py'))
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def test_saved_success_resumes_without_network_or_resubmission(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    source = tmp_path / 'input.json'
    source.write_text('{"samples":[]}')
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / 'run',
        model='phenoage', idempotency_key='acceptance-key')
    args.output_dir.mkdir()
    identity = {'model_id':'phenoage', 'input_sha256':client.hashlib.sha256(source.read_bytes()).hexdigest(),
        'endpoint':'https://example.invalid/mcp', 'caller_fingerprint':client.hashlib.sha256(b'synthetic-key').hexdigest(),
        'idempotency_key':'acceptance-key'}
    record = {'identity':identity, 'state':'succeeded', 'operation_id':'saved-operation'}
    client.save(args.output_dir / 'receipt.json', record)
    client.save(args.output_dir / 'result.json', {'test': True})
    assert asyncio.run(client.run(args)) == record
    source.write_text('{"samples":[{}]}')
    with pytest.raises(ValueError, match='different inputs'):
        asyncio.run(client.run(args))


def test_ambiguous_admission_is_not_resubmitted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    source = tmp_path / 'input.json'
    source.write_text('{}')
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / 'run',
        model='altumage', idempotency_key='acceptance-key')
    args.output_dir.mkdir()
    identity = {'model_id':'altumage', 'input_sha256':client.hashlib.sha256(source.read_bytes()).hexdigest(),
        'endpoint':'https://example.invalid/mcp', 'caller_fingerprint':client.hashlib.sha256(b'synthetic-key').hexdigest(),
        'idempotency_key':'acceptance-key'}
    client.save(args.output_dir / 'receipt.json', {'identity':identity, 'state':'admission_unknown'})
    with pytest.raises(RuntimeError, match='unknown'):
        asyncio.run(client.run(args))


def test_flat_operation_receipt_is_recovered_without_resubmitting(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    source = tmp_path / 'input.json'
    source.write_text('{}')
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / 'run',
        model='altumage', idempotency_key='acceptance-key')
    args.output_dir.mkdir()
    identity = {'model_id':'altumage', 'input_sha256':client.hashlib.sha256(source.read_bytes()).hexdigest(),
        'endpoint':'https://example.invalid/mcp', 'caller_fingerprint':client.hashlib.sha256(b'synthetic-key').hexdigest(),
        'idempotency_key':'acceptance-key'}
    client.save(args.output_dir / 'receipt.json', {'identity':identity, 'state':'admission_unknown'})
    accepted = {'id':'saved-operation','operation':'predict-age','model_id':'altumage',
        'idempotency_key':'acceptance-key','status':'failed'}
    client.save(args.output_dir / 'submission.json', {'structuredContent':accepted})
    recovered = asyncio.run(client.run(args))
    assert recovered['operation_id'] == 'saved-operation'
    assert recovered['state'] == 'failed'


def test_explicit_non_admission_is_safe_to_retry():
    error = {'isError': True, 'content': [{'type': 'text', 'text': json.dumps({'error': {
        'type': 'admission_limit_reached', 'code': 'admission_limit_reached',
        'message': 'retry shortly', 'retryable': True, 'durable_admission': False,
        'request_id': 'request-1', 'idempotency_key': 'acceptance-key',
        'retry_after_seconds': 2,
    }})}]}
    assert client.explicit_rejection(error) == {
        'type': 'admission_limit_reached', 'code': 'admission_limit_reached',
        'message': 'retry shortly', 'request_id': 'request-1',
        'idempotency_key': 'acceptance-key', 'retryable': True,
        'retry_after_seconds': 2, 'durable_admission': False,
    }
    error['content'][0]['text'] = json.dumps({'error': {'durable_admission': True}})
    assert client.explicit_rejection(error) is None


def test_result_artifact_is_hash_verified_and_decoded():
    data = b'{"answer":42}'
    envelope = {'schema': 'fs2-serve.nebius.ai/operation-artifact-result/v1',
        'content_type': 'application/json', 'artifact': {'artifact_id': 'artifact-1',
        'compression': 'none', 'size_bytes': len(data),
        'sha256': client.hashlib.sha256(data).hexdigest()}}
    assert client.parse_result_artifact(envelope, data) == {'answer': 42}
    with pytest.raises(ValueError, match='SHA-256'):
        client.parse_result_artifact(envelope, b'{"answer":43}')


def test_local_validation_failure_keeps_exact_pointer_and_receipt(tmp_path):
    record = {'identity': {'model_id': 'fixture'}, 'state': 'prepared'}
    schema = {'type': 'object', 'properties': {'samples': {'type': 'array', 'items': {
        'type': 'object', 'required': ['measured_value']}}}}
    with pytest.raises(client.ValidationError):
        client.validate_input(schema, {'samples': [{}]}, tmp_path, record)
    evidence = json.loads((tmp_path / 'validation-error.json').read_text())
    assert evidence['input_pointer'] == '/samples/0'
    assert evidence['schema_pointer'] == '/properties/samples/items/required'
    assert evidence['message'] == "'measured_value' is a required property"
    assert evidence['durable_admission'] is False
    assert client.load_receipt(tmp_path / 'receipt.json')['state'] == 'input_rejected'


def test_read_only_recovery_never_submits_to_recreate_missing_error(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    source = tmp_path / 'input.json'
    source.write_text('{"samples":[{}]}')
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / 'run',
        model='phenoage', idempotency_key='acceptance-key', recover_only=True)
    def forbidden_network(*args, **kwargs):
        pytest.fail('Read-only recovery must not rediscover or resubmit without a known operation.')
    monkeypatch.setattr(client.httpx2, 'AsyncClient', forbidden_network)
    with pytest.raises(RuntimeError, match='no known operation'):
        asyncio.run(client.run(args))
    receipt = client.load_receipt(args.output_dir / 'receipt.json')
    assert receipt['state'] == 'prepared'
    assert 'operation_id' not in receipt


def test_large_file_native_arrays_use_one_session_no_uploads(tmp_path, monkeypatch):
    """Transport-only fixture, not biological model qualification."""
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://example.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'synthetic-key')
    payload = {'cpg_sites': [f'fixture-{n}' for n in range(20318)],
               'samples': [{'sample_id': str(n), 'beta_values': [0.5] * 20318} for n in range(16)],
               'missing_values': 'error'}
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(payload))
    assert source.stat().st_size > 1_000_000
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / 'run',
        model='altumage', idempotency_key='file-backed-fixture', wait_seconds=30)
    calls, sessions = [], []
    schema = {'type': 'object', 'required': ['cpg_sites', 'samples'], 'properties': {
        'cpg_sites': {'type': 'array', 'minItems': 20318, 'maxItems': 20318},
        'samples': {'type': 'array', 'minItems': 1, 'maxItems': 128}}}
    class Response:
        def __init__(self, value): self.value = value
        def model_dump(self, **kwargs): return {'structuredContent': self.value}
    class MCP:
        async def __aenter__(self):
            sessions.append(self)
            return self
        async def __aexit__(self, *args): pass
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            if name == 'get_model_schema':
                return Response({'contracts': [{'protocol': 'native', 'tool_name': 'infer_altumage_native', 'input_schema': schema}]})
            if name == 'infer_altumage_native':
                assert arguments == {**payload, 'idempotency_key': args.idempotency_key, 'wait_seconds': 0}
                return Response({'id': 'original', 'status': 'running'})
            if name == 'get_operation':
                count = sum(n == name for n, _ in calls)
                return Response({'id': 'original', 'status': 'running' if count == 1 else 'succeeded', 'result_available': count > 1})
            if name == 'get_operation_result':
                return Response({'operation': {'id': 'original'}, 'result': {'fixture': True}})
            pytest.fail('No artifact upload or other tool is needed for valid file-backed arrays: ' + name)
    monkeypatch.setattr(client, 'Client', lambda *args: MCP())
    monkeypatch.setattr(client, 'streamable_http_client', lambda *args, **kwargs: None)
    async def sleep(delay): pass
    monkeypatch.setattr(client.asyncio, 'sleep', sleep)
    result = asyncio.run(client.run(args))
    assert result['state'] == 'succeeded' and len(sessions) == 1
    assert [name for name, _ in calls] == ['get_model_schema', 'infer_altumage_native',
        'get_operation', 'get_operation', 'get_operation_result']
    assert json.loads((args.output_dir / 'result.json').read_text()) == {'fixture': True}
