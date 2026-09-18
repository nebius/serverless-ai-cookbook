"""Non-inference live check of the packaged receipt writers on mounted storage.

Run explicitly as an operator qualification check, never a scientific result.
Pass --helpers for staged candidate clients; the default checks installed ones.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helpers', type=Path, default=Path('/opt/bionemo'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.helpers))
    args.output.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='receipt-check-', dir=args.output))
    report = {'purpose': 'receipt storage qualification; zero model calls', 'directory': str(directory), 'writers': []}
    for source in ['invoke-native.py', 'upload-artifact.py', 'invoke-scientific-batch.py']:
        path = args.helpers / source
        if not path.exists() and source == 'invoke-scientific-batch.py':
            path = args.helpers / 'scientific-batch-acceptance.py'
        spec = importlib.util.spec_from_file_location('candidate_client', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = directory / source / 'receipt.json'
        first = {'state': 'prepared', 'qualification_only': True}
        resumed = {'state': 'accepted', 'operation_id': 'synthetic-storage-check-only'}
        module.save(target, first)
        assert json.loads(target.read_text()) == first
        module.save(target, resumed)
        assert json.loads(target.read_text()) == resumed
        assert module.load_receipt(target) == resumed
        target.write_bytes(b'')  # Simulate a disconnect during only the canonical view write.
        assert module.load_receipt(target) == resumed
        module.save(target, resumed)
        report['writers'].append({'source': str(path), 'path': str(target), 'create_read_update_read': 'passed',
                                  'interrupted_canonical_recovered_original_operation': True})
    from scientific_receipts import receipt_lock
    with receipt_lock(directory):
        try:
            with receipt_lock(directory):
                raise AssertionError('Receipt lock did not exclude the second writer')
        except BlockingIOError:
            report['same_container_receipt_lock'] = 'second writer blocked as expected'
    assert not list(directory.glob('*.tmp'))
    report['temporary_files_remaining'] = 0
    report_path = directory / 'report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    assert json.loads(report_path.read_text()) == report
    print(json.dumps({'status': 'passed', 'report': str(report_path), 'writers': len(report['writers']), 'model_calls': 0}))


if __name__ == '__main__':
    main()
