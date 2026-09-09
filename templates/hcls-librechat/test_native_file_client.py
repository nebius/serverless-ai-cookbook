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
