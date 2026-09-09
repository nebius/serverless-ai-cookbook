#!/usr/bin/env python3
"""Keep large BioNeMo MCP artifacts out of the language-model tool stream."""

import base64
import hashlib
import json
import mimetypes
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request


ARTIFACT_ROOT = pathlib.Path(os.environ.get('BIONEMO_ARTIFACT_ROOT', '/workspace/shared/bionemo-artifacts')).resolve()
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
CHUNK_BYTES = 24 * 1024
UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
ID_RE = re.compile(r'^[0-9a-f]{32}$')
SAFE_NAME = re.compile(r'[^A-Za-z0-9._-]+')
rpc_id = 0


def send(payload):
    print(json.dumps(payload), flush=True)


def rpc_error(request_id, message):
    send({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32000, 'message': message}})


def tool(name, description, schema):
    return {'name': name, 'description': description, 'inputSchema': schema}


TOOLS = [
    tool(
        'bionemo_artifact_download',
        'Download one BioNeMo MCP artifact to the local workbench without placing its contents in the chat. Use this for PDB/mmCIF structure artifacts, then call protein_viewer with the returned structure_path.',
        {
            'type': 'object',
            'properties': {
                'job_id': {'type': 'string', 'description': 'The exact 32-character job ID returned by BioNeMo MCP.'},
                'artifact_id': {'type': 'string', 'description': 'The exact 32-character artifact ID from job_status.'},
                'filename_hint': {'type': 'string', 'description': 'Optional safe display filename, for example boltz2.cif.'},
            },
            'required': ['job_id', 'artifact_id'],
        },
    ),
    tool(
        'bionemo_json_summary',
        'Fetch a JSON BioNeMo artifact inside the instance and return only compact confidence, affinity, ranking, and timing values. Never use clawbio_model_fetch for a response JSON artifact.',
        {
            'type': 'object',
            'properties': {
                'job_id': {'type': 'string', 'description': 'The exact 32-character job ID returned by BioNeMo MCP.'},
                'artifact_id': {'type': 'string', 'description': 'The exact 32-character JSON artifact ID from job_status.'},
            },
            'required': ['job_id', 'artifact_id'],
        },
    ),
    tool(
        'bionemo_upload_local_file',
        'Stream a file already present on this Serverless instance into the tenant-scoped BioNeMo upload service. Use this instead of clawbio_input_stage_local: the hosted gateway intentionally cannot read this instance’s filesystem. The returned job_id and artifact_id can be used as an InputReference in a typed BioNeMo model tool.',
        {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'Absolute path to a regular local file. Files in /workspace/shared are retained in the mounted bucket.'},
                'purpose': {'type': 'string', 'enum': ['protein_structure', 'microscopy_image', 'single_cell_anndata', 'genomics_reference', 'genomics_reads', 'genomics_index']},
                'media_type': {'type': 'string', 'description': 'Optional MIME type. A valid default is selected from the filename and upload purpose when omitted.'},
                'idempotency_key': {'type': 'string', 'description': 'Optional 16–128 character idempotency key. Omit to derive a stable key from the file digest and purpose.'},
            },
            'required': ['path', 'purpose'],
        },
    ),
]


def validate_id(value, label):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ValueError(f'{label} must be a 32-character lowercase hexadecimal ID')
    return value


def result_value(message):
    if not isinstance(message, dict):
        raise ValueError('BioNeMo MCP returned an invalid JSON-RPC response')
    if message.get('error'):
        raise ValueError(f"BioNeMo MCP error: {message['error'].get('message', 'unknown error')}")
    result = message.get('result')
    if not isinstance(result, dict):
        raise ValueError('BioNeMo MCP returned no tool result')
    if result.get('isError'):
        content = result.get('content') or []
        detail = next((item.get('text') for item in content if isinstance(item, dict) and isinstance(item.get('text'), str)), 'tool failed')
        raise ValueError(f'BioNeMo MCP tool failed: {detail}')
    structured = result.get('structuredContent')
    if isinstance(structured, dict):
        return structured.get('result', structured)
    for item in result.get('content') or []:
        if isinstance(item, dict) and item.get('type') == 'text' and isinstance(item.get('text'), str):
            try:
                return json.loads(item['text'])
            except json.JSONDecodeError:
                return item['text']
    raise ValueError('BioNeMo MCP returned no readable tool content')


