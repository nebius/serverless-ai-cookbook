#!/usr/bin/env python3
"""Exercise seekable output publication on an actual mounted workspace.

Place the candidate scientific_receipts.py beside this fixture, or expose the
installed helper on PYTHONPATH. No network, inference, or credential access.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

import h5py
import numpy as np

from scientific_receipts import file_measurement, save, staged_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    if list(root.iterdir()):
        raise RuntimeError('Use a new empty qualification output directory')
    x = np.arange(24, dtype=np.float64).reshape(6, 4)
    receipts = []
    with staged_output(root / 'array.npz') as staged:
        np.savez(staged.path, values=x)
    receipts.append(staged.receipt)
    with np.load(root / 'array.npz') as loaded:
        np.testing.assert_array_equal(loaded['values'], x)
    with staged_output(root / 'archive.zip') as staged:
        with zipfile.ZipFile(staged.path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('sample.txt', 'closed and hash-verified\n')
    receipts.append(staged.receipt)
    with zipfile.ZipFile(root / 'archive.zip') as archive:
        assert archive.read('sample.txt') == b'closed and hash-verified\n'
    with staged_output(root / 'array.h5') as staged:
        with h5py.File(staged.path, 'w') as hdf:
            hdf.create_dataset('values', data=x)
    receipts.append(staged.receipt)
    with h5py.File(root / 'array.h5', 'r') as hdf:
        np.testing.assert_array_equal(hdf['values'][:], x)
    with tempfile.TemporaryDirectory(prefix='qualification-sqlite-') as temporary:
        live = sqlite3.connect(Path(temporary) / 'source.sqlite')
        try:
            live.execute('PRAGMA journal_mode=WAL')
            live.execute('CREATE TABLE measurements (sample INTEGER, value REAL)')
            live.executemany('INSERT INTO measurements VALUES (?, ?)', [(i, float(i) / 2) for i in range(8)])
            live.commit()
            with staged_output(root / 'backup.sqlite') as staged:
                backup = sqlite3.connect(staged.path)
                try:
                    live.backup(backup)
                finally:
                    backup.close()
            receipts.append(staged.receipt)
        finally:
            live.close()
    # Readers of SQLite use a closed local copy: no shared WAL/POSIX guarantee.
    with tempfile.TemporaryDirectory(prefix='qualification-sqlite-read-') as temporary:
        copy = Path(temporary) / 'snapshot.sqlite'
        copy.write_bytes((root / 'backup.sqlite').read_bytes())
        with sqlite3.connect(copy) as database:
            assert database.execute('SELECT * FROM measurements ORDER BY sample').fetchall() == [(i, i / 2) for i in range(8)]
    try:
        with staged_output(root / 'failed-writer.bin') as staged:
            staged.path.write_bytes(b'incomplete')
            raise RuntimeError('expected writer failure')
    except RuntimeError as error:
        assert str(error) == 'expected writer failure'
    assert not (root / 'failed-writer.bin').exists()
    with staged_output(root / 'conflict.bin') as staged:
        staged.path.write_bytes(b'original')
    original = file_measurement(root / 'conflict.bin')
    conflict_preserved = False
    try:
        with staged_output(root / 'conflict.bin') as staged:
            staged.path.write_bytes(b'different')
    except RuntimeError:
        conflict_preserved = file_measurement(root / 'conflict.bin') == original
    assert conflict_preserved
    with staged_output(root / 'conflict.bin') as staged:
        staged.path.write_bytes(b'original')
    assert staged.receipt['publication'] == 'verified-existing'
    receipts.append(staged.receipt)
    summary = {'schema': 'workspace-staging-qualification/v1', 'passed': True,
               'formats': ['numpy-npz', 'zip', 'hdf5', 'closed-sqlite-backup'],
               'files': receipts, 'writer_exception_did_not_publish': True,
               'conflict_preserved_existing': True, 'identical_resume_verified': True,
               'shared_posix_or_live_sqlite_guarantee': False}
    save(root / 'summary.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
