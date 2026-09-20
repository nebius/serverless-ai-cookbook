#!/usr/bin/env python3
"""Verify, install and package the same customer skills without extra dependencies."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
EXCLUDED = {'__pycache__', '.pytest_cache', '.git', 'dist'}


def manifest(root=ROOT):
    return json.loads((root / 'manifest.json').read_text())


def inventory(root=ROOT):
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if set(relative.parts) & EXCLUDED or relative.as_posix() == 'files.sha256.json':
            continue
        if path.is_symlink():
            raise ValueError(f'Bundle must be self-contained, not a symlink: {relative}')
        if path.is_file() and path.suffix != '.pyc':
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def validate(root=ROOT):
    data = manifest(root)
    actual = {p.parent.name for p in root.glob('*/SKILL.md')}
    if actual != set(data['skills']):
        raise ValueError(f'Skill/manifest mismatch: {actual ^ set(data["skills"])}')
    for name in sorted(actual):
        text = (root / name / 'SKILL.md').read_text()
        front = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        if not front or not re.search(rf'^name: {re.escape(name)}$', front[1], re.M):
            raise ValueError(f'Invalid skill name/frontmatter: {name}')
        if not re.search(r'^description: .+', front[1], re.M):
            raise ValueError(f'Missing skill description: {name}')
        if len(text.encode()) > 32768:
            raise ValueError(f'Move large examples to referenced files: {name}')
    return data


def verify(root=ROOT):
    data = validate(root)
    expected = json.loads((root / 'files.sha256.json').read_text())
    if inventory(root) != expected:
        raise ValueError('Bundle file inventory/hash mismatch; inspect changes before re-locking')
    return data


def check_catalog(catalog, root=ROOT):
    """A visible catalog can be a grant-limited subset, but not contain unmapped Apps."""
    visible = {row.get('id') or row.get('model_id') for row in catalog['models']}
    if not visible or None in visible:
        raise ValueError('Catalog is empty or lacks model identifiers')
    covered = {model for models in manifest(root)['skills'].values() for model in models}
    missing = visible - covered
    if missing:
        raise ValueError(f'Add workflow coverage before onboarding these Apps: {sorted(missing)}')
    return {'visible_apps': len(visible), 'covered_apps': len(covered), 'unmapped': []}


def install(destination, root=ROOT):
    data = verify(root)
    destination = Path(destination).expanduser().resolve()
    if destination == root or root in destination.parents:
        raise ValueError('Install destination must be outside the source bundle')
    # Preflight the entire operation; a late conflict must not partially install.
    metadata = ('NOTICE.md', 'LICENSE-APACHE', 'LICENSE-CC-BY-4.0', 'manifest.json')
    for name in metadata:
        target = destination / '.scientific-ai' / name
        if target.is_symlink() or (target.exists() and target.read_bytes() != (root / name).read_bytes()):
            raise ValueError('Existing release metadata differs; use a fresh versioned destination')
    for name in data['skills']:
        target = destination / name
        if target.is_symlink() or (target.exists() and (
                not target.is_dir() or inventory(target) != inventory(root / name))):
            raise ValueError(f'Existing skill differs; use a fresh versioned destination: {target}')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / '.scientific-ai').mkdir(exist_ok=True)
    for name in metadata:
        target = destination / '.scientific-ai' / name
        if not target.exists():
            shutil.copyfile(root / name, target)
    for name in data['skills']:
        target = destination / name
        if not target.exists():
            shutil.copytree(root / name, target, ignore=shutil.ignore_patterns(*EXCLUDED, '*.pyc'))
        if inventory(target) != inventory(root / name):
            raise RuntimeError(f'Installed hash mismatch: {name}')
    return {'version': data['version'], 'skills': len(data['skills']), 'destination': str(destination)}


def build(output, root=ROOT):
    data = verify(root)
    output = Path(output).resolve()
    if output == root or root in output.parents:
        raise ValueError('Release output must be outside source bundle')
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'scientific-ai-skills-{data["version"]}.tar.gz'
    # Fixed metadata and ordering make downloads byte-for-byte reproducible.
    with target.open('xb') as handle:
        with gzip.GzipFile(fileobj=handle, mode='wb', filename='', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name in sorted([*inventory(root), 'files.sha256.json']):
                    raw = (root / name).read_bytes()
                    info = tarfile.TarInfo(f'scientific-ai/{name}')
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    archive.addfile(info, io.BytesIO(raw))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with (output / 'SHA256SUMS').open('x') as handle:
        handle.write(f'{digest}  {target.name}\n')
    return {'archive': str(target), 'sha256': digest}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest='command', required=True)
    sub.add_parser('verify')
    sub.add_parser('lock')
    sub.add_parser('install').add_argument('--dest', type=Path, required=True)
    sub.add_parser('build').add_argument('--output', type=Path, required=True)
    sub.add_parser('check-catalog').add_argument('--url', default=manifest()['catalog_url'])
    args = cli.parse_args()
    if args.command == 'lock':
        validate()
        (ROOT / 'files.sha256.json').write_text(json.dumps(inventory(), indent=2) + '\n')
        result = {'locked': len(inventory())}
    elif args.command == 'install':
        result = install(args.dest)
    elif args.command == 'build':
        result = build(args.output)
    elif args.command == 'check-catalog':
        with urlopen(args.url, timeout=20) as response:
            result = check_catalog(json.load(response))
    else:
        data = verify()
        result = {'version': data['version'], 'skills': len(data['skills']), 'verified': True}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
