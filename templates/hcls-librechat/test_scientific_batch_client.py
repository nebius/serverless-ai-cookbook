"""The packaged client reuses the existing real scientific-batch transport."""
import asyncio
import hashlib
import importlib.util
from pathlib import Path

import pytest
import sys
import argparse
import json

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('batch_client', ROOT / 'scripts/scientific-batch-acceptance.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def test_packaged_helper_and_skill_use_one_canonical_batch_implementation():
    docker = (ROOT / 'Dockerfile').read_text()
    assert 'COPY templates/hcls-librechat/scripts/scientific-batch-acceptance.py /opt/bionemo/invoke-scientific-batch.py' in docker
    skill = (ROOT.parents[1] / 'life-science/bionemo-librechat/skills/scientific-gateway/SKILL.md').read_text()
    assert 'invoke-scientific-batch.py' in skill
    assert 'no compatible attachment\nbridge or connected structure viewer' not in skill
    assert 'nonterminal, not proof' in skill
    assert 'workbench_get_operation_result' in skill


def test_batch_upload_hashes_and_verifies_exact_compressed_file():
    data = b'bounded exact scientific bundle fixture\x00\xff'
    calls = []
    class Response:
        is_success = True
        def __init__(self, body):
            self.body = body
        def json(self):
            return self.body
    class HTTP:
        async def post(self, path, *, json, headers=None):
            calls.append(('POST', path, json))
            if path.endswith('/uploads'):
                assert json['sha256'] == hashlib.sha256(data).hexdigest()
                assert json['size_bytes'] == len(data)
                assert headers['idempotency-key'] == 'batch-input-fixture'
                return Response({'max_content_bytes': 1000, 'content_path': '/v1/scientific-artifacts/uploads/fixture/content',
                                 'operation_id': 'operation-fixture', 'upload_id': 'fixture'})
            assert json == {'operation_id': 'operation-fixture'}
            return Response({'artifact_id': 'artifact-fixture', 'size_bytes': len(data),
                             'sha256': hashlib.sha256(data).hexdigest(),
                             'media_type': 'application/gzip', 'compression': 'gzip'})
        async def put(self, path, *, content, headers):
            assert content == data and headers['content-length'] == str(len(data))
            calls.append(('PUT', path, len(content)))
            return Response({})
    result = asyncio.run(client.upload(HTTP(), 'fixture-model', data, 'application/gzip', 'gzip', 'batch-input-fixture'))
    assert result['artifact_id'] == 'artifact-fixture'
    assert [call[0] for call in calls] == ['POST', 'PUT', 'POST']


def test_batch_download_must_verify_bytes_before_deliverable(tmp_path):
    class Response:
        is_success = True
        content = b'wrong bytes'
    class HTTP:
        async def get(self, path):
            return Response()
    target = tmp_path / 'output.artifact'
    with pytest.raises(RuntimeError, match='hash or size mismatch'):
        asyncio.run(client.download(HTTP(), {'artifact_id': 'fixture', 'size_bytes': 4, 'sha256': '0' * 64}, target))
    assert not target.exists()


@pytest.mark.parametrize('state,code', [('verified', 0), ('running', 75), ('queued', 75)])
def test_cli_observation_does_not_claim_shell_success(tmp_path, monkeypatch, state, code):
    async def run(args):
        return {'state': state, 'operation_id': 'original'}
    monkeypatch.setattr(client, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['batch', '--model', 'fixture', '--tool', 'submit_fixture',
        '--operation', 'design', '--source', str(tmp_path / 'input'), '--media-type', 'text/plain',
        '--entry-name', 'input', '--semantic-type', 'fixture/v1', '--parameters', str(tmp_path / 'params'),
        '--output', str(tmp_path / 'run'), '--idempotency-key', 'stable', '--display-name', 'fixture'])
    with pytest.raises(SystemExit) as error:
        client.main()
    assert error.value.code == code


def test_discovered_semantic_role_fails_before_upload_for_filename_mistake():
    contract = {'protocol': 'scientific-batch-v1', 'input_artifact_contract': {
        'source_kind_parameter': 'parameters.source.kind', 'exactly_one_entry': True,
        'source_kinds': {'uploaded-bundle': {'name': 'lerobot-dataset',
          'semantic_type': 'lerobot-v3-bundle/v1', 'media_type': 'application/x-tar',
          'compression': 'zstd', 'maximum_bytes': 10000}}}}
    args = argparse.Namespace(entry_name='recorded.tar.zst', semantic_type='lerobot-bundle',
                              media_type='application/x-tar', compression='zstd')
    with pytest.raises(ValueError, match='semantic role, not the local filename'):
        client.preflight_source(contract, {'source': {'kind': 'uploaded-bundle'}}, args, 100)
    args.entry_name = 'lerobot-dataset'
    args.semantic_type = 'lerobot-v3-bundle/v1'
    client.preflight_source(contract, {'source': {'kind': 'uploaded-bundle'}}, args, 100)
    assert client.scientific_contract({'contracts': [contract]}) is contract


def test_reused_finalized_source_must_match_bytes_and_format(tmp_path):
    data = b'exact original source'
    args = argparse.Namespace(media_type='application/x-tar', compression='zstd')
    reference = {'artifact_id': 'caller-owned-fixture', 'sha256': client.digest(data),
                 'size_bytes': len(data), 'media_type': args.media_type, 'compression': args.compression}
    source = tmp_path / 'artifact.json'
    source.write_text(json.dumps(reference))
    assert client.source_reference(source, data, args) == reference
    with pytest.raises(ValueError, match='exact source bytes'):
        client.source_reference(source, data + b'changed', args)


def test_old_schema_without_manifest_policy_retains_existing_transport():
    client.preflight_source({}, {}, argparse.Namespace(), 100)


def test_real_top_level_discovery_preserves_manifest_and_fixed_entry_policy():
    entry = {'name': 'protenix-input', 'semantic_type': 'protenix-input-json/v1',
             'media_type': 'application/json', 'compression': 'none', 'maximum_bytes': 4096}
    selected = {'protocol': 'scientific-batch-v1', 'input_schema': {}}
    discovery = {'model_id': 'protenix-v2', 'contracts': [selected],
                 'input_artifact_contract': {'exactly_one_entry': True, 'entry': entry},
                 'artifact_manifest_schema': {'type': 'object', 'required': ['entries']}}
    contract = client.scientific_contract(discovery)
    assert contract['artifact_manifest_schema'] == discovery['artifact_manifest_schema']
    assert 'input_artifact_contract' not in selected
    args = argparse.Namespace(entry_name='protenix-v2-1acb-heteromer-s1', semantic_type='fs2.protenix-v2-input/v1',
                              media_type='application/vnd.fs2.scientific-manifest+json', compression='none')
    with pytest.raises(ValueError) as error:
        client.preflight_source(contract, {}, args, 596)
    assert all(word in str(error.value) for word in ['name must', 'semantic_type must', 'media_type must', 'No upload'])
    args.entry_name, args.semantic_type, args.media_type = entry['name'], entry['semantic_type'], entry['media_type']
    client.preflight_source(contract, {}, args, 596)
    assert args.entry_name == 'protenix-input'  # No automatic caller correction.


def test_operation_selected_roles_and_compression_alternatives_are_generic():
    policy = {'exactly_one_entry': True, 'operation_parameter': 'operation', 'operations': {
        'design-backbone': {'name': 'design-spec', 'semantic_type': 'design-json/v1', 'media_type': 'application/json',
                            'compression': 'none', 'allowed_compressions': ['none', 'gzip'], 'maximum_bytes': 512},
        'scaffold-motif': {'name': 'motif-pdb', 'semantic_type': 'motif-pdb/v1', 'media_type': 'chemical/x-pdb',
                           'compression': 'none', 'allowed_compressions': ['none'], 'maximum_bytes': 1024}}}
    contract = client.scientific_contract({'contracts': [{'protocol': 'scientific-batch-v1'}], 'input_artifact_contract': policy})
    args = argparse.Namespace(operation='design-backbone', entry_name='design-spec', semantic_type='design-json/v1',
                              media_type='application/json', compression='gzip')
    client.preflight_source(contract, {}, args, 512)
    with pytest.raises(ValueError, match='maximum_bytes'):
        client.preflight_source(contract, {}, args, 513)
    args.operation = 'scaffold-motif'
    with pytest.raises(ValueError, match='motif-pdb'):
        client.preflight_source(contract, {}, args, 512)
    args.operation = 'undeclared-mode'
    with pytest.raises(ValueError, match='not in the published'):
        client.preflight_source(contract, {}, args, 512)


def test_top_level_source_kind_policy_is_enforced_for_existing_cosmos_shape():
    contract = client.scientific_contract({'contracts': [{'protocol': 'scientific-batch-v1'}],
        'input_artifact_contract': {'source_kind_parameter': 'parameters.source.kind', 'source_kinds': {
            'uploaded-bundle': {'name': 'lerobot-dataset', 'semantic_type': 'lerobot-v3-bundle/v1',
                                'media_type': 'application/x-tar', 'compression': 'zstd'}}}})
    args = argparse.Namespace(entry_name='recorded.tar.zst', semantic_type='lerobot-bundle',
                              media_type='application/x-tar', compression='zstd')
    with pytest.raises(ValueError, match='lerobot-dataset'):
        client.preflight_source(contract, {'source': {'kind': 'uploaded-bundle'}}, args, 100)


def test_run_rejects_published_role_mismatch_before_any_upload_or_admission(tmp_path, monkeypatch):
    from types import SimpleNamespace
    calls = []
    class Context:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
    class MCP(Context):
        async def list_tools(self):
            tool = SimpleNamespace(name='submit_fixture', model_dump=lambda **kwargs: {'name': 'submit_fixture'})
            return SimpleNamespace(tools=[tool])
    async def discovered(connection, name, arguments):
        calls.append(name)
        assert name == 'get_model_schema'
        return {'contracts': [{'protocol': 'scientific-batch-v1'}], 'input_artifact_contract': {
            'entry': {'name': 'model-input', 'semantic_type': 'model-json/v1',
                      'media_type': 'application/json', 'compression': 'none'}}}
    async def forbidden_upload(*args, **kwargs):
        calls.append('upload')
        raise AssertionError('Preflight must finish before reserving storage or submitting inference')
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://fixture.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-only-key')
    monkeypatch.setattr(client.httpx2, 'AsyncClient', lambda **kwargs: Context())
    monkeypatch.setattr(client, 'streamable_http_client', lambda *args, **kwargs: None)
    monkeypatch.setattr(client, 'Client', lambda *args, **kwargs: MCP())
    monkeypatch.setattr(client, 'call', discovered)
    monkeypatch.setattr(client, 'upload', forbidden_upload)
    source, params = tmp_path/'source.json', tmp_path/'params.json'
    source.write_text('{}')
    params.write_text('{}')
    args = argparse.Namespace(source=source, parameters=params, model='fixture', output=tmp_path/'run',
        idempotency_key='unchanged-fixture', tool='submit_fixture', operation='predict',
        entry_name='invented-file.json', semantic_type='invented/v1',
        media_type='application/vnd.fs2.scientific-manifest+json', compression='none')
    with pytest.raises(ValueError, match='No upload or inference'):
        asyncio.run(client.run(args))
    assert calls == ['get_model_schema']
    receipt = client.load_receipt(args.output/'receipt.json')
    assert receipt['state'] == 'prepared' and 'operation_id' not in receipt
