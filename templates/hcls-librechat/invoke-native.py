#!/usr/bin/env python3
"""Submit file-backed native inputs through the public MCP, retaining receipts.

Large inputs, credentials and raw results stay on disk. Reusing the output
directory resumes the saved operation; ambiguous admission is never retried.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import quote

import httpx2
from jsonschema import Draft202012Validator, ValidationError
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from scientific_receipts import load as load_receipt, receipt_lock, save, staged_output, verify_file


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


def explicit_rejection(response):
    """Return a bounded error only when the gateway proves no admission occurred."""
    data = response if isinstance(response, dict) else response.model_dump(mode='json', by_alias=True)
    if not data.get('isError'):
        return None
    texts = [c.get('text', '') for c in data.get('content', []) if c.get('type') == 'text']
    if len(texts) != 1:
        return None
    try:
        error = json.loads(texts[0]).get('error', {})
    except (TypeError, ValueError, AttributeError):
        return None
    if error.get('durable_admission') is not False:
        return None
    allowed = ('type', 'code', 'message', 'request_id', 'idempotency_key',
               'retryable', 'retry_after_seconds', 'durable_admission')
    return {key: error[key] for key in allowed if key in error}


def parse_result_artifact(envelope, data):
    if envelope.get('schema') != 'fs2-serve.nebius.ai/operation-artifact-result/v1':
        return envelope
    artifact = envelope.get('artifact', {})
    if (envelope.get('content_type') != 'application/json'
            or artifact.get('compression') != 'none'
            or len(data) != artifact.get('size_bytes')
            or hashlib.sha256(data).hexdigest() != artifact.get('sha256')):
        raise ValueError('Result artifact format, size or SHA-256 mismatch.')
    return json.loads(data)


def materialize_result_artifact(envelope, data, output_dir):
    """Keep JSON compatibility and publish native media as verified files.

    The gateway's content_type describes the bytes, whereas its storage
    artifact may use application/octet-stream. Never parse MP4/audio as JSON
    or mistake a successful model's download for a new inference admission.
    """
    if envelope.get('content_type') == 'application/json':
        return parse_result_artifact(envelope, data)
    artifact = envelope.get('artifact', {})
    if (envelope.get('schema') != 'fs2-serve.nebius.ai/operation-artifact-result/v1'
            or artifact.get('compression') != 'none'
            or len(data) != artifact.get('size_bytes')
            or hashlib.sha256(data).hexdigest() != artifact.get('sha256')):
        raise ValueError('Result artifact format, size or SHA-256 mismatch.')
    media_type = envelope.get('content_type')
    extensions = {'video/mp4': 'mp4', 'video/webm': 'webm', 'image/png': 'png',
                  'image/jpeg': 'jpg', 'audio/wav': 'wav', 'audio/x-wav': 'wav',
                  'audio/mpeg': 'mp3', 'audio/ogg': 'ogg',
                  'application/octet-stream': 'bin'}
    if media_type not in extensions:
        raise ValueError('Native artifact content type has no supported file contract.')
    target = output_dir / ('result.' + extensions[media_type])
    with staged_output(target) as staged:
        staged.path.write_bytes(data)
    return {'schema': 'scientific-native-file/v1', 'content_type': media_type,
            'artifact': artifact, 'file': staged.receipt}


def verify_saved_native_file(value, output_dir):
    if value.get('schema') != 'scientific-native-file/v1':
        return
    reference = value['file']
    target = Path(reference['path'])
    if target.parent.resolve() != output_dir.resolve() or not target.name.startswith('result.'):
        raise ValueError('Saved native media must belong to this operation directory.')
    if (reference['size_bytes'], reference['sha256']) != (
            value['artifact']['size_bytes'], value['artifact']['sha256']):
        raise ValueError('Saved native file identity differs from its gateway artifact.')
    verify_file(target, reference)


def validate_input(schema, arguments, output_dir, record):
    """Retain a useful pre-admission diagnostic without another model call."""
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as error:
        pointer = lambda parts: '/' + '/'.join(str(part).replace('~', '~0').replace('/', '~1') for part in parts)
        evidence = {'type': 'local_input_validation', 'durable_admission': False,
                    'message': error.message[:2000], 'validator': error.validator,
                    'input_pointer': pointer(error.absolute_path),
                    'schema_pointer': pointer(error.absolute_schema_path)}
        save(output_dir / 'validation-error.json', evidence)
        record.update(state='input_rejected', last_rejection=evidence)
        save(output_dir / 'receipt.json', record)
        raise


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
    record = load_receipt(path)
    if record is None:
        record = {'identity': identity, 'state': 'prepared'}
    if record['identity'] != identity:
        raise ValueError('Output directory belongs to different inputs, caller, model or idempotency key.')
    save(path, record)
    if record['state'] in ('submitting', 'admission_unknown'):
        submission = args.output_dir / 'submission.json'
        saved_submission = json.loads(submission.read_text()) if submission.exists() else {}
        rejection = explicit_rejection(saved_submission)
        if rejection:
            record.update(state='prepared', last_rejection=rejection)
            save(path, record)
            accepted = {}
        else:
            accepted = unpack(saved_submission) if submission.exists() else {}
        if not rejection:
            operation = accepted['operation'] if isinstance(accepted.get('operation'), dict) else accepted
            if (operation.get('id') and operation.get('status')
                    and operation.get('model_id') == args.model
                    and operation.get('idempotency_key') == args.idempotency_key):
                record.update(operation_id=operation['id'], state=operation['status'])
                save(path, record)
            else:
                raise RuntimeError('Previous admission is unknown. Inspect receipt; do not resubmit.')
    if record['state'] == 'succeeded':
        result_path = args.output_dir / 'result.json'
        saved_result = json.loads(result_path.read_text()) if result_path.is_file() else {}
        verify_saved_native_file(saved_result, args.output_dir)
        if (not result_path.is_file()
                or saved_result.get('schema') == 'fs2-serve.nebius.ai/operation-artifact-result/v1'):
            record['state'] = 'result_pending'
            save(path, record)
    if record['state'] in ('succeeded', 'failed', 'cancelled', 'expired', 'preempted'):
        return record
    if getattr(args, 'recover_only', False) and not record.get('operation_id'):
        # No admission, upload, or rediscovery is needed to read a saved error.
        # An absent receipt is not permission to reconstruct it by resubmission.
        raise RuntimeError('Read-only recovery has no known operation. Inspect the saved receipt and validation-error.json; no new inference was submitted.')
    # Session setup/submission consume the observation allowance too. An in-
    # flight network request still has its existing timeout; do not extend the
    # workflow's observation deadline by starting a new wait after setup.
    deadline = time.monotonic() + args.wait_seconds
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
                validate_input(contract['input_schema'], arguments, args.output_dir, record)
                record.update(state='submitting', tool=contract['tool_name'], input_bytes=len(payload_bytes))
                save(path, record)
                try:
                    accepted = await call(contract['tool_name'], arguments, 'submission.json')
                    operation = accepted['operation'] if isinstance(accepted.get('operation'), dict) else accepted
                    record.update(operation_id=operation['id'], state=operation['status'])
                except Exception:
                    response = json.loads((args.output_dir / 'submission.json').read_text()) if (args.output_dir / 'submission.json').exists() else {}
                    rejection = explicit_rejection(response)
                    if rejection:
                        record.update(state='rejected', last_rejection=rejection)
                    else:
                        record['state'] = 'admission_unknown'
                    save(path, record)
                    raise
                save(path, record)

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
                    value = result['result']
                    if value.get('schema') == 'fs2-serve.nebius.ai/operation-artifact-result/v1':
                        save(args.output_dir / 'result-artifact.json', value)
                        artifact_id = value.get('artifact', {}).get('artifact_id')
                        if not isinstance(artifact_id, str):
                            raise ValueError('Result artifact identifier is missing.')
                        origin = endpoint.removesuffix('/mcp').removesuffix('/mcp/')
                        downloaded = await http.get(origin + '/v1/artifacts/' + quote(artifact_id, safe='') + '/content')
                        downloaded.raise_for_status()
                        value = materialize_result_artifact(value, downloaded.content, args.output_dir)
                    save(args.output_dir / 'result.json', value)
                    record.update(state='succeeded', result_path=str(args.output_dir / 'result.json'))
                    save(path, record)
                    return record
                if state in ('failed', 'cancelled', 'expired', 'preempted') or time.monotonic() >= deadline:
                    return record
                await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true',
                        help='Only read/poll a saved operation and its result; never submit a request to reconstruct missing evidence.')
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 200 or args.wait_seconds < 0:
        parser.error('Use an 8–200 character idempotency key and a nonnegative wait.')
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with receipt_lock(args.output_dir):
            record = asyncio.run(run(args))
        print(json.dumps({k: record[k] for k in ('state', 'operation_id', 'result_path') if k in record}))
        if record['state'] in ('failed', 'cancelled', 'expired', 'preempted'):
            raise SystemExit(1)
        if record['state'] != 'succeeded':
            raise SystemExit(75)
    except Exception as error:
        # Provider/library exception text may contain signed handles or headers.
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect local receipt files; no automatic resubmission.',
                          'output_dir': str(args.output_dir)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
