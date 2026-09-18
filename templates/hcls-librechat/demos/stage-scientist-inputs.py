"""Stage frozen public study inputs through the authenticated customer workspace.

This prepares data only: no model requests, platform key mutation, or inference.
The agent receives provenance and real local files, not a scripted tool sequence.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--workbenches', type=Path, required=True)
    parser.add_argument('--scientist', required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--case-id', action='append', required=True)
    parser.add_argument('--include-input-data', action='store_true')
    parser.add_argument('--include-reference-files', action='store_true',
                        help='Stage frozen provenance files and explicit reference transcripts for independent analysis, not model input.')
    parser.add_argument('--reference-root', action='append', type=Path, default=[],
                        help='Additional explicit root for provenance files referenced by the frozen manifest; checksums are still required to match.')
    parser.add_argument('--extra-file', action='append', type=Path, default=[],
                        help='Supplementary public source or reference file, copied under supplementary/.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index-name', default='study-sources.json')
    parser.add_argument('--input-directory', default='study-inputs',
                        help='Workspace-relative directory below the selected scientist, for versioned input sets.')
    args = parser.parse_args()
    if Path(args.index_name).name != args.index_name or not args.index_name.endswith('.json'):
        parser.error('Use a plain JSON filename for the source index.')
    if Path(args.input_directory).is_absolute() or '..' in Path(args.input_directory).parts:
        parser.error('Use a relative input directory without parent traversal.')
    os.umask(0o077)
    person = next(p for p in json.loads(args.manifest.read_text())['scientists'] if p['id'] == args.scientist)
    deployment = json.loads((args.workbenches / args.scientist / 'deployment.json').read_text())
    for field in ('principal_id', 'tenant_id', 'bucket_name', 'email'):
        if person[field] != deployment[field]:
            raise ValueError('Deployment identity does not match selected scientist: ' + field)
    data = json.loads(args.cases.read_text())
    selected = {case['case_id']: case for case in data['cases'] if case['case_id'] in args.case_id}
    if set(selected) != set(args.case_id):
        raise ValueError('A requested frozen case is missing')
    prefix = f'{args.scientist}/{args.input_directory}'
    receipt = {'scientist_id': args.scientist, 'source_manifest': str(args.cases), 'files': [], 'studies': []}
    with httpx.Client(base_url=deployment['url'], timeout=120) as client:
        login = client.post('/api/auth/login', json={'email': person['email'], 'password': person['password']})
        login.raise_for_status()
        client.headers['authorization'] = 'Bearer ' + login.json()['token']

        def put(relative, content, content_type):
            existing = client.get('/api/scientific-demos/workspace/file', params={'path': relative})
            if existing.status_code == 200:
                if existing.content != content:
                    raise ValueError('Existing workspace file differs; choose a new path: ' + relative)
            else:
                if existing.status_code != 404:
                    existing.raise_for_status()
                response = client.post('/api/scientific-demos/workspace', data={'path': relative},
                    files={'file': (Path(relative).name, io.BytesIO(content), content_type)})
                # A simultaneous identical staged write can be reused only after readback.
                if response.status_code != 409:
                    response.raise_for_status()
            digest = hashlib.sha256(content).hexdigest()
            downloaded = client.get('/api/scientific-demos/workspace/file', params={'path': relative})
            downloaded.raise_for_status()
            if downloaded.content != content:
                raise ValueError('Workspace readback differs from staged bytes: ' + relative)
            receipt['files'].append({'workspace_file': '/workspace/' + relative,
                                     'size_bytes': len(content), 'sha256': digest})

        staged = set()
        for case in selected.values():
            study = {'case_id': case['case_id'], 'model_id': case['model_id'],
                     'provenance': case.get('provenance'), 'files': []}
            preparation = case.get('preparation') or {}
            for entry in preparation.get('inputs', []) + preparation.get('artifact_fields', []):
                relative = Path(entry['local_path'])
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Frozen input must be relative to its dataset manifest')
                content = (args.cases.parent / relative).read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                if entry.get('sha256') and digest != entry['sha256']:
                    raise ValueError('Frozen input digest differs: ' + str(relative))
                target = prefix + '/' + relative.as_posix()
                if target not in staged:
                    put(target, content, entry.get('media_type', 'application/octet-stream'))
                    staged.add(target)
                study['files'].append({**entry, 'workspace_file': '/workspace/' + target})
            if args.include_input_data:
                target = prefix + '/' + case['case_id'] + '.json'
                put(target, json.dumps(case['arguments'], indent=2).encode(), 'application/json')
                study['input_data_file'] = '/workspace/' + target
            if args.include_reference_files:
                study['reference_files'] = []
                provenance = case.get('provenance') or {}
                for entry in provenance.get('sources', []) + provenance.get('files', []):
                    if not entry.get('path'):
                        continue
                    relative = Path(entry['path'])
                    if relative.is_absolute() or '..' in relative.parts:
                        raise ValueError('Frozen reference must remain relative to the dataset manifest')
                    reference = next((root / relative for root in [args.cases.parent, *args.reference_root]
                                      if (root / relative).is_file()), args.cases.parent / relative)
                    content = reference.read_bytes()
                    if entry.get('sha256') and hashlib.sha256(content).hexdigest() != entry['sha256']:
                        raise ValueError('Frozen reference digest differs: ' + str(relative))
                    target = prefix + '/' + relative.as_posix()
                    if target not in staged:
                        put(target, content, 'application/octet-stream')
                        staged.add(target)
                    study['reference_files'].append({**entry, 'workspace_file': '/workspace/' + target})
                reference_text = (case.get('expected') or {}).get('reference_text')
                if isinstance(reference_text, str):
                    target = prefix + '/references/' + case['case_id'] + '.reference.txt'
                    put(target, reference_text.encode(), 'text/plain')
                    study['reference_files'].append({'workspace_file': '/workspace/' + target,
                        'purpose': 'Frozen dataset reference transcript; preserve the documented alignment limitations.'})
            receipt['studies'].append(study)
        for source in args.extra_file:
            if not source.is_file():
                raise ValueError('Supplementary source file is missing: ' + str(source))
            target = prefix + '/supplementary/' + source.name
            if target in staged:
                raise ValueError('Duplicate supplementary basename: ' + source.name)
            put(target, source.read_bytes(), 'application/octet-stream')
            staged.add(target)
            receipt['studies'].append({'supplementary_source': source.name, 'workspace_file': '/workspace/' + target})
        index = prefix + '/' + args.index_name
        put(index, json.dumps(receipt['studies'], indent=2).encode(), 'application/json')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'scientist_id': args.scientist, 'verified_files': len(receipt['files']),
                      'workspace_index': '/workspace/' + index, 'receipt': str(args.output)}))


if __name__ == '__main__':
    main()
