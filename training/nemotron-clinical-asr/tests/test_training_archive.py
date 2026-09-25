import hashlib
import io
import tarfile

import pytest

from clinical_asr.cloud_train import extract_verified_archive


def archive(path, name, data=b'not-real-audio', symlink=False):
    with tarfile.open(path, 'w') as target:
        entry = tarfile.TarInfo(name)
        entry.size = len(data)
        if symlink:
            entry.type = tarfile.SYMTYPE
            entry.linkname = '/etc/passwd'
            entry.size = 0
        target.addfile(entry, None if symlink else io.BytesIO(data))


def test_exact_declared_bytes_required(tmp_path):
    source = tmp_path / 'data.tar'
    data = b'exact audited bytes'
    archive(source, 'audio/id.wav', data)
    expected = {'audio/id.wav': {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}
    assert extract_verified_archive(source, tmp_path / 'dest', expected) == 1
    assert (tmp_path / 'dest/audio/id.wav').read_bytes() == data
    expected['audio/id.wav']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='sha256'):
        extract_verified_archive(source, tmp_path / 'wrong', expected)


@pytest.mark.parametrize('name,link', [('../escape', False), ('/etc/passwd', False), ('audio/id.wav', True)])
def test_archive_traversal_and_links_rejected(tmp_path, name, link):
    source = tmp_path / 'data.tar'
    archive(source, name, symlink=link)
    with pytest.raises(ValueError):
        extract_verified_archive(source, tmp_path / 'dest', {})
