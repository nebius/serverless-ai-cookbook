"""Large scientific result files retain exact bytes with bounded client memory."""
import asyncio
from contextlib import asynccontextmanager
import errno
import gzip
import hashlib
import itertools
from pathlib import Path
import tracemalloc

import pytest

from test_scientific_batch_client import client


def reference(data):
    return {'artifact_id': 'scope/retained', 'size_bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


class HTTP:
    def __init__(self, chunks, headers=None, status=200):
        self.chunks = chunks
        self.headers = headers or {}
        self.status = status
        self.paths = []
        self.closed = False

    @asynccontextmanager
    async def stream(self, method, path):
        assert method == 'GET'
        self.paths.append(path)
        owner = self
        class Response:
            is_success = 200 <= owner.status < 300
            status_code = owner.status
            headers = owner.headers
            @property
            def content(self):
                raise AssertionError('Whole-body download is forbidden')
            async def aiter_raw(self, chunk_size):
                assert chunk_size == client.ARTIFACT_CHUNK_BYTES
                for chunk in owner.chunks():
                    if isinstance(chunk, BaseException):
                        raise chunk
                    yield chunk
        try:
            yield Response()
        finally:
            self.closed = True


def test_exact_compressed_raw_bytes_and_atomic_publication(tmp_path):
    payload = gzip.compress(b'actual stored compressed weights' * 1000)
    http = HTTP(lambda: [payload[:9], payload[9:]], {'content-encoding': 'gzip'})
    target = tmp_path / 'result.gz'
    receipt = asyncio.run(client.download(http, reference(payload), target))
    assert target.read_bytes() == payload
    assert receipt['publication'] == 'atomic-link'
    assert http.paths == ['/v1/artifacts/scope%2Fretained/content'] and http.closed


@pytest.mark.parametrize('chunks,size,checksum,headers,match', [
    ([b'ab', ConnectionError('interrupted transfer')], 4, hashlib.sha256(b'abcd').hexdigest(), {}, 'interrupted'),
    ([b'abcde'], 4, hashlib.sha256(b'abcd').hexdigest(), {}, 'exceeds'),
    ([b'ab'], 4, hashlib.sha256(b'abcd').hexdigest(), {}, 'hash or size'),
    ([b'abcd'], 4, '0' * 64, {}, 'hash or size'),
    ([b'abcd'], 4, hashlib.sha256(b'abcd').hexdigest(), {'content-length': '5'}, 'Content-Length'),
])
def test_failed_network_bytes_never_publish_or_leave_spool(tmp_path, monkeypatch, chunks, size, checksum, headers, match):
    spool = tmp_path / 'local-spool'
    spool.mkdir()
    monkeypatch.setattr(client.tempfile, 'tempdir', str(spool))
    target = tmp_path / 'customer' / 'artifact'
    http = HTTP(lambda: chunks, headers)
    with pytest.raises((RuntimeError, ConnectionError), match=match):
        asyncio.run(client.download(http, {'artifact_id': 'stored', 'size_bytes': size, 'sha256': checksum}, target))
    assert not target.exists() and list(spool.iterdir()) == [] and http.closed


@pytest.mark.parametrize('status', [302, 401, 403, 404, 503])
def test_failed_http_is_not_followed_or_published(tmp_path, status):
    http = HTTP(lambda: [b'no'], {'location': 'https://not-followed.invalid/'}, status)
    target = tmp_path / 'artifact'
    with pytest.raises(RuntimeError, match=f'HTTP {status}'):
        asyncio.run(client.download(http, reference(b'no'), target))
    assert len(http.paths) == 1 and not target.exists()


def test_existing_dataset_reuses_chunked_hash_without_network(tmp_path, monkeypatch):
    payload = b'keep retained bytes'
    target = tmp_path / 'artifact'
    target.write_bytes(payload)
    monkeypatch.setattr(Path, 'read_bytes', lambda self: (_ for _ in ()).throw(AssertionError('unbounded read')))
    http = HTTP(lambda: [])
    receipt = asyncio.run(client.download(http, reference(payload), target))
    assert not http.paths and receipt['publication'] == 'verified-existing'
    with pytest.raises(RuntimeError, match='preserve'):
        asyncio.run(client.download(http, reference(b'different'), target))
    assert target.open('rb').read() == payload


def force_bucket_link_error(*args):
    raise OSError(errno.EXDEV, 'actual local spool to bucket boundary')


def test_bucket_publication_uses_verified_copy_without_rename(tmp_path, monkeypatch):
    monkeypatch.setattr(client.os, 'link', force_bucket_link_error)
    monkeypatch.setattr(client.os, 'replace', lambda *args: (_ for _ in ()).throw(AssertionError('bucket rename')))
    payload = b'bucket data' * 10000
    target = tmp_path / 'artifact'
    receipt = asyncio.run(client.download(HTTP(lambda: [payload]), reference(payload), target))
    assert receipt['publication'] == 'verified-copy' and target.read_bytes() == payload


def test_bucket_write_failure_removes_only_owned_partial_target(tmp_path, monkeypatch):
    monkeypatch.setattr(client.os, 'link', force_bucket_link_error)
    real_fsync = client.os.fsync
    calls = 0
    def fail_second_fsync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('bucket write interrupted')
        real_fsync(fd)
    monkeypatch.setattr(client.os, 'fsync', fail_second_fsync)
    existing = tmp_path / 'prior-evidence'
    existing.write_bytes(b'keep')
    target = tmp_path / 'artifact'
    with pytest.raises(OSError, match='interrupted'):
        asyncio.run(client.download(HTTP(lambda: [b'new']), reference(b'new'), target))
    assert not target.exists() and existing.read_bytes() == b'keep'


def test_cleanup_failure_preserves_original_error_and_identifies_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(client.os, 'link', force_bucket_link_error)
    staged = tmp_path / 'staged'
    staged.write_bytes(b'new')
    target = tmp_path / 'artifact'
    monkeypatch.setattr(client.os, 'fsync', lambda fd: (_ for _ in ()).throw(OSError('original write failure')))
    real_unlink = Path.unlink
    def fail_target_unlink(path, *args, **kwargs):
        if path == target:
            raise OSError('bucket temporarily unavailable')
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail_target_unlink)
    with pytest.raises(OSError, match='original write failure') as error:
        client.publish_artifact(staged, target, reference(b'new'))
    assert target.exists()
    assert any('Partial artifact remains' in note and str(target) in note for note in error.value.__notes__)


