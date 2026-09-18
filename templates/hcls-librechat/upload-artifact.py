#!/usr/bin/env python3
"""Upload exact local bytes and return a verified immutable model artifact.

Hashes, signed handles and file bytes never pass through the language model.
The output directory is a private resumable receipt, bound to one immutable
file identity, caller and idempotency key. This helper does not run inference.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def file_identity(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


async def chunks(path):
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            yield chunk


def unpack(response):
    value = response if isinstance(response, dict) else response.model_dump(mode='json', by_alias=True)
    if value.get('isError'):
        raise RuntimeError('Upload request failed; see private receipt. No inference was submitted.')
    if value.get('structuredContent') is not None:
        return value['structuredContent']
    messages = [item['text'] for item in value.get('content', []) if item.get('type') == 'text']
    if len(messages) != 1:
        raise RuntimeError('Expected one JSON upload result.')
    return json.loads(messages[0])


async def transfer(client, object_http, args, endpoint, key):
    content = file_identity(args.file)
    identity = {**content, 'model_id': args.model, 'media_type': args.media_type,
                'endpoint': endpoint, 'caller_fingerprint': hashlib.sha256(key.encode()).hexdigest(),
                'idempotency_key': args.idempotency_key}
    receipt = args.output_dir / 'receipt.json'
    record = json.loads(receipt.read_text()) if receipt.exists() else {'identity': identity, 'state': 'prepared'}
    if record['identity'] != identity:
        raise ValueError('File bytes, caller or upload identity changed. Use a new output directory and idempotency key.')
    if record['state'] == 'finalized':
        return record

    async def call(tool, arguments, filename):
        response = await client.call_tool(tool, arguments)
        save(args.output_dir / filename, response if isinstance(response, dict) else response.model_dump(mode='json', by_alias=True))
        return unpack(response)

    record['state'] = 'reserving'
    save(receipt, record)
    # Same immutable identity is safe to replay after a lost reservation response.
    reserved = await call('begin_model_artifact_upload', dict(content, model_id=args.model,
                           media_type=args.media_type, idempotency_key=args.idempotency_key), 'reservation.json')
    record.update(operation_id=reserved['operation_id'], upload_id=reserved['upload_id'], state='reserved')
    save(receipt, record)
    handle = reserved['handle']
    if handle.get('method') != 'PUT' or not handle.get('url', '').startswith('https://'):
        raise ValueError('Expected a platform-issued HTTPS PUT handle.')
    # object_http is deliberately separate and has NO platform Authorization header.
    response = await object_http.put(handle['url'], content=chunks(args.file),
                                     headers={**handle.get('headers', {}), 'Content-Length': str(content['size_bytes'])})
    save(args.output_dir / 'transfer.json', {'status': response.status_code, **content})
    if response.status_code not in (409, 412):
        response.raise_for_status()
    # 409/412 may mean a previous attempt already wrote the immutable object.
    # Finalization verifies its digest; never overwrite it or assume it matches.
    if file_identity(args.file) != content:
        # This reservation cannot be used for the changed file. Release only our
        # own known upload operation, preserving both the transfer and cancel receipt.
        record['state'] = 'input_changed'
        save(receipt, record)
        cancelled = await call('cancel_operation', {'operation_id': reserved['operation_id']}, 'cancel.json')
        record['cancellation'] = cancelled
        save(receipt, record)
        raise ValueError('Local file changed during transfer; do not reuse this upload identity.')
    record['state'] = 'verifying'
    save(receipt, record)
    artifact = await call('finalize_model_artifact_upload',
                          {'operation_id': reserved['operation_id'], 'upload_id': reserved['upload_id']}, 'finalize.json')
    if any(artifact.get(field) != expected for field, expected in content.items()) or not artifact.get('artifact_id'):
        raise ValueError('Finalized artifact does not match the actual input bytes.')
    save(args.output_dir / 'artifact.json', artifact)
    record.update(state='finalized', artifact=artifact)
    save(receipt, record)
    return record


async def run(args):
    endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
    key = os.environ['SCIENTIFIC_MODELS_API_KEY']
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + key}, timeout=120, trust_env=False) as http:
        async with httpx2.AsyncClient(timeout=300, trust_env=False, follow_redirects=False) as object_http:
            async with Client(streamable_http_client(endpoint, http_client=http)) as client:
                return await transfer(client, object_http, args, endpoint, key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('--media-type', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 200:
        parser.error('Use an 8–200 character idempotency key.')
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (args.output_dir / 'client.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = asyncio.run(run(args))
        print(json.dumps({'state': result['state'], 'operation_id': result['operation_id'],
                          'artifact': result['artifact'], 'artifact_file': str(args.output_dir / 'artifact.json')}))
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect private receipt files. Do not fabricate hashes or resubmit inference.',
                          'output_dir': str(args.output_dir)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
