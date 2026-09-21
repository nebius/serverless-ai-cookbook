#!/usr/bin/env python3
"""Read-only bridge from verified scientific results/files to sandboxed UI.

No model submission, arbitrary URL/path access, or browser credentials.
Coordinates and media travel server-to-UI, not back through the LLM context.
"""
import base64
import importlib.util
import hashlib
import html
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
MAX_WORKSPACE_STRUCTURES = 4
# A 45-second, 48 kHz stereo PCM16 WAV is about 8.3 MiB. Keep the viewer
# bounded while allowing the recording-ready soundtrack and similarly sized
# scientific clips to render without forcing users through a download-only
# fallback.
MAX_MEDIA_BYTES = 12 * 1024 * 1024
MAX_MEDIA_TOTAL_BYTES = 24 * 1024 * 1024
MAX_MEDIA_FILES = 4
ASSETS = Path(os.environ.get('BIONEMO_ASSET_ROOT', '/opt/bionemo'))
WORKSPACE = Path(os.environ.get('SCIENTIFIC_WORKSPACE', '/workspace')).resolve()
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


def workspace_file(path, max_bytes):
    """Resolve one regular file without permitting an escape from /workspace."""
    if not isinstance(path, str) or not path.strip() or '\x00' in path:
        raise ValueError('Workspace path must be nonempty text.')
    supplied = Path(path)
    candidate = supplied if supplied.is_absolute() else WORKSPACE / supplied
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError):
        raise ValueError('Workspace file does not exist or cannot be resolved.') from None
    if resolved != WORKSPACE and WORKSPACE not in resolved.parents:
        raise ValueError('Workspace file must remain under the configured /workspace root.')
    if not resolved.is_file():
        raise ValueError('Workspace path must name a regular file.')
    try:
        size = resolved.stat().st_size
    except OSError:
        raise ValueError('Workspace file cannot be inspected.') from None
    if size > max_bytes:
        raise ValueError(f'Workspace file exceeds the {max_bytes // (1024 * 1024)} MiB inline-view limit.')
    return resolved, size


def workspace_structures(requested):
    if (not isinstance(requested, list) or not 1 <= len(requested) <= MAX_WORKSPACE_STRUCTURES
            or any(not isinstance(item, dict) or set(item) != {'path', 'label'} for item in requested)):
        raise ValueError('workspace_files must contain one to four exact path and label objects.')
    entries = []
    resolved_paths = set()
    for item in requested:
        label = item['label']
        if not isinstance(label, str) or not label.strip() or len(label) > 100:
            raise ValueError('Every workspace structure needs a nonempty label of at most 100 characters.')
        path, _ = workspace_file(item['path'], MAX_BYTES)
        if path in resolved_paths:
            raise ValueError('Workspace structure paths must be unique.')
        resolved_paths.add(path)
        try:
            raw = path.read_bytes()
            text = raw.decode('utf-8')
        except (OSError, UnicodeDecodeError):
            raise ValueError('Workspace structures must be readable UTF-8 text.') from None
        fmt = structure_format(text)
        if not fmt:
            raise ValueError('Workspace structure is not recognized PDB, mmCIF or SDF coordinates.')
        if fmt == 'cif':
            normalised = viewer.normalise_mmcif_for_viewer(text)
            if normalised != text:
                text, fmt = normalised, 'pdb'
        entries.append({'text': text, 'format': fmt, 'label': label.strip(),
                        'source': f'workspace:{path.relative_to(WORKSPACE)}'})
    return entries


MEDIA_TYPES = {
    '.png': ('image/png', 'image'),
    '.jpg': ('image/jpeg', 'image'), '.jpeg': ('image/jpeg', 'image'),
    '.webp': ('image/webp', 'image'), '.gif': ('image/gif', 'image'),
    '.mp4': ('video/mp4', 'video'), '.webm': ('video/webm', 'video'),
    '.wav': ('audio/wav', 'audio'), '.mp3': ('audio/mpeg', 'audio'),
    '.ogg': ('audio/ogg', 'audio'), '.flac': ('audio/flac', 'audio'),
}


