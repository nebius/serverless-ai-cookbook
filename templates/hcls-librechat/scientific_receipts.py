"""Verified JSON persistence on POSIX disks and object-storage bucket mounts.

The mounted customer bucket does not implement reliable rename/chmod semantics.
Receipts therefore have immutable journal records written before their convenient
canonical view. Resume always reads the latest journal, including after an
interrupted canonical write. An incomplete journal fails closed; it is never
silently skipped in favor of an older pre-admission state.
"""
import json
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4


@contextmanager
def receipt_lock(directory: Path):
    """Exclude competing clients in this container, without locking the bucket.

    Cross-container admission remains protected by the platform idempotency
    identity, not by an unsupported distributed filesystem-lock promise.
    """
    root = Path(os.environ.get('SCIENTIFIC_RECEIPT_LOCK_DIR',
                str(Path(tempfile.gettempdir()) / f'scientific-receipt-locks-{os.geteuid()}')))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest() + '.lock'
    with open(root / name, 'w', opener=lambda path, flags: os.open(path, flags, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _write_verified(path: Path, data: bytes) -> None:
    with open(path, 'wb', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    # No retry or inference follows a failed durability check. Retain the files
    # for diagnosis instead of hiding a mount error behind a claimed success.
    if path.read_bytes() != data:
        raise OSError(f'JSON storage readback differs: {path}; retained evidence requires inspection.')


def _journal(path: Path) -> Path:
    return path.parent / '.receipt-history' / path.name


def save(path: Path, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = (json.dumps(value, indent=2) + '\n').encode('utf-8')
    if path.name == 'receipt.json':
        history = _journal(path)
        history.mkdir(parents=True, exist_ok=True, mode=0o700)
        previous = sorted(history.glob('*.json'))
        sequence = max(time.time_ns(), int(previous[-1].name.split('-', 1)[0]) + 1 if previous else 0)
        version = history / f'{sequence:020d}-{uuid4().hex}.json'
        _write_verified(version, data)
    _write_verified(path, data)


def load(path: Path):
    """Return the latest verified receipt, or None only when no receipt exists."""
    path = Path(path)
    versions = sorted(_journal(path).glob('*.json'))
    source = versions[-1] if versions else path
    if not versions and not source.exists():
        return None
    try:
        value = json.loads(source.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('Receipt must be a JSON object')
        return value
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Latest receipt is unreadable: {source}. Admission may be unknown; '
                           'do not submit a new request. Inspect the retained receipt history.') from error
