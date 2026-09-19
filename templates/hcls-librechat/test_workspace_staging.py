"""Seek-dependent scientific formats publish complete, verified bucket files."""
import errno
import hashlib
from pathlib import Path
import sqlite3
import zipfile

import h5py
import numpy as np
import pytest

import scientific_receipts as storage


@pytest.fixture
def bucket_copy(monkeypatch):
    def unsupported(*args):
        raise OSError(errno.EXDEV, 'cross-device bucket link')
    monkeypatch.setattr(storage.os, 'link', unsupported)


@pytest.mark.parametrize('kind', ['npz', 'zip', 'h5', 'sqlite'])
def test_closed_scientific_format_roundtrip(tmp_path, bucket_copy, kind):
    target = tmp_path / 'bucket' / ('results.' + kind)
    values = np.asarray([[1.25, 2.5], [3.75, 5.0]], dtype=np.float64)
    with storage.staged_output(target) as staged:
        assert staged.path.name == target.name and staged.path.parent != target.parent
        assert staged.receipt is None and not target.exists()
        if kind == 'npz':
            np.savez(staged.path, values=values)
        elif kind == 'zip':
            with zipfile.ZipFile(staged.path, 'w') as archive:
                archive.writestr('measurements.txt', 'retained scientific bytes')
        elif kind == 'h5':
            with h5py.File(staged.path, 'w') as archive:
                archive.create_dataset('values', data=values)
        else:
            source = sqlite3.connect(':memory:')
            source.execute('CREATE TABLE measurements (value REAL)')
            source.executemany('INSERT INTO measurements VALUES (?)', [(1.25,), (5.0,)])
            source.commit()
            destination = sqlite3.connect(staged.path)
            source.backup(destination)
            destination.close()
            source.close()
        expected = staged.path.read_bytes()
    assert target.read_bytes() == expected and not staged.path.exists()
    assert staged.receipt == {'path': str(target), 'size_bytes': len(expected),
                              'sha256': hashlib.sha256(expected).hexdigest(),
                              'publication': 'verified-copy'}
    if kind == 'npz':
        with np.load(target) as result:
            np.testing.assert_array_equal(result['values'], values)
    elif kind == 'zip':
        with zipfile.ZipFile(target) as result:
            assert result.read('measurements.txt') == b'retained scientific bytes'
    elif kind == 'h5':
        with h5py.File(target, 'r') as result:
            np.testing.assert_array_equal(result['values'][:], values)
    else:
        with sqlite3.connect(f'file:{target}?mode=ro', uri=True) as result:
            assert result.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert result.execute('SELECT value FROM measurements').fetchall() == [(1.25,), (5.0,)]


def test_writer_exception_never_publishes(tmp_path):
    target = tmp_path / 'bucket' / 'failed.npz'
    with pytest.raises(RuntimeError, match='writer failed'):
        with storage.staged_output(target) as staged:
            staged.path.write_bytes(b'partial')
            raise RuntimeError('writer failed')
    assert not target.exists() and staged.receipt is None and not staged.path.exists()


def test_missing_closed_file_does_not_publish(tmp_path):
    target = tmp_path / 'bucket' / 'missing.h5'
    with pytest.raises(FileNotFoundError):
        with storage.staged_output(target) as staged:
            pass
    assert not target.exists() and staged.receipt is None


def test_existing_output_preserved_and_identical_resume(tmp_path, bucket_copy):
    target = tmp_path / 'measurement.bin'
    target.write_bytes(b'original')
    with pytest.raises(RuntimeError, match='preserve'):
        with storage.staged_output(target) as conflict:
            conflict.path.write_bytes(b'changed')
    assert target.read_bytes() == b'original' and conflict.receipt is None
    with storage.staged_output(target) as resumed:
        resumed.path.write_bytes(b'original')
    assert resumed.receipt['publication'] == 'verified-existing'


def test_streamed_publication_does_not_require_read_bytes(tmp_path, monkeypatch, bucket_copy):
    local = tmp_path / 'local.bin'
    local.write_bytes(b'x' * (2 * storage.FILE_CHUNK_BYTES + 17))
    monkeypatch.setattr(Path, 'read_bytes', lambda *args: (_ for _ in ()).throw(AssertionError('whole-file read')))
    receipt = storage.persist_local_file(local, tmp_path / 'bucket' / 'large.bin')
    assert receipt['size_bytes'] == 2 * storage.FILE_CHUNK_BYTES + 17
    assert receipt['publication'] == 'verified-copy'
