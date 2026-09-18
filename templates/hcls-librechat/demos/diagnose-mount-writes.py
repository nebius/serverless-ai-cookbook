"""Qualification-only bounded write/flush/rename probe; performs no model calls."""
import argparse
import json
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='mount-probe-', dir=args.output))
    results = []
    for method in ['mkstemp', 'mkstemp-fsync', 'writeonly', 'writeonly-fsync', 'direct', 'path-temp']:
        target = root / (method + '.json')
        payload = json.dumps({'method': method, 'value': 'retained-write-probe'}) + '\n'
        record = {'method': method}
        try:
            if method == 'direct':
                target.write_text(payload)
            elif method == 'path-temp':
                temporary = target.with_suffix('.tmp')
                temporary.write_text(payload)
                record['before_rename'] = temporary.read_text() == payload
                temporary.replace(target)
            else:
                if method.startswith('mkstemp'):
                    descriptor, name = tempfile.mkstemp(dir=root, prefix=method)
                    temporary = Path(name)
                else:
                    temporary = target.with_suffix('.tmp')
                    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'w') as stream:
                    stream.write(payload)
                    if method.endswith('fsync'):
                        stream.flush()
                        os.fsync(stream.fileno())
                record['before_rename'] = temporary.read_text() == payload
                temporary.replace(target)
            record['immediate_readback'] = target.read_text() == payload
            record['observed_bytes'] = target.stat().st_size
        except Exception as error:
            record['error'] = type(error).__name__ + ': ' + str(error)
        results.append(record)
    report = {'directory': str(root), 'results': results, 'model_calls': 0}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
