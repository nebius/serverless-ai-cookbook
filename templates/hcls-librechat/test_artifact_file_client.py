import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('upload_artifact', Path(__file__).with_name('upload-artifact.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(tmp_path, corrupt=False, status=200):
    source = tmp_path / 'input.txt'
    content = 'UTF-8 fixture αβγ\r\n'.encode() + b'X' * 1000
    source.write_bytes(content)
    args = argparse.Namespace(file=source, model='fixture-app', media_type='text/plain',
                              output_dir=tmp_path / 'upload', idempotency_key='fixture-upload-001')
    args.output_dir.mkdir()
    ref = {'artifact_id': 'artifact-fixture', 'size_bytes': len(content),
           'sha256': hashlib.sha256(content).hexdigest(), 'media_type': 'text/plain', 'compression': 'none'}
    calls = []
    class Client:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            if name == 'begin_model_artifact_upload':
                assert arguments['sha256'] == ref['sha256']
                assert arguments['size_bytes'] == len(content)
                return {'structuredContent': {'operation_id': 'operation-fixture', 'upload_id': 'upload-fixture',
                    'handle': {'method': 'PUT', 'url': 'https://objects.example.invalid/signed-secret',
                               'headers': {'Content-Type': 'text/plain'}}}}
            assert name == 'finalize_model_artifact_upload'
            return {'structuredContent': dict(ref, sha256='0' * 64) if corrupt else ref}
    class Objects:
        async def put(self, url, *, content: object, headers):
            transferred = b''.join([chunk async for chunk in content])
            assert transferred == source.read_bytes()
            assert int(headers['Content-Length']) == len(transferred)
            assert not any(key.lower() == 'authorization' for key in headers)
            class Response:
                status_code = status
                def raise_for_status(self):
                    assert status == 200
            return Response()
    return args, Client(), Objects(), calls, ref


def test_actual_bytes_are_hashed_streamed_verified_and_replayed_without_transfer(tmp_path):
    args, client, http, calls, ref = fixture(tmp_path)
    first = asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))
    assert first['artifact'] == ref
    assert first['state'] == 'finalized'
    second = asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))
    assert second['artifact'] == ref
    assert len(calls) == 2
    assert json.loads((args.output_dir / 'artifact.json').read_text()) == ref
    assert 'fixture-key' not in (args.output_dir / 'receipt.json').read_text()
    assert 'signed-secret' not in (args.output_dir / 'artifact.json').read_text()


def test_changed_bytes_cannot_reuse_immutable_upload_identity(tmp_path):
    args, client, http, calls, _ = fixture(tmp_path)
    asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))
    args.file.write_bytes(b'changed')
    with pytest.raises(ValueError, match='identity changed'):
        asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))
    assert len(calls) == 2


def test_existing_write_is_verified_not_overwritten_or_assumed_correct(tmp_path):
    args, client, http, _, ref = fixture(tmp_path, status=412)
    assert asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))['artifact'] == ref


def test_mismatched_finalized_ref_cannot_become_model_input(tmp_path):
    args, client, http, _, _ = fixture(tmp_path, corrupt=True)
    with pytest.raises(ValueError, match='does not match'):
        asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))
    assert not (args.output_dir / 'artifact.json').exists()


def test_file_mutation_cancels_only_its_known_upload_reservation(tmp_path):
    args, client, http, _, _ = fixture(tmp_path)
    real_put, real_call = http.put, client.call_tool
    cancelled = []
    async def put(*positional, **keywords):
        response = await real_put(*positional, **keywords)
        args.file.write_bytes(b'changed during transfer')
        return response
    async def call(name, arguments):
        if name == 'cancel_operation':
            cancelled.append(arguments['operation_id'])
            return {'structuredContent': {'status': 'cancelled'}}
        return await real_call(name, arguments)
    http.put, client.call_tool = put, call
    with pytest.raises(ValueError, match='changed during transfer'):
        asyncio.run(module.transfer(client, http, args, 'https://gateway.example.invalid/mcp', 'fixture-key'))
    assert cancelled == ['operation-fixture']
    assert not (args.output_dir / 'artifact.json').exists()
