#!/usr/bin/env python3
"""Make an immutable reproducible GROMACS input archive from real local files."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile


def build(source: Path, output: Path):
    source, output = source.resolve(strict=True), output.absolute()
    if not source.is_dir() or output == source or source in output.resolve().parents:
        raise ValueError('The output must be outside the input directory.')
    files = sorted(source.rglob('*'))
    if any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in files):
        raise ValueError('Inputs must be regular files/directories, not symlinks or special files.')
    files = [path for path in files if path.is_file()]
    if not files or len(files) > 9998:
        raise ValueError('Expected 1–9998 input files.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as target:
        with gzip.GzipFile(fileobj=target, mode='wb', filename='', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for path in files:
                    info = tarfile.TarInfo(path.relative_to(source).as_posix())
                    info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                    with path.open('rb') as handle:
                        archive.addfile(info, handle)
    digest = hashlib.sha256()
    with output.open('rb') as handle:
        while chunk := handle.read(4 * 1024**2):
            digest.update(chunk)
    return {'path': str(output), 'sha256': digest.hexdigest(), 'size_bytes': output.stat().st_size,
            'files': len(files), 'media_type': 'application/x-tar', 'compression': 'gzip'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output)))