def media_signature(data, suffix):
    return {
        '.png': data.startswith(b'\x89PNG\r\n\x1a\n'),
        '.jpg': data.startswith(b'\xff\xd8\xff'), '.jpeg': data.startswith(b'\xff\xd8\xff'),
        '.webp': len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP',
        '.gif': data.startswith((b'GIF87a', b'GIF89a')),
        '.mp4': len(data) >= 12 and data[4:8] == b'ftyp',
        '.webm': data.startswith(b'\x1aE\xdf\xa3'),
        '.wav': len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE',
        '.mp3': data.startswith(b'ID3') or (len(data) >= 2 and data[0] == 0xff and data[1] & 0xe0 == 0xe0),
        '.ogg': data.startswith(b'OggS'),
        '.flac': data.startswith(b'fLaC'),
    }.get(suffix, False)


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
        'description': 'Show an interactive PDB/mmCIF/SDF protein or molecule viewer in chat. For one completed folding/docking operation pass only operation_id and optional title. To overlay a prepared receptor from /workspace with a completed docking operation, pass operation_id plus workspace_files:[{path,label}]. Use operations for two to four completed operation IDs, or workspace_files alone for verified local structures. Never pass model_id, kind, image, audio or video fields. The viewer supports fullscreen, rotation, zoom and representations. It does not submit compute. Include its returned UI resource marker verbatim.',
        'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False},
        'inputSchema': {'type': 'object', 'additionalProperties': False,
                        'properties': {'operation_id': {'type': 'string', 'format': 'uuid'},
                                       'operations': {'type': 'array', 'minItems': 2, 'maxItems': 4,
                                                      'description': 'Completed operations to compare in one synchronized viewer. Labels should be the exact model names.',
                                                      'items': {'type': 'object', 'additionalProperties': False,
                                                                'properties': {'operation_id': {'type': 'string', 'format': 'uuid'},
                                                                               'label': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                                                                'required': ['operation_id', 'label']}},
                                       'workspace_files': {'type': 'array', 'minItems': 1, 'maxItems': 4,
                                                           'description': 'PDB/mmCIF/SDF files under /workspace. May be used alone or with one operation_id for receptor/ligand overlay.',
                                                           'items': {'type': 'object', 'additionalProperties': False,
                                                                     'properties': {'path': {'type': 'string', 'minLength': 1},
                                                                                    'label': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                                                                     'required': ['path', 'label']}},
                                       'title': {'type': 'string', 'maxLength': 160},
                                       'structure_text': {'type': 'string', 'maxLength': 65536,
                                                          'description': 'Only for a small structure supplied directly by the user. Prefer operation_id for model results.'}},
                        'description': 'Provide operation_id, operations, structure_text, or workspace_files. Only operation_id may be combined with workspace_files.'}}


def call_viewer(args):
    if not isinstance(args, dict) or set(args) - {'operation_id', 'operations', 'structure_text', 'workspace_files', 'title'}:
        raise ValueError('Unsupported viewer arguments.')
    sources = [name for name in ('operation_id', 'operations', 'structure_text') if name in args]
    has_workspace = 'workspace_files' in args
    if len(sources) > 1 or (not sources and not has_workspace):
        raise ValueError('Provide operation_id, operations, structure_text, or workspace_files; only operation_id can be combined with workspace_files.')
    if has_workspace and sources and sources[0] != 'operation_id':
        raise ValueError('Only operation_id can be combined with workspace_files.')
    title = args.get('title', 'Scientific structure')
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise ValueError('Title must be text, at most 160 characters.')
    operation = None
    operations = []
    entries = workspace_structures(args['workspace_files']) if has_workspace else []
    if 'operation_id' in args:
        try:
            operation = str(uuid.UUID(args['operation_id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Use the operation UUID returned by the gateway.') from None
        data = get_result(operation)
        found = collect_structures(data)
        for entry in found:
            entry = dict(entry)
            entry['source'] = f'operation:{operation}.{entry["source"]}'
            entries.append(entry)
    elif 'operations' in args:
        requested = args['operations']
        if (not isinstance(requested, list) or not 2 <= len(requested) <= 4
                or any(not isinstance(item, dict) or set(item) != {'operation_id', 'label'} for item in requested)):
            raise ValueError('operations must contain two to four exact operation_id and label objects.')
        identifiers = []
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
        if 'structure_text' in args:
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
    label = f'{title.strip()} · {operation}' if operation else title.strip()
    if operation and has_workspace:
        source_summary = f'completed operation {operation} plus {len(args["workspace_files"])} workspace structure(s)'
    else:
        source_summary = operation or (f'{len(operations)} completed operations' if operations
                                       else f'{len(args.get("workspace_files", []))} workspace structure(s)'
                                       if has_workspace else 'user-supplied coordinates')
    return {'content': [
        {'type': 'text', 'text': f'Interactive viewer prepared with {len(entries)} structure(s) from {source_summary}. Include the supplied UI resource marker verbatim in the answer. Multi-operation mode provides one synchronized overlay camera and separate structure views. The viewer does not align structures or validate scientific quality.'},
        {'type': 'resource', 'resource': {'uri': f'ui://scientific/structure/{resource_id}',
         'mimeType': 'text/html', 'text': viewer.viewer_html(first['text'], first['format'], label, entries)}}]}


MEDIA_TOOL = {'name': 'visualize_workspace_media',
              'description': 'Display verified image, video or audio files already stored under /workspace in an inline gallery. Use this for PNG/JPEG/WebP/GIF, MP4/WebM, WAV/MP3/OGG/FLAC; never use visualize_structure for those formats. Pass only files:[{path,label}] and optional title. Files are read locally, signature-checked and bounded; no URL is fetched and no compute is submitted. Include the returned UI resource marker verbatim.',
              'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False},
              'inputSchema': {'type': 'object', 'additionalProperties': False,
                              'properties': {'files': {'type': 'array', 'minItems': 1, 'maxItems': MAX_MEDIA_FILES,
                                                       'items': {'type': 'object', 'additionalProperties': False,
                                                                 'properties': {'path': {'type': 'string', 'minLength': 1},
                                                                                'label': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                                                                 'required': ['path', 'label']}},
                                             'title': {'type': 'string', 'maxLength': 160}},
                              'required': ['files']}}


def media_html(title, items):
    cards = []
    for item in items:
        label = html.escape(item['label'])
        source = f'data:{item["mime"]};base64,{item["data"]}'
        if item['kind'] == 'image':
            element = f'<img src="{source}" alt="{label}" loading="eager">'
        elif item['kind'] == 'video':
            element = f'<video src="{source}" controls preload="metadata" aria-label="{label}"></video>'
        else:
            element = f'<audio src="{source}" controls preload="metadata" aria-label="{label}"></audio>'
        cards.append(f'<figure><div class="stage">{element}</div><figcaption>{label}</figcaption></figure>')
    safe_title = html.escape(title)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title><style>
:root{{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:#f2f5f2;color:#052b42}}.panel{{border:1px solid #d8dfda;border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 3px 14px #052b4212}}header{{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid #e5ebe7}}h1{{font-size:15px;line-height:1.3;margin:0;flex:1}}button{{border:1px solid #b8c5bc;border-radius:7px;background:#e0ff4f;color:#052b42;padding:6px 10px;font:inherit;cursor:pointer}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:12px;padding:12px}}figure{{margin:0;border:1px solid #dfe6e1;border-radius:9px;overflow:hidden;background:#f8faf8}}.stage{{min-height:180px;display:flex;align-items:center;justify-content:center;background:#071d28}}img,video{{display:block;width:100%;max-height:520px;object-fit:contain}}audio{{width:calc(100% - 24px);margin:54px 12px}}figcaption{{padding:9px 11px;font-size:13px;overflow-wrap:anywhere}}footer{{padding:8px 12px;border-top:1px solid #e5ebe7;color:#53655a;font-size:12px}}html:fullscreen body,.panel{{min-height:100%}}html:fullscreen .panel{{border:0;border-radius:0}}@media(max-width:560px){{main{{grid-template-columns:1fr}}}}
</style></head><body><section class="panel" data-viewer-ready="true"><header><h1>{safe_title}</h1><button id="fullscreen" type="button">Full screen</button></header><main>{''.join(cards)}</main><footer>Verified files from this workspace · scientific outputs require domain review</footer></section><script>
const button=document.getElementById('fullscreen');button.addEventListener('click',async()=>{{try{{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}}catch{{}}}});document.addEventListener('fullscreenchange',()=>button.textContent=document.fullscreenElement?'Exit full screen':'Full screen');function reportHeight(){{window.parent.postMessage({{type:'ui-size-change',payload:{{height:Math.ceil(document.querySelector('.panel').scrollHeight)}}}},'*')}}requestAnimationFrame(reportHeight);new ResizeObserver(reportHeight).observe(document.querySelector('.panel'));
</script></body></html>'''


def call_media_viewer(args):
    if not isinstance(args, dict) or set(args) - {'files', 'title'}:
        raise ValueError('Unsupported media viewer arguments.')
    requested = args.get('files')
    if (not isinstance(requested, list) or not 1 <= len(requested) <= MAX_MEDIA_FILES
            or any(not isinstance(item, dict) or set(item) != {'path', 'label'} for item in requested)):
        raise ValueError('files must contain one to four exact path and label objects.')
    title = args.get('title', 'Scientific media')
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise ValueError('Title must be nonempty text, at most 160 characters.')
    items, total, paths = [], 0, set()
    for requested_item in requested:
        label = requested_item['label']
        if not isinstance(label, str) or not label.strip() or len(label) > 100:
            raise ValueError('Every media file needs a nonempty label of at most 100 characters.')
        path, size = workspace_file(requested_item['path'], MAX_MEDIA_BYTES)
        if path in paths:
            raise ValueError('Workspace media paths must be unique.')
        paths.add(path)
        suffix = path.suffix.lower()
        if suffix not in MEDIA_TYPES:
            raise ValueError('Unsupported workspace media type. Use PNG/JPEG/WebP/GIF, MP4/WebM, WAV/MP3/OGG/FLAC.')
        total += size
        if total > MAX_MEDIA_TOTAL_BYTES:
            raise ValueError(
                f'Selected workspace media exceeds the '
                f'{MAX_MEDIA_TOTAL_BYTES // (1024 * 1024)} MiB combined inline-view limit.'
            )
        try:
            data = path.read_bytes()
        except OSError:
            raise ValueError('Workspace media file cannot be read.') from None
        if len(data) != size or not media_signature(data, suffix):
            raise ValueError('Workspace media content does not match its supported file type.')
        mime, kind = MEDIA_TYPES[suffix]
        items.append({'label': label.strip(), 'mime': mime, 'kind': kind,
                      'data': base64.b64encode(data).decode('ascii')})
    resource_id = f'media{uuid.uuid4().hex}'
    return {'content': [
        {'type': 'text', 'text': f'Inline media viewer prepared with {len(items)} verified workspace file(s). Include the supplied UI resource marker verbatim in the answer. Files larger than the bounded viewer limit remain downloadable through Workspace.'},
        {'type': 'resource', 'resource': {'uri': f'ui://scientific/media/{resource_id}',
         'mimeType': 'text/html', 'text': media_html(title.strip(), items)}}]}


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
                          'serverInfo': {'name': 'scientific-viewers', 'version': '4.0'}}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': [TOOL, MEDIA_TOOL]}
            elif method == 'tools/call' and request.get('params', {}).get('name') == TOOL['name']:
                try:
                    result = call_viewer(request['params'].get('arguments', {}))
                except ValueError as error:
                    result = {'isError': True, 'content': [{'type': 'text', 'text': str(error)}]}
            elif method == 'tools/call' and request.get('params', {}).get('name') == MEDIA_TOOL['name']:
                try:
                    result = call_media_viewer(request['params'].get('arguments', {}))
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