def upstream_tool(name, arguments):
    global rpc_id
    url = os.environ.get('BIONEMO_MCP_URL', '')
    key = os.environ.get('BIONEMO_MCP_API_KEY', '')
    if not url.startswith('https://') or not key:
        raise ValueError('BioNeMo MCP is not configured for artifact relay')
    rpc_id += 1
    payload = json.dumps({
        'jsonrpc': '2.0', 'id': f'artifact-{rpc_id}', 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }).encode('utf-8')
    request = urllib.request.Request(
        url, data=payload, method='POST',
        headers={
            'Accept': 'application/json, text/event-stream',
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'MCP-Protocol-Version': '2025-06-18',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read(MAX_ARTIFACT_BYTES + 262144)
    except urllib.error.HTTPError as error:
        raise ValueError(f'BioNeMo MCP returned HTTP {error.code}') from error
    except urllib.error.URLError as error:
        raise ValueError(f'BioNeMo MCP is unreachable: {error.reason}') from error
    if len(body) > MAX_ARTIFACT_BYTES + 262144:
        raise ValueError('BioNeMo MCP response exceeded the relay limit')
    try:
        return result_value(json.loads(body.decode('utf-8')))
    except json.JSONDecodeError as error:
        raise ValueError('BioNeMo MCP returned invalid JSON') from error


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(UPLOAD_CHUNK_BYTES), b''):
            digest.update(chunk)
    return digest.hexdigest()


def default_media_type(path, purpose):
    suffix = path.suffix.lower()
    if suffix in {'.pdb', '.ent'}:
        return 'chemical/x-pdb'
    if suffix in {'.cif', '.mmcif'}:
        return 'chemical/x-mmcif'
    if suffix in {'.fasta', '.fa', '.fna', '.fq', '.fastq', '.txt'}:
        return 'text/plain'
    if suffix in {'.h5', '.h5ad'}:
        return 'application/x-hdf5'
    if suffix == '.bam':
        return 'application/x-bam'
    if suffix == '.cram':
        return 'application/x-cram'
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and purpose == 'microscopy_image':
        return guessed
    return 'application/octet-stream'


def upload_base_url():
    url = os.environ.get('BIONEMO_MCP_URL', '').rstrip('/')
    if not url.startswith('https://') or not url.endswith('/mcp'):
        raise ValueError('BioNeMo MCP upload service is not configured')
    return url[:-4]


def upload_local_file(arguments):
    raw_path = arguments.get('path')
    purpose = arguments.get('purpose')
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError('path must be a non-empty string')
    if purpose not in {'protein_structure', 'microscopy_image', 'single_cell_anndata', 'genomics_reference', 'genomics_reads', 'genomics_index'}:
        raise ValueError('purpose must be one of the supported BioNeMo upload purposes')
    path = pathlib.Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError('path must identify a readable regular file on this instance')
    size_bytes = path.stat().st_size
    if size_bytes < 1:
        raise ValueError('path must not be empty')
    sha256 = file_sha256(path)
    media_type = arguments.get('media_type') or default_media_type(path, purpose)
    if not isinstance(media_type, str):
        raise ValueError('media_type must be a string when provided')
    idempotency_key = arguments.get('idempotency_key') or f'local-upload-{purpose}-{sha256[:40]}'
    if not isinstance(idempotency_key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{15,127}', idempotency_key):
        raise ValueError('idempotency_key must contain 16–128 safe characters')
    session = upstream_tool('clawbio_upload_create', {
        'purpose': purpose,
        'filename': path.name,
        'media_type': media_type,
        'size_bytes': size_bytes,
        'sha256': sha256,
        'idempotency_key': idempotency_key,
    })
    if not isinstance(session, dict):
        raise ValueError('BioNeMo MCP returned an invalid upload session')
    upload_path = session.get('upload_path')
    upload_id = session.get('upload_id')
    offset = session.get('offset_bytes')
    if not isinstance(upload_path, str) or not upload_path.startswith('/upload/v1/') or not isinstance(upload_id, str) or not isinstance(offset, int):
        raise ValueError('BioNeMo MCP upload session is incomplete')
    state = session.get('state')
    artifact_id = session.get('artifact_id')
    job_id = session.get('job_id')
    if state not in {'ready', 'created', 'uploading'}:
        raise ValueError(f'BioNeMo MCP upload is {state or "unavailable"}')
    if state != 'ready':
        key = os.environ.get('BIONEMO_MCP_API_KEY', '')
        if not key:
            raise ValueError('BioNeMo MCP upload credentials are unavailable')
        with path.open('rb') as handle:
            handle.seek(offset)
            while offset < size_bytes:
                chunk = handle.read(min(UPLOAD_CHUNK_BYTES, size_bytes - offset))
                if not chunk:
                    raise ValueError('local file changed while it was being uploaded')
                request = urllib.request.Request(
                    upload_base_url() + upload_path,
                    data=chunk,
                    method='PATCH',
                    headers={
                        'Authorization': f'Bearer {key}',
                        'Content-Type': 'application/offset+octet-stream',
                        'Content-Length': str(len(chunk)),
                        'Upload-Offset': str(offset),
                        'Upload-Chunk-SHA256': hashlib.sha256(chunk).hexdigest(),
                    },
                )
                try:
                    with urllib.request.urlopen(request, timeout=300) as response:
                        next_offset = response.headers.get('Upload-Offset')
                        state = response.headers.get('Upload-State', state)
                        artifact_id = response.headers.get('Upload-Artifact-ID', artifact_id)
                        job_id = response.headers.get('Upload-Job-ID', job_id)
                except urllib.error.HTTPError as error:
                    raise ValueError(f'BioNeMo upload failed with HTTP {error.code}') from error
                if next_offset is None or not next_offset.isdigit() or int(next_offset) != offset + len(chunk):
                    raise ValueError('BioNeMo upload returned an invalid offset')
                offset = int(next_offset)
    if state != 'ready' or not isinstance(artifact_id, str) or not isinstance(job_id, str):
        raise ValueError('BioNeMo upload did not finalize successfully')
    return {
        'path': str(path), 'bytes': size_bytes, 'sha256': sha256,
        'upload_id': upload_id, 'job_id': job_id, 'artifact_id': artifact_id,
        'state': state, 'purpose': purpose, 'media_type': media_type,
    }


def fetch_artifact(job_id, artifact_id):
    metadata = upstream_tool('clawbio_model_fetch', {
        'job_id': job_id, 'artifact_id': artifact_id, 'representation': 'metadata', 'offset': 0, 'length': 1,
    })
    if not isinstance(metadata, dict):
        raise ValueError('BioNeMo MCP returned malformed artifact metadata')
    total = metadata.get('bytes')
    checksum = metadata.get('sha256')
    if not isinstance(total, int) or total < 1 or total > MAX_ARTIFACT_BYTES:
        raise ValueError(f'artifact size must be between 1 and {MAX_ARTIFACT_BYTES} bytes for this viewer relay')
    if not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum):
        raise ValueError('artifact metadata is missing a valid SHA-256')
    chunks = []
    offset = 0
    while offset < total:
        fetched = upstream_tool('clawbio_model_fetch', {
            'job_id': job_id, 'artifact_id': artifact_id, 'representation': 'base64', 'offset': offset,
            'length': min(CHUNK_BYTES, total - offset),
        })
        if not isinstance(fetched, dict) or fetched.get('artifact_id') != artifact_id or fetched.get('offset') != offset:
            raise ValueError('BioNeMo MCP returned an inconsistent artifact chunk')
        encoded = fetched.get('data')
        if not isinstance(encoded, str):
            raise ValueError('BioNeMo MCP returned artifact data in an invalid encoding')
        try:
            chunk = base64.b64decode(encoded, validate=True)
        except Exception as error:
            raise ValueError('BioNeMo MCP returned invalid base64 artifact data') from error
        if len(chunk) != fetched.get('returned_bytes') or not chunk:
            raise ValueError('BioNeMo MCP returned an invalid artifact chunk length')
        chunks.append(chunk)
        offset += len(chunk)
        expected_next = offset if offset < total else None
        if fetched.get('next_offset') != expected_next:
            raise ValueError('BioNeMo MCP returned a discontinuous artifact chunk')
    content = b''.join(chunks)
    if len(content) != total or hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError('BioNeMo MCP artifact failed integrity verification')
    return metadata, content


def save_artifact(job_id, artifact_id, filename_hint=None):
    metadata, content = fetch_artifact(job_id, artifact_id)
    original = filename_hint if isinstance(filename_hint, str) and filename_hint.strip() else metadata.get('name', 'artifact')
    safe = SAFE_NAME.sub('-', str(original)).strip('.-')[:160] or 'artifact'
    folder = (ARTIFACT_ROOT / job_id).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    destination = (folder / f'{artifact_id}-{safe}').resolve()
    if folder not in destination.parents:
        raise ValueError('unsafe artifact destination')
    destination.write_bytes(content)
    return metadata, destination


def leaf_values(value, prefix='', depth=0):
    if depth > 5:
        return []
    wanted = ('confidence', 'affinity', 'ranking', 'plddt', 'iptm', 'ptm', 'score', 'time', 'runtime')
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            path = f'{prefix}.{key}' if prefix else str(key)
            if any(token in str(key).lower() for token in wanted):
                if isinstance(item, (str, int, float, bool)) or item is None:
                    rows.append((path, item))
                elif isinstance(item, list) and len(item) <= 8 and all(isinstance(x, (str, int, float, bool)) or x is None for x in item):
                    rows.append((path, item))
            rows.extend(leaf_values(item, path, depth + 1))
        return rows
    if isinstance(value, list) and len(value) <= 8:
        rows = []
        for index, item in enumerate(value):
            rows.extend(leaf_values(item, f'{prefix}[{index}]', depth + 1))
        return rows
    return []


def download(arguments):
    job_id = validate_id(arguments.get('job_id'), 'job_id')
    artifact_id = validate_id(arguments.get('artifact_id'), 'artifact_id')
    metadata, destination = save_artifact(job_id, artifact_id, arguments.get('filename_hint'))
    media_type = str(metadata.get('media_type', ''))
    suffix = destination.suffix.lower()
    if suffix not in {'.cif', '.mmcif', '.pdb'} and media_type not in {'chemical/x-cif', 'chemical/x-pdb'}:
        raise ValueError('downloaded artifact is not a PDB or mmCIF structure; use bionemo_json_summary for response JSON')
    structure_format = 'pdb' if suffix == '.pdb' or media_type == 'chemical/x-pdb' else 'cif'
    return {
        'content': [{'type': 'text', 'text': json.dumps({
            'structure_path': str(destination), 'structure_format': structure_format,
            'bytes': metadata.get('bytes'), 'sha256': metadata.get('sha256'),
            'next_step': 'Call protein_viewer with structure_path and structure_format. Do not put the structure text in a tool call.',
        })}],
        'structuredContent': {'structure_path': str(destination), 'structure_format': structure_format, 'bytes': metadata.get('bytes')},
    }


def summarize(arguments):
    job_id = validate_id(arguments.get('job_id'), 'job_id')
    artifact_id = validate_id(arguments.get('artifact_id'), 'artifact_id')
    metadata, destination = save_artifact(job_id, artifact_id, 'response.json')
    if metadata.get('media_type') != 'application/json' and destination.suffix.lower() != '.json':
        raise ValueError('artifact is not JSON; use bionemo_artifact_download for structures')
    try:
        payload = json.loads(destination.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('JSON artifact could not be parsed') from error
    summary = []
    seen = set()
    for path, value in leaf_values(payload):
        encoded = json.dumps(value, ensure_ascii=False)
        if path not in seen and len(encoded) <= 500:
            summary.append({'field': path, 'value': value})
            seen.add(path)
        if len(summary) == 40:
            break
    result = {'json_path': str(destination), 'bytes': metadata.get('bytes'), 'scores': summary}
    return {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}], 'structuredContent': result}


def call_tool(name, arguments):
    if name == 'bionemo_artifact_download':
        return download(arguments)
    if name == 'bionemo_json_summary':
        return summarize(arguments)
    if name == 'bionemo_upload_local_file':
        result = upload_local_file(arguments)
        return {'content': [{'type': 'text', 'text': json.dumps(result)}], 'structuredContent': result}
    raise ValueError('unknown tool')


for line in sys.stdin:
    request = None
    try:
        request = json.loads(line)
        request_id = request.get('id')
        method = request.get('method')
        if method == 'initialize':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'bionemo-artifacts', 'version': '1.0'}}})
        elif method == 'ping':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': {}})
        elif method == 'notifications/initialized':
            continue
        elif method == 'tools/list':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': {'tools': TOOLS}})
        elif method == 'tools/call':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': call_tool(request.get('params', {}).get('name'), request.get('params', {}).get('arguments', {}))})
    except Exception as error:
        rpc_error(request.get('id') if isinstance(request, dict) else None, str(error))
