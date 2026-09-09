#!/usr/bin/env python3
"""Submit file-backed native inputs through the public MCP, retaining receipts.

Large inputs, credentials and raw results stay on disk. Reusing the output
directory resumes the saved operation; ambiguous admission is never retried.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(path)


def unpack(response):
    data = response if isinstance(response, dict) else response.model_dump(mode='json', by_alias=True)
    if data.get('isError'):
        raise RuntimeError('MCP returned isError; inspect the saved receipt. Admission may be unknown.')
    if data.get('structuredContent') is not None:
        return data['structuredContent']
    texts = [c['text'] for c in data.get('content', []) if c['type'] == 'text']
    if len(texts) != 1:
        raise RuntimeError('Expected one JSON MCP result.')
    return json.loads(texts[0])


async def run(args):
    endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
    key = os.environ['SCIENTIFIC_MODELS_API_KEY']
    payload_bytes = args.input.read_bytes()
    payload = json.loads(payload_bytes)
    if not isinstance(payload, dict):
        raise ValueError('Input must be a JSON object containing only model fields.')
    if set(payload) & {'idempotency_key', 'wait_seconds'}:
        raise ValueError('Keep lifecycle fields out of the input file; pass --idempotency-key.')
    identity = {'model_id': args.model, 'input_sha256': hashlib.sha256(payload_bytes).hexdigest(),
                'endpoint': endpoint, 'caller_fingerprint': hashlib.sha256(key.encode()).hexdigest(),
                'idempotency_key': args.idempotency_key}
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = args.output_dir / 'receipt.json'
    record = json.loads(path.read_text()) if path.exists() else {'identity': identity, 'state': 'prepared'}
    if record['identity'] != identity:
        raise ValueError('Output directory belongs to different inputs, caller, model or idempotency key.')
    if record['state'] in ('submitting', 'admission_unknown'):
        submission = args.output_dir / 'submission.json'
        accepted = unpack(json.loads(submission.read_text())) if submission.exists() else {}
        operation = accepted['operation'] if isinstance(accepted.get('operation'), dict) else accepted
        if (operation.get('id') and operation.get('status')
                and operation.get('model_id') == args.model
                and operation.get('idempotency_key') == args.idempotency_key):
            record.update(operation_id=operation['id'], state=operation['status'])
            save(path, record)
        else:
            raise RuntimeError('Previous admission is unknown. Inspect receipt; do not resubmit.')
    if record['state'] == 'succeeded' and not (args.output_dir / 'result.json').is_file():
        record['state'] = 'result_pending'
        save(path, record)
    if record['state'] in ('succeeded', 'failed', 'cancelled', 'expired', 'preempted'):
        return record
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + key}, timeout=120, trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http)) as client:
            async def call(name, arguments, filename):
                response = await client.call_tool(name, arguments)
                save(args.output_dir / filename, response.model_dump(mode='json', by_alias=True))
                return unpack(response)

            if not record.get('operation_id'):
                schema = await call('get_model_schema', {'model_id': args.model, 'protocol': 'native'}, 'schema.json')
                contract = next(c for c in schema['contracts'] if c['protocol'] == 'native')
                arguments = dict(payload, idempotency_key=args.idempotency_key, wait_seconds=0)
                Draft202012Validator(contract['input_schema']).validate(arguments)
                record.update(state='submitting', tool=contract['tool_name'], input_bytes=len(payload_bytes))
                save(path, record)
                try:
                    accepted = await call(contract['tool_name'], arguments, 'submission.json')
                    operation = accepted['operation'] if isinstance(accepted.get('operation'), dict) else accepted
                    record.update(operation_id=operation['id'], state=operation['status'])
                except Exception:
                    record['state'] = 'admission_unknown'
                    save(path, record)
                    raise
                save(path, record)

            deadline = time.monotonic() + args.wait_seconds
            while True:
                operation = await call('get_operation', {'operation_id': record['operation_id']}, 'operation.json')
                # Only mark succeeded after the result bytes have been saved.
                state = operation['status']
                record['state'] = 'result_pending' if state == 'succeeded' else state
                save(path, record)
                if state == 'succeeded' and operation.get('result_available'):
                    result = await call('get_operation_result', {'operation_id': record['operation_id']}, 'result-envelope.json')
                    if result['operation']['id'] != record['operation_id']:
                        raise RuntimeError('Result operation identity mismatch.')
                    save(args.output_dir / 'result.json', result['result'])
                    record.update(state='succeeded', result_path=str(args.output_dir / 'result.json'))
                    save(path, record)
                    return record
                if state in ('failed', 'cancelled', 'expired', 'preempted') or time.monotonic() >= deadline:
                    return record
                await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=300)
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 200 or args.wait_seconds < 0:
        parser.error('Use an 8–200 character idempotency key and a nonnegative wait.')
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (args.output_dir / 'client.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record = asyncio.run(run(args))
        print(json.dumps({k: record[k] for k in ('state', 'operation_id', 'result_path') if k in record}))
        if record['state'] in ('failed', 'cancelled', 'expired', 'preempted'):
            raise SystemExit(1)
    except Exception as error:
        # Provider/library exception text may contain signed handles or headers.
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect local receipt files; no automatic resubmission.',
                          'output_dir': str(args.output_dir)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
