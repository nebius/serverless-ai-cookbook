"""Verified JSON persistence on POSIX disks and object-storage bucket mounts.

The mounted customer bucket does not implement reliable rename/chmod semantics.
Receipts therefore have immutable journal records written before their convenient
canonical view. Resume always reads the latest journal, including after an
interrupted canonical write. An incomplete journal fails closed; it is never
silently skipped in favor of an older pre-admission state.

Within the dedicated owner instance, short local publication locks keep readers
out of an in-progress write. They do not make bucket writes atomic or coordinate
overlapping instances. The previous owner must be stopped before replacement.
"""
import json
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4

FILE_CHUNK_BYTES = 1024 * 1024


def file_measurement(path: Path) -> tuple[int, str]:
    """Hash a closed scientific file without loading it all into memory."""
    size, checksum = 0, hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(FILE_CHUNK_BYTES):
            size += len(chunk)
            checksum.update(chunk)
    return size, checksum.hexdigest()


def verify_file(path: Path, reference: dict) -> None:
    if file_measurement(path) != (reference['size_bytes'], reference['sha256']):
        raise RuntimeError('Existing artifact bytes differ from the declared result; preserve them and use a new recovery directory.')


def publish_file(staged: Path, target: Path, reference: dict) -> str:
    """Existing artifact publisher: exclusive streaming and verified readback.

    A local hard link is atomic. Bucket publication is an exclusive streamed
    copy, NOT atomically visible; a receipt is valid only after readback.
    """
    try:
        os.link(staged, target)
        return 'atomic-link'
    except FileExistsError:
        verify_file(target, reference)
        return 'verified-existing'
    except OSError as error:
        if error.errno not in {errno.EXDEV, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM, errno.ENOSYS}:
            raise
    created = False
    try:
        with open(target, 'xb', opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
            created = True
            with staged.open('rb') as source:
                while chunk := source.read(FILE_CHUNK_BYTES):
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        verify_file(target, reference)
        return 'verified-copy'
    except FileExistsError:
        verify_file(target, reference)
        return 'verified-existing'
    except BaseException as error:
        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(f'Partial artifact remains at {target}; cleanup failed: {cleanup_error}. No verified receipt was published.')
        raise


def persist_local_file(source: Path, target: Path) -> dict:
    """Publish a CLOSED local file; identical destinations resume, conflicts fail.

    Writers must be closed first. Use SQLite's backup API to a closed standalone
    file; copying a live database/WAL or arbitrary directory is not supported.
    """
    source, target = Path(source), Path(target)
    size, checksum = file_measurement(source)
    with source.open('rb') as stream:
        os.fsync(stream.fileno())
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    reference = {'size_bytes': size, 'sha256': checksum}
    publication = publish_file(source, target, reference)
    return {'path': str(target), **reference, 'publication': publication}


@dataclass
class StagedOutput:
    path: Path
    receipt: dict | None = None


@contextmanager
def staged_output(target: Path):
    """Yield a seekable local path; publish only after a successful closed writer.

    Example: ``with staged_output(target) as staged: np.savez(staged.path, x=x)``.
    After exit, ``staged.receipt`` contains exact persisted size/hash. Scratch
    is temporary, not durable. Close every library handle inside the block.
    """
    target = Path(target)
    with tempfile.TemporaryDirectory(prefix='scientific-output-') as folder:
        staged = StagedOutput(Path(folder) / target.name)
        yield staged
        staged.receipt = persist_local_file(staged.path, target)


def _local_lock_root() -> Path:
    root = Path(os.environ.get('SCIENTIFIC_RECEIPT_LOCK_DIR',
                str(Path(tempfile.gettempdir()) / f'scientific-receipt-locks-{os.geteuid()}')))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


@contextmanager
def receipt_lock(directory: Path):
    """Exclude competing clients in this container, without locking the bucket.

    Cross-container admission remains protected by the platform idempotency
    identity, not by an unsupported distributed filesystem-lock promise.
    """
    root = _local_lock_root()
    name = hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest() + '.lock'
    with open(root / name, 'w', opener=lambda path, flags: os.open(path, flags, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


@contextmanager
def _publication_lock(path: Path, *, writing: bool):
    """Synchronize a single save/load, not the long-running client operation.

    The API's observer child and the receipt worker inherit the same UID and
    local lock root in the supported dedicated-instance deployment. Keep this
    namespace distinct from receipt_lock, which a writer can hold for a whole
    stage. No lock files or rename assumptions are imposed on the bucket.
    Process exit releases the lock, but NEVER repairs/skips a partial journal.
    """
    name = 'publication-' + hashlib.sha256(str(path.resolve()).encode()).hexdigest() + '.lock'
    with open(_local_lock_root() / name, 'a+b',
              opener=lambda name, flags: os.open(name, flags, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if writing else fcntl.LOCK_SH)
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
    with _publication_lock(path, writing=True):
        if path.name == 'receipt.json':
            history = _journal(path)
            history.mkdir(parents=True, exist_ok=True, mode=0o700)
            previous = sorted(history.glob('*.json'))
            sequence = max(time.time_ns(), int(previous[-1].name.split('-', 1)[0]) + 1 if previous else 0)
            version = history / f'{sequence:020d}-{uuid4().hex}.json'
            _write_verified(version, data)
        _write_verified(path, data)


def save_analysis(path: Path, value: object) -> None:
    """Export measured scientific values without partial NumPy JSON writes.

    Analysis may contain NumPy scalars/arrays; protocol receipts keep their
    existing strict types. Serialize and validate the complete analysis before
    touching an existing file, then reuse the bucket-compatible readback path.
    Non-finite numbers are not silently converted into measurements.
    """
    import numpy as np

    def scientific_value(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f'Unsupported scientific JSON type: {type(item).__name__}')

    serialized = json.dumps(value, default=scientific_value, allow_nan=False)
    save(Path(path), json.loads(serialized))


def load(path: Path):
    """Return the latest verified receipt, or None only when no receipt exists."""
    path = Path(path)
    with _publication_lock(path, writing=False):
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
