#!/usr/bin/env python3
"""Read-only bridge from authorized gateway operation results to sandboxed 3D UI.

No model submission, arbitrary URL/path access, shared disk artifacts, or browser
credentials. Coordinates travel server-to-UI, not back through the LLM context.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import uuid

MAX_BYTES = 4 * 1024 * 1024
MAX_STRUCTURES = 20
ASSETS = Path(os.environ.get('BIONEMO_ASSET_ROOT', '/opt/bionemo'))
spec = importlib.util.spec_from_file_location('scientific_viewer', ASSETS / 'viewer-mcp.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_result(operation_id):
    key = os.environ.get('SCIENTIFIC_MODELS_API_KEY', '')
    if not key or key.startswith(('${', '{{')):
        raise ValueError('Structure viewer is not connected. Configure your scientific platform key for this viewer.')
    base = os.environ.get('SCIENTIFIC_MODELS_API_BASE_URL', '').rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('The viewer requires an operator-configured HTTPS scientific gateway.')
    request = urllib.request.Request(f'{base}/operations/{operation_id}/result',
                                     headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Result exceeds the 4 MiB inline viewer limit. Use the scientific artifact workflow outside this viewer.')
        return json.loads(raw)
    except urllib.error.HTTPError as error:
        raise ValueError(f'Could not retrieve result (HTTP {error.code}). Check access, completion and retention; no work was submitted.') from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise ValueError('Could not read the scientific result. Check the existing operation; no work was submitted.') from None


def structure_format(text):
    if re.search(r'^(ATOM  |HETATM).{24,}', text, re.M):
        return 'pdb'
    if '_atom_site.Cartn_x' in text or '_atom_site.cartn_x' in text:
        return 'cif'
    if re.search(r'V[23]000\s*$', text, re.M) and 'M  END' in text:
        return 'sdf'
    return None


def collect_structures(value):
    entries, seen = [], set()

    def walk(item, path='result', depth=0):
        if depth > 12 or len(entries) >= MAX_STRUCTURES:
            return
        if isinstance(item, str):
            fmt = structure_format(item)
            if fmt and item not in seen:
                seen.add(item)
                if fmt == 'cif':
                    normalised = viewer.normalise_mmcif_for_viewer(item)
                    if normalised != item:
                        item, fmt = normalised, 'pdb'
                kind = 'Docking pose' if 'ligand_positions' in path else 'Molecule' if fmt == 'sdf' else 'Protein structure'
                number = 1 + sum(entry['label'].startswith(kind) for entry in entries)
                entries.append({'text': item, 'format': fmt, 'label': f'{kind} {number}', 'source': path[:140]})
        elif isinstance(item, dict):
            for name, child in item.items():
                walk(child, f'{path}.{name}', depth + 1)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f'{path}[{index}]', depth + 1)
    walk(value)
    return entries


TOOL = {'name': 'visualize_structure',
        'description': 'Show an interactive protein/molecule viewer in chat: fullscreen, rotation, zoom and representations. For a completed folding/docking operation, pass its operation_id: coordinates are fetched with the configured gateway key without copying them through the LLM. Supports inline PDB/mmCIF/SDF results (not batch artifact references or SMILES-only results). Does not submit compute. Include the returned UI resource marker verbatim in your response.',
        'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False},
        'inputSchema': {'type': 'object', 'additionalProperties': False,
                        'properties': {'operation_id': {'type': 'string', 'format': 'uuid'},
                                       'title': {'type': 'string', 'maxLength': 160},
                                       'structure_text': {'type': 'string', 'maxLength': 65536,
                                                          'description': 'Only for a small structure supplied directly by the user. Prefer operation_id for model results.'}},
                        'description': 'Provide exactly one of operation_id or structure_text.'}}


def call_viewer(args):
    if not isinstance(args, dict) or set(args) - {'operation_id', 'structure_text', 'title'}:
        raise ValueError('Unsupported viewer arguments.')
    if ('operation_id' in args) == ('structure_text' in args):
        raise ValueError('Provide exactly one of operation_id or structure_text.')
    title = args.get('title', 'Scientific structure')
    if not isinstance(title, str) or len(title) > 160:
        raise ValueError('Title must be text, at most 160 characters.')
    operation = None
    if 'operation_id' in args:
        try:
            operation = str(uuid.UUID(args['operation_id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Use the operation UUID returned by the gateway.') from None
        data = get_result(operation)
    else:
        data = args['structure_text']
        if not isinstance(data, str) or not 1 <= len(data.encode('utf-8')) <= 65536:
            raise ValueError('Inline structures must be between 1 and 65536 bytes.')
    entries = collect_structures(data)
    if not entries:
        raise ValueError('No inline PDB/mmCIF/SDF coordinates found. Batch artifact references, sequences and SMILES alone cannot be rendered. No coordinates were invented.')
    first = entries[0]
    resource_id = f'structure{uuid.uuid4().hex}'
    label = f'{title} · {operation}' if operation else title
    return {'content': [
        {'type': 'text', 'text': f'Interactive viewer prepared with {len(entries)} structure(s). Operation: {operation or "user-supplied coordinates"}. Include the supplied UI resource marker verbatim in the answer. The viewer does not validate scientific quality.'},
        {'type': 'resource', 'resource': {'uri': f'ui://scientific/structure/{resource_id}',
         'mimeType': 'text/html', 'text': viewer.viewer_html(first['text'], first['format'], label, entries)}}]}


def main():
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError('Expected a JSON-RPC object.')
            if 'id' not in request:
                continue
            request_id, method = request['id'], request.get('method')
            if method == 'initialize':
                result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'structure-viewer', 'version': '3.0'}}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': [TOOL]}
            elif method == 'tools/call' and request.get('params', {}).get('name') == TOOL['name']:
                try:
                    result = call_viewer(request['params'].get('arguments', {}))
                except ValueError as error:
                    result = {'isError': True, 'content': [{'type': 'text', 'text': str(error)}]}
            else:
                raise ValueError('Unknown method or tool.')
            viewer.send({'jsonrpc': '2.0', 'id': request_id, 'result': result})
        except Exception:
            viewer.send({'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                         'error': {'code': -32602, 'message': 'Invalid viewer request or unavailable viewer. No work was submitted.'}})


if __name__ == '__main__':
    main()
