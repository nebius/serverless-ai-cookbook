#!/usr/bin/env python3
"""Shared, receipt-safe primitives for deterministic recording workflows."""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from urllib.parse import urlencode
import zipfile

from scientific_receipts import load, save, staged_output


ARTIFACT_FIELDS = ('artifact_id', 'sha256', 'size_bytes', 'media_type', 'compression')
TERMINAL_FAILURES = {'failed', 'cancelled', 'expired', 'preempted'}
WORKSPACE_ROOT = Path('/workspace')


def file_identity(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


def workspace_url(path: Path, *, root: Path = WORKSPACE_ROOT) -> str:
    """Build the authenticated, origin-relative Workspace deep link for a file."""
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError('Workspace links are only valid for files under /workspace.') from error
    if not relative.parts or relative.name in ('', '.', '..'):
        raise ValueError('Workspace link must select a file below /workspace.')
    relative_name = relative.as_posix()
    parent = relative.parent.as_posix()
    return '/demos?' + urlencode({
        'tab': 'workspace',
        'path': '' if parent == '.' else parent,
        'file': relative_name,
    })


def workspace_urls(**paths: Path | None) -> dict[str, str]:
    """Return production workspace links while keeping temporary-directory tests portable."""
    links = {}
    for name, path in paths.items():
        if path is None:
            continue
        try:
            links[name] = workspace_url(path)
        except ValueError:
            continue
    return links


def execute(command: list[str], runner=subprocess.run):
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 75):
        raise RuntimeError(
            f'Pipeline stage failed with exit code {completed.returncode}; inspect its retained receipt.'
        )
    return completed


def helper_command(name: str) -> list[str]:
    return [str(Path(sys.executable)), str(Path(__file__).resolve().parent / name)]


def verified_artifact_reference(path: Path, source: Path, media_types: tuple[str, ...]) -> dict:
    value = load(path)
    if not isinstance(value, dict) or any(field not in value for field in ARTIFACT_FIELDS):
        raise ValueError('Finalized source artifact is missing required fields.')
    reference = {field: value[field] for field in ARTIFACT_FIELDS}
    identity = file_identity(source)
    if (reference['sha256'], reference['size_bytes']) != (identity['sha256'], identity['size_bytes']):
        raise ValueError('Finalized artifact differs from the source bytes.')
    if reference['media_type'] not in media_types or reference['compression'] != 'none':
        raise ValueError('Finalized artifact has the wrong media contract.')
    return reference


def upload_source(*, source: Path, model: str, media_type: str, directory: Path,
                  idempotency_key: str, runner=subprocess.run):
    completed = execute(helper_command('upload-artifact.py') + [
        '--model', model, '--file', str(source), '--media-type', media_type,
        '--output-dir', str(directory), '--idempotency-key', idempotency_key,
    ], runner)
    if completed.returncode == 75:
        return None, 75
    return verified_artifact_reference(directory / 'artifact.json', source, (media_type,)), 0


def immutable_input(path: Path, payload: dict) -> None:
    existing = load(path)
    if existing is not None and existing != payload:
        raise ValueError('Saved model input differs; use a new output directory.')
    save(path, payload)


def invoke(*, model: str, tool: str, input_path: Path, directory: Path,
           idempotency_key: str, wait_seconds: int, recover_only: bool,
           runner=subprocess.run):
    command = helper_command('invoke-native.py') + [
        '--model', model, '--tool', tool, '--input', str(input_path),
        '--output-dir', str(directory), '--idempotency-key', idempotency_key,
        '--wait-seconds', str(wait_seconds),
    ]
    if recover_only:
        command.append('--recover-only')
    completed = execute(command, runner)
    receipt = load(directory / 'receipt.json') or {}
    if completed.returncode == 75:
        return {'state': receipt.get('state', 'pending'),
                'operation_id': receipt.get('operation_id')}, 75
    if receipt.get('state') in TERMINAL_FAILURES:
        raise RuntimeError(f"Model operation ended in {receipt['state']}; inspect the retained operation.")
    if receipt.get('state') != 'succeeded':
        raise RuntimeError('Native client returned zero without a succeeded receipt.')
    return receipt, 0


def unwrap(value):
    for _ in range(4):
        if not isinstance(value, dict):
            break
        if isinstance(value.get('structuredContent'), dict):
            value = value['structuredContent']
        elif isinstance(value.get('result'), dict) and set(value) <= {'operation', 'result'}:
            value = value['result']
        else:
            break
    if not isinstance(value, dict):
        raise ValueError('Model result must be an object.')
    return value


def operation_metadata(path: Path) -> dict:
    value = load(path) or {}
    if isinstance(value, dict) and isinstance(value.get('structuredContent'), dict):
        value = value['structuredContent']
    return value if isinstance(value, dict) else {}


def elapsed_seconds(operation: dict):
    start, end = operation.get('accepted_at'), operation.get('completed_at')
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    return (datetime.fromisoformat(end.replace('Z', '+00:00'))
            - datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds()


def timing(operation: dict) -> dict:
    return {'accepted_at': operation.get('accepted_at'),
            'completed_at': operation.get('completed_at'),
            'elapsed_seconds': elapsed_seconds(operation)}


def native_file(result_path: Path, expected_media_type: str) -> Path:
    value = load(result_path)
    if not isinstance(value, dict) or value.get('schema') != 'scientific-native-file/v1':
        raise ValueError('Completed native result is not a retained file.')
    if value.get('content_type') != expected_media_type:
        raise ValueError('Completed native file has the wrong media type.')
    reference = value.get('file')
    if not isinstance(reference, dict) or not isinstance(reference.get('path'), str):
        raise ValueError('Completed native result has no verified file reference.')
    path = Path(reference['path'])
    if path.parent.resolve() != result_path.parent.resolve() or not path.name.startswith('result.'):
        raise ValueError('Completed native media must remain inside its operation directory.')
    if file_identity(path) != {key: reference[key] for key in ('sha256', 'size_bytes')}:
        raise ValueError('Completed native result differs from its saved receipt.')
    return path


def publish_bytes(path: Path, data: bytes):
    with staged_output(path) as staged:
        staged.path.write_bytes(data)
    return staged.receipt


def publish_copy(source: Path, destination: Path):
    with staged_output(destination) as staged:
        with source.open('rb') as reader, staged.path.open('wb') as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
    return staged.receipt


def extract_verified_zip(source: Path, destination: Path, *, required: tuple[str, ...],
                         max_entries: int = 4096, max_uncompressed_bytes: int = 2_147_483_648) -> dict:
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipts = {}
    total = 0
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > max_entries:
            raise ValueError('Result ZIP has an invalid entry count.')
        names = {item.filename for item in infos}
        if any(name not in names for name in required):
            raise ValueError('Result ZIP is missing a required artifact.')
        for info in infos:
            path = Path(info.filename)
            mode = info.external_attr >> 16
            if (not info.filename or path.is_absolute() or '..' in path.parts
                    or stat.S_ISLNK(mode) or info.is_dir()):
                if info.is_dir() and not (path.is_absolute() or '..' in path.parts):
                    continue
                raise ValueError('Result ZIP contains an unsafe entry.')
            total += info.file_size
            if total > max_uncompressed_bytes:
                raise ValueError('Result ZIP exceeds the extraction limit.')
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with staged_output(target) as staged, archive.open(info) as reader, staged.path.open('wb') as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
            receipts[info.filename] = staged.receipt
    return receipts
