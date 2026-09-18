"""The packaged client reuses the existing real scientific-batch transport."""
import asyncio
import hashlib
import importlib.util
from pathlib import Path

import pytest

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
