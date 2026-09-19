"""Completed-result recovery reuses the batch client without any admission."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from test_execution import SCRIPT, call
from test_scientific_batch_client import client

OPERATION = '4e333485-573f-42ac-af81-a919cdf20913'


def setup_client(tmp_path, monkeypatch):
    data = {'manifest': b'', 'result': b'{"retained":true}', 'bundle': b'compressed\x00archive'}
    def ref(name):
        return {'artifact_id': name, 'sha256': client.digest(data[name]), 'size_bytes': len(data[name]),
                'media_type': 'application/x-tar' if name == 'bundle' else 'application/json',
                'compression': 'zstd' if name == 'bundle' else 'none'}
    manifest = {'entries': [{'name': name, 'semantic_type': name + '/v1', 'artifact': ref(name)}
                            for name in ('result', 'bundle')]}
    data['manifest'] = json.dumps(manifest).encode()
    result = {'operation_id': OPERATION, 'terminal_status': 'succeeded',
              'semantic_validation': {'status': 'passed'}, 'output_manifest': ref('manifest')}
    requested = []
    tools = []
    class Context:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        @asynccontextmanager
        async def stream(self, method, path):
            assert method == 'GET'
            requested.append(path)
            name = path.split('/')[-2]
            if name == 'bundle' and (tmp_path / 'disconnect-once').exists():
                (tmp_path / 'disconnect-once').unlink()
                raise ConnectionError('retained failed transfer')
            class Response:
                is_success = True
                headers = {}
                async def aiter_raw(self, chunk_size):
                    yield data[name]
            yield Response()
    async def rpc(connection, name, arguments):
        tools.append(name)
        assert arguments == {'operation_id': OPERATION}
        if name == 'get_scientific_status':
            return {'operation': {'id': OPERATION, 'status': result['terminal_status']},
                    'batch': {'result_published': result['terminal_status'] == 'succeeded'}}
        assert name == 'get_scientific_result'
        return result
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.example/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-owned-key')
    monkeypatch.setattr(client.httpx2, 'AsyncClient', lambda **kwargs: Context())
    monkeypatch.setattr(client, 'streamable_http_client', lambda *args, **kwargs: None)
    monkeypatch.setattr(client, 'Client', lambda *args, **kwargs: Context())
    monkeypatch.setattr(client, 'call', rpc)
    return argparse.Namespace(recover_operation_id=OPERATION, output=tmp_path / 'recovered'), result, requested, tools


def test_recovers_exact_manifest_and_children_without_inference(tmp_path, monkeypatch):
    args, _, requests, tools = setup_client(tmp_path, monkeypatch)
    receipt = asyncio.run(client.recover_completed(args))
    assert receipt['state'] == 'verified'
    assert tools == ['get_scientific_status', 'get_scientific_result']
    assert len(requests) == 3
    bundle = receipt['verified_artifacts'][1]
    assert bundle['name'] == 'bundle' and bundle['compression'] == 'zstd'
    assert Path(bundle['path']).read_bytes() == b'compressed\x00archive'
    asyncio.run(client.recover_completed(args))
    assert len(requests) == 3  # Existing bytes verified and reused, not redownloaded.


def test_disconnected_transfer_resumes_original_operation_and_exact_files(tmp_path, monkeypatch):
    args, _, requests, tools = setup_client(tmp_path, monkeypatch)
    (tmp_path / 'disconnect-once').touch()
    with pytest.raises(ConnectionError):
        asyncio.run(client.recover_completed(args))
    first = (args.output / 'output-00.artifact').read_bytes()
    receipt = asyncio.run(client.recover_completed(args))
    assert receipt['operation_id'] == OPERATION
    assert (args.output / 'output-00.artifact').read_bytes() == first
    assert requests.count('/v1/artifacts/result/content') == 1
    assert requests.count('/v1/artifacts/bundle/content') == 2
    assert set(tools) == {'get_scientific_status', 'get_scientific_result'}


@pytest.mark.parametrize('state', ['running', 'failed', 'preempted'])
def test_pending_or_failed_operation_never_downloads_or_resubmits(tmp_path, monkeypatch, state):
    args, result, requests, tools = setup_client(tmp_path, monkeypatch)
    result['terminal_status'] = state
    with pytest.raises(RuntimeError, match='No model work was submitted'):
        asyncio.run(client.recover_completed(args))
    assert tools == ['get_scientific_status'] and requests == []


def test_different_identity_or_changed_download_is_not_overwritten(tmp_path, monkeypatch):
    args, _, requests, _ = setup_client(tmp_path, monkeypatch)
    asyncio.run(client.recover_completed(args))
    target = args.output / 'output-01.artifact'
    target.write_bytes(b'retained corruption')
    with pytest.raises(RuntimeError, match='Existing artifact bytes differ'):
        asyncio.run(client.recover_completed(args))
    assert target.read_bytes() == b'retained corruption' and len(requests) == 3
    args.recover_operation_id = 'b9a1bf61-f2bc-4677-9692-fab8c76248c9'
    with pytest.raises(ValueError, match='different operation or caller'):
        asyncio.run(client.recover_completed(args))


def test_recovery_cli_does_not_require_original_inputs_or_inference_parameters(tmp_path, monkeypatch):
    async def recovered(args):
        assert args.recover_operation_id == OPERATION
        assert not hasattr(args, 'source') and not hasattr(args, 'idempotency_key')
        return {'state': 'verified'}
    monkeypatch.setattr(client, 'recover_completed', recovered)
    monkeypatch.setattr(sys, 'argv', ['batch', '--recover-operation-id', OPERATION, '--output', str(tmp_path / 'recovery')])
    client.main()


def test_typed_wrapper_reuses_job_and_preserves_directory_identity(tmp_path, monkeypatch):
    helper = tmp_path / 'existing client.py'
    helper.write_text('''import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--recover-operation-id',required=True);p.add_argument('--output',required=True)
a=p.parse_args();d=Path(a.output);d.mkdir(parents=True,exist_ok=True)
(d/'receipt.json').write_text(json.dumps({'operation_id':a.recover_operation_id}))
print(json.dumps({'state':'verified','inference_submitted':False}))
''')
    monkeypatch.setenv('SCIENTIFIC_CLIENT_PYTHON', sys.executable)
    monkeypatch.setenv('SCIENTIFIC_BATCH_HELPER', str(helper))
    args = {'operation_id': OPERATION, 'output_directory': 'actual mounted recovery'}
    _, first = call(tmp_path, 'recover_scientific_results', args)
    assert first['status'] == 'completed' and not first['inference_submitted']
    _, second = call(tmp_path, 'recover_scientific_results', args)
    assert first['job_id'] == second['job_id'] and second['reused_existing_job']
    spec = importlib.util.spec_from_file_location('recovery_execution', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(module, 'ROOT', tmp_path / 'jobs')
    with pytest.raises(ValueError, match='another operation'):
        module.recover_scientific_results({**args, 'operation_id': 'b9a1bf61-f2bc-4677-9692-fab8c76248c9'})
    assert len(list((tmp_path / 'jobs').glob('*/request.json'))) == 1
    assert 'recover_scientific_results_mcp_environment-execution' in SCRIPT.with_name('seed-workbench.js').read_text()
    assert 'apt-get install -y --no-install-recommends zstd' in SCRIPT.with_name('Dockerfile').read_text()
