"""Receipts must work on the customer bucket mount, not just a POSIX disk."""
import importlib.util
import json
from pathlib import Path
import stat

import pytest


ROOT = Path(__file__).parent


@pytest.fixture(params=['invoke-native.py', 'upload-artifact.py', 'scripts/scientific-batch-acceptance.py'])
def writer(request):
    spec = importlib.util.spec_from_file_location('receipt_client', ROOT / request.param)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.save


def test_receipt_create_and_resume_do_not_require_chmod(writer, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise PermissionError('Bucket mount does not support chmod')
    monkeypatch.setattr(Path, 'chmod', forbidden)
    monkeypatch.setattr(Path, 'replace', forbidden)
    target = tmp_path / 'receipt.json'
    writer(target, {'state': 'prepared'})
    assert json.loads(target.read_text()) == {'state': 'prepared'}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    writer(target, {'state': 'accepted', 'operation_id': 'retained-operation'})
    assert json.loads(target.read_text())['operation_id'] == 'retained-operation'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert len(list((tmp_path / '.receipt-history/receipt.json').glob('*.json'))) == 2


def test_interrupted_canonical_write_recovers_latest_admission(writer, tmp_path, monkeypatch):
    import scientific_receipts
    target = tmp_path / 'receipt.json'
    writer(target, {'state': 'prepared'})
    original = scientific_receipts._write_verified
    def failed_canonical(path, data):
        if path == target:
            path.write_bytes(b'')
            raise OSError('Object storage unavailable')
        return original(path, data)
    monkeypatch.setattr(scientific_receipts, '_write_verified', failed_canonical)
    with pytest.raises(OSError, match='storage unavailable'):
        writer(target, {'state': 'accepted', 'operation_id': 'retained-operation'})
    assert scientific_receipts.load(target)['operation_id'] == 'retained-operation'


def test_incomplete_latest_journal_is_never_replaced_with_pre_admission_state(writer, tmp_path):
    import scientific_receipts
    target = tmp_path / 'receipt.json'
    writer(target, {'state': 'prepared'})
    history = tmp_path / '.receipt-history/receipt.json'
    (history / '99999999999999999999-interrupted.json').write_text('{"state":')
    with pytest.raises(RuntimeError, match='Admission may be unknown'):
        scientific_receipts.load(target)


def test_legacy_receipt_without_journal_remains_resumable(tmp_path):
    from scientific_receipts import load
    target = tmp_path / 'receipt.json'
    assert load(target) is None
    target.write_text('{"operation_id":"old-operation","state":"running"}')
    assert load(target)['operation_id'] == 'old-operation'


def test_client_lock_is_local_and_excludes_same_receipt_only(tmp_path, monkeypatch):
    from scientific_receipts import receipt_lock
    root = tmp_path / 'local-locks'
    monkeypatch.setenv('SCIENTIFIC_RECEIPT_LOCK_DIR', str(root))
    with receipt_lock(tmp_path / 'bucket/run-1'):
        with pytest.raises(BlockingIOError):
            with receipt_lock(tmp_path / 'bucket/run-1'):
                pytest.fail('Second writer must not start')
        with receipt_lock(tmp_path / 'bucket/run-2'):
            pass
    assert not (tmp_path / 'bucket').exists()
    with receipt_lock(tmp_path / 'bucket/run-1'):
        pass