def test_real_httpx_stream_preserves_content_encoding_bytes(tmp_path):
    payload = gzip.compress(b'not transparently decoded' * 1000)
    class RawBody(client.httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield payload[:11]
            yield payload[11:]
    async def exercise():
        async def transport(request):
            assert request.url.host == 'platform.invalid'
            assert request.headers['authorization'] == 'Bearer test-only'
            return client.httpx2.Response(200, headers={'content-encoding': 'gzip', 'content-length': str(len(payload))}, stream=RawBody())
        async with client.httpx2.AsyncClient(base_url='https://platform.invalid', headers={'authorization': 'Bearer test-only'},
                                            follow_redirects=False, transport=client.httpx2.MockTransport(transport)) as http:
            return await client.download(http, reference(payload), tmp_path / 'stored.gz')
    asyncio.run(exercise())
    assert (tmp_path / 'stored.gz').read_bytes() == payload


def test_concurrent_existing_bytes_are_never_overwritten(tmp_path, monkeypatch):
    target = tmp_path / 'artifact'
    def competing_publish(source, destination):
        destination.write_bytes(b'someone retained this')
        raise FileExistsError('competing completed output')
    monkeypatch.setattr(client.os, 'link', competing_publish)
    with pytest.raises(RuntimeError, match='preserve'):
        asyncio.run(client.download(HTTP(lambda: [b'new']), reference(b'new'), target))
    assert target.read_bytes() == b'someone retained this'


def test_64_mib_artifact_does_not_scale_python_heap_with_file_size(tmp_path):
    chunk = b'bounded-scientific-bytes\x00' * 2048
    count = 1400
    checksum = hashlib.sha256()
    for _ in range(count):
        checksum.update(chunk)
    ref = {'artifact_id': 'large', 'size_bytes': len(chunk) * count, 'sha256': checksum.hexdigest()}
    http = HTTP(lambda: itertools.repeat(chunk, count))
    tracemalloc.start()
    try:
        receipt = asyncio.run(client.download(http, ref, tmp_path / 'large'))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert receipt['size_bytes'] > 64 * 1024 * 1024
    assert peak < 8 * 1024 * 1024
