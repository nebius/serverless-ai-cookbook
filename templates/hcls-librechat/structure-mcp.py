#!/usr/bin/env python3
"""Read-only bridge from authorized gateway operation results to sandboxed 3D UI.

No model submission, arbitrary URL/path access, shared disk artifacts, or browser
credentials. Coordinates travel server-to-UI, not back through the LLM context.
"""
import importlib.util
import hashlib
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
    def fetch(path):
        request = urllib.request.Request(f'{base}{path}',
                                         headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Result exceeds the 4 MiB viewer limit. Use the scientific artifact workflow outside this viewer.')
        return raw

    try:
        result = json.loads(fetch(f'/operations/{operation_id}/result'))
        if isinstance(result, dict) and isinstance(result.get('operation'), dict):
            if result['operation'].get('id') != operation_id:
                raise ValueError('Platform returned a mismatched operation result.')
            result = result.get('result')
        if not isinstance(result, dict) or result.get('schema') != 'fs2-serve.nebius.ai/operation-artifact-result/v1':
            return result
        artifact = result.get('artifact') or {}
        if (not isinstance(artifact, dict) or result.get('content_type') != 'application/json'
                or artifact.get('compression') != 'none'
                or type(artifact.get('size_bytes')) is not int
                or not 0 <= artifact['size_bytes'] <= MAX_BYTES
                or not isinstance(artifact.get('sha256'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', artifact['sha256'])):
            raise ValueError('This result artifact is not bounded, uncompressed JSON supported by the viewer.')
        try:
            artifact_id = str(uuid.UUID(artifact.get('artifact_id')))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Platform returned an invalid result artifact identity.') from None
        # Resolve only platform-issued artifact IDs through the configured gateway.
        # No URL from the payload is followed and credentials never go to object storage.
        raw = fetch(f'/artifacts/{artifact_id}/content')
        if len(raw) != artifact['size_bytes'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
            raise ValueError('Result artifact failed size or SHA-256 verification; no coordinates were displayed.')
        return json.loads(raw)
    except urllib.error.HTTPError as error:
        raise ValueError(f'Could not retrieve result (HTTP {error.code}). Check access, completion and retention; no work was submitted.') from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('Could not read the scientific result. Check the existing operation; no work was submitted.') from None


def structure_format(text):
    if re.search(r'^(ATOM  |HETATM).{24,}', text, re.M):
        return 'pdb'
    if '_atom_site.Cartn_x' in text or '_atom_site.cartn_x' in text:
        return 'cif'
    if re.search(r'V[23]000\s*$', text, re.M) and 'M  END' in text:
        return 'sdf'
    return None


def has_plddt_evidence(value, depth=0):
    """Recognize explicit model pLDDT evidence, not generic confidence."""
    if depth > 12:
        return False
    if isinstance(value, dict):
        for name, child in value.items():
            if name.lower() in {'plddt', 'plddt_mean', 'plddt_score', 'complex_plddt_score'}:
                if isinstance(child, (int, float)) and not isinstance(child, bool):
                    return True
                if isinstance(child, list) and child and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in child):
                    return True
            if isinstance(child, (dict, list)) and has_plddt_evidence(child, depth + 1):
                return True
    elif isinstance(value, list):
        return any(has_plddt_evidence(item, depth + 1) for item in value)
    return False


def collect_structures(value):
    entries, seen = [], set()
    plddt_evidence = has_plddt_evidence(value)

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
                entry = {'text': item, 'format': fmt, 'label': f'{kind} {number}', 'source': path[:140]}
                if plddt_evidence and kind == 'Protein structure':
                    entry['color_by'] = 'plddt-b-factor'
                entries.append(entry)
        elif isinstance(item, dict):
            for name, child in item.items():
                walk(child, f'{path}.{name}', depth + 1)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f'{path}[{index}]', depth + 1)
    walk(value)
    return entries


TOOL = {'name': 'visualize_structure',
        'description': 'Show an interactive protein/molecule viewer in chat: fullscreen, rotation, zoom and representations. For one completed folding/docking operation, pass operation_id. For a synchronized comparison, pass operations with two to four operation IDs and labels; the viewer can overlay all returned coordinates in one camera or inspect them separately. When the same verified result contains explicit pLDDT evidence, protein coordinates offer true pLDDT B-factor coloring with a visible legend; otherwise the viewer does not claim confidence coloring. Coordinates are fetched with the configured gateway key without copying them through the LLM. Supports PDB/mmCIF/SDF inside inline or verified native JSON result artifacts up to 4 MiB per operation (not batch artifact lists or SMILES-only results). Does not submit compute. Include the returned UI resource marker verbatim in your response.',
        'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False},
        'inputSchema': {'type': 'object', 'additionalProperties': False,
                        'properties': {'operation_id': {'type': 'string', 'format': 'uuid'},
                                       'operations': {'type': 'array', 'minItems': 2, 'maxItems': 4,
                                                      'description': 'Completed operations to compare in one synchronized viewer. Labels should be the exact model names.',
                                                      'items': {'type': 'object', 'additionalProperties': False,
                                                                'properties': {'operation_id': {'type': 'string', 'format': 'uuid'},
                                                                               'label': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                                                                'required': ['operation_id', 'label']}},
                                       'title': {'type': 'string', 'maxLength': 160},
                                       'structure_text': {'type': 'string', 'maxLength': 65536,
                                                          'description': 'Only for a small structure supplied directly by the user. Prefer operation_id for model results.'}},
                        'description': 'Provide exactly one of operation_id, operations, or structure_text.'}}


def call_viewer(args):
    if not isinstance(args, dict) or set(args) - {'operation_id', 'operations', 'structure_text', 'title'}:
        raise ValueError('Unsupported viewer arguments.')
    sources = [name for name in ('operation_id', 'operations', 'structure_text') if name in args]
    if len(sources) != 1:
        raise ValueError('Provide exactly one of operation_id, operations, or structure_text.')
    title = args.get('title', 'Scientific structure')
    if not isinstance(title, str) or len(title) > 160:
        raise ValueError('Title must be text, at most 160 characters.')
    operation = None
    operations = []
    if 'operation_id' in args:
        try:
            operation = str(uuid.UUID(args['operation_id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Use the operation UUID returned by the gateway.') from None
        data = get_result(operation)
        entries = collect_structures(data)
    elif 'operations' in args:
        requested = args['operations']
        if (not isinstance(requested, list) or not 2 <= len(requested) <= 4
                or any(not isinstance(item, dict) or set(item) != {'operation_id', 'label'} for item in requested)):
            raise ValueError('operations must contain two to four exact operation_id and label objects.')
        identifiers = []
        entries = []
        for item in requested:
            try:
                identifier = str(uuid.UUID(item['operation_id']))
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Every comparison operation needs a gateway operation UUID.') from None
            label = item['label']
            if not isinstance(label, str) or not label.strip() or len(label) > 100:
                raise ValueError('Every comparison operation needs a nonempty model label of at most 100 characters.')
            if identifier in identifiers:
                raise ValueError('Comparison operation IDs must be unique.')
            identifiers.append(identifier)
            found = collect_structures(get_result(identifier))
            for entry in found:
                entry = dict(entry)
                entry['label'] = f'{label.strip()} · {entry["label"]}'
                entry['source'] = f'operation:{identifier}.{entry["source"]}'
                entries.append(entry)
        operations = identifiers
    else:
        data = args['structure_text']
        if not isinstance(data, str) or not 1 <= len(data.encode('utf-8')) <= 65536:
            raise ValueError('Inline structures must be between 1 and 65536 bytes.')
        entries = collect_structures(data)
    if not entries:
        raise ValueError('No inline PDB/mmCIF/SDF coordinates found. Batch artifact references, sequences and SMILES alone cannot be rendered. No coordinates were invented.')
    if len(entries) > MAX_STRUCTURES:
        raise ValueError(f'Comparison returned more than the supported {MAX_STRUCTURES} coordinate structures.')
    first = entries[0]
    resource_id = f'structure{uuid.uuid4().hex}'
    label = f'{title} · {operation}' if operation else title
    source_summary = operation or (f'{len(operations)} completed operations' if operations else 'user-supplied coordinates')
    return {'content': [
        {'type': 'text', 'text': f'Interactive viewer prepared with {len(entries)} structure(s) from {source_summary}. Include the supplied UI resource marker verbatim in the answer. Multi-operation mode provides one synchronized overlay camera and separate structure views. The viewer does not align structures or validate scientific quality.'},
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
