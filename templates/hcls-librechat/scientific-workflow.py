#!/usr/bin/env python3
"""Resume a durable sequential scientific workflow using the existing batch client.

The JSON plan has schema scientific-workflow/v1 and steps with unique id plus
the batch client's named arguments (underscores, not CLI dashes). Each step uses
an immutable idempotency_key and output directory. Observation timeout is NOT
completion: later steps start only after the previous receipt is verified.
No new inference is attempted after ambiguous admission or an application error.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time

import httpx2
from scientific_receipts import load, receipt_lock, save

HERE = Path(__file__).parent
BATCH = HERE / 'invoke-scientific-batch.py'
if not BATCH.exists():
    BATCH = HERE / 'scripts/scientific-batch-acceptance.py'
spec = importlib.util.spec_from_file_location('scientific_batch_client', BATCH)
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)
REQUIRED = {'model', 'tool', 'operation', 'source', 'media_type', 'entry_name',
            'semantic_type', 'parameters', 'output', 'idempotency_key', 'display_name'}
OPTIONAL = {'compression', 'service_class', 'source_artifact'}


def prepare(plan):
    if plan.get('schema') != 'scientific-workflow/v1' or not plan.get('steps'):
        raise ValueError('Expected scientific-workflow/v1 with nonempty steps.')
    ids, outputs = set(), set()
    for step in plan['steps']:
        identifier = step.get('id', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identifier) or identifier in ids:
            raise ValueError('Step IDs must be unique and readable.')
        if set(step) - REQUIRED - OPTIONAL - {'id'} or REQUIRED - set(step):
            raise ValueError('Step must use exactly the documented batch-client arguments.')
        ids.add(identifier)
        for field in ('source', 'parameters', 'output', 'source_artifact'):
            if field not in step:
                continue
            if not Path(step[field]).is_absolute():
                raise ValueError('Step paths must be absolute.')
        output = str(Path(step['output']).resolve())
        if output in outputs:
            raise ValueError('Different steps must not share a receipt directory.')
        outputs.add(output)
    return plan


async def caller_policy():
    """Optional self-description, never an admission reservation or internal API."""
    origin = os.environ['SCIENTIFIC_MODELS_MCP_URL'].rstrip('/').removesuffix('/mcp')
    async with httpx2.AsyncClient(timeout=15, trust_env=False) as http:
        try:
            response = await http.get(origin + '/v1/me', headers={
                'authorization': 'Bearer ' + os.environ['SCIENTIFIC_MODELS_API_KEY']})
            if response.status_code == 404:
                return {'available': False, 'reason': 'server_does_not_expose_self_description'}
            response.raise_for_status()
            body = response.json()
            return {'available': True, **{key: body[key] for key in
                ('tenant_id', 'principal_id', 'max_concurrency', 'concurrency_scope',
                 'counted_states', 'available_slots') if key in body}}
        except (httpx2.HTTPError, ValueError):
            return {'available': False, 'reason': 'self_description_unavailable',
                    'note': 'Admission remains enforced by the server.'}


async def run(plan, output, wait_seconds=1800, poll_seconds=10, run_step=None, clock=time.monotonic,
              sleep=asyncio.sleep):
    prepare(plan)
    run_step = run_step or batch.run
    identity = hashlib.sha256(batch.canonical({'plan': plan,
        'endpoint': os.environ.get('SCIENTIFIC_MODELS_MCP_URL'),
        'caller_fingerprint': hashlib.sha256(os.environ.get('SCIENTIFIC_MODELS_API_KEY', '').encode()).hexdigest()})).hexdigest()
    receipt_path = output / 'receipt.json'
    receipt = load(receipt_path) or {'plan_sha256': identity, 'state': 'prepared',
                                     'completed_steps': [], 'step_states': {}}
    if receipt['plan_sha256'] != identity:
        raise ValueError('Workflow plan changed. Preserve this workflow and its original receipts.')
    if receipt.get('state') in {'failed', 'admission_unknown'}:
        raise RuntimeError('Workflow requires inspection; retained failure must not be silently retried.')
    save(output / 'plan.json', plan)
    deadline = clock() + wait_seconds if wait_seconds else float('inf')
    for step in plan['steps']:
        step_id = step['id']
        if step_id in receipt['completed_steps']:
            continue
        while True:
            arguments = {**{'compression': 'none', 'service_class': 'customer-batch'},
                         **{key: value for key, value in step.items() if key != 'id'},
                         'wait_seconds': 0, 'poll_seconds': poll_seconds}
            for key in ('source', 'parameters', 'output'):
                arguments[key] = Path(arguments[key])
            if arguments.get('source_artifact'):
                arguments['source_artifact'] = Path(arguments['source_artifact'])
            receipt.update(state='running', current_step=step_id)
            save(receipt_path, receipt)
            try:
                with receipt_lock(arguments['output']):
                    result = await run_step(argparse.Namespace(**arguments))
                state = result['state']
                receipt['step_states'][step_id] = {key: result[key] for key in
                    ('state', 'operation_id', 'verified_artifacts') if key in result}
            except batch.ExplicitRejection as error:
                if error.error.get('code') != 'concurrency_exceeded' or error.error.get('durable_admission') is not False:
                    receipt.update(state='failed', failure={'type': type(error).__name__, **error.error})
                    save(receipt_path, receipt)
                    raise
                state = 'waiting_admission'
                receipt['step_states'][step_id] = {'state': state, 'error': error.error}
            except Exception as error:
                # Streamable HTTP cleanup may wrap the sole explicit rejection
                # in a task-group exception. Multiple or unknown failures remain
                # ambiguous and must never be converted into a retry.
                leaf = error
                while isinstance(leaf, BaseExceptionGroup) and len(leaf.exceptions) == 1:
                    leaf = leaf.exceptions[0]
                if isinstance(leaf, batch.ExplicitRejection) and leaf.error.get('code') == 'concurrency_exceeded' and leaf.error.get('durable_admission') is False:
                    state = 'waiting_admission'
                    receipt['step_states'][step_id] = {'state': state, 'error': leaf.error}
                    receipt['state'] = state
                    save(receipt_path, receipt)
                    print(json.dumps({'workflow_state': state, 'step': step_id,
                                      'completed_steps': receipt['completed_steps']}), flush=True)
                    if clock() >= deadline:
                        return receipt
                    await sleep(max(poll_seconds, min(float(leaf.error.get('retry_after_seconds') or poll_seconds), 60)))
                    continue
                known = load(arguments['output'] / 'receipt.json') or {}
                state = 'admission_unknown' if known.get('state') in {'submitting', 'admission_unknown'} else 'failed'
                receipt.update(state=state, failure={'type': type(error).__name__, 'message': str(error)[:500]})
                save(receipt_path, receipt)
                raise
            receipt['state'] = state
            save(receipt_path, receipt)
            print(json.dumps({'workflow_state': state, 'step': step_id,
                              'operation_id': receipt['step_states'][step_id].get('operation_id'),
                              'completed_steps': receipt['completed_steps']}), flush=True)
            if state == 'verified':
                receipt['completed_steps'].append(step_id)
                save(receipt_path, receipt)
                break
            if clock() >= deadline:
                return receipt
            delay = receipt['step_states'][step_id].get('error', {}).get('retry_after_seconds') or poll_seconds
            await sleep(max(poll_seconds, min(float(delay), 60)))
    receipt.update(state='completed', current_step=None)
    save(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait-seconds', type=float, default=1800,
                        help='Observation duration; 0 waits until terminal. Resume the same plan/output.')
    parser.add_argument('--poll-seconds', type=float, default=10)
    args = parser.parse_args()
    if args.wait_seconds < 0 or args.poll_seconds < 1:
        parser.error('wait-seconds must be nonnegative and poll-seconds at least 1.')
    with receipt_lock(args.output):
        save(args.output / 'caller-policy.json', asyncio.run(caller_policy()))
        result = asyncio.run(run(json.loads(args.plan.read_text()), args.output,
                                 args.wait_seconds, args.poll_seconds))
    print(json.dumps({'state': result['state'], 'completed_steps': result['completed_steps'],
                      'resume': str(args.output)}))
    # An incomplete observation must not allow an && chain to claim completion.
    raise SystemExit(0 if result['state'] == 'completed' else 75)


if __name__ == '__main__':
    main()
