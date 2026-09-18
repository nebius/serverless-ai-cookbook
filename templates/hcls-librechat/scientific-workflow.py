#!/usr/bin/env python3
"""Resume a durable sequential workflow using the existing native/batch clients.

The JSON plan has schema scientific-workflow/v1 and steps with unique id plus
the client's named arguments (underscores, not CLI dashes). Batch steps use the
existing batch arguments. Native steps specify kind=native plus model, input,
output and idempotency_key. Each step uses
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
native_spec = importlib.util.spec_from_file_location('scientific_native_client', HERE / 'invoke-native.py')
native = importlib.util.module_from_spec(native_spec)
native_spec.loader.exec_module(native)
REQUIRED = {'model', 'tool', 'operation', 'source', 'media_type', 'entry_name',
            'semantic_type', 'parameters', 'output', 'idempotency_key', 'display_name'}
OPTIONAL = {'compression', 'service_class', 'source_artifact'}
NATIVE_REQUIRED = {'model', 'input', 'output', 'idempotency_key'}
TERMINAL_FAILURES = {'failed', 'cancelled', 'expired', 'preempted'}
CONCURRENCY_CODES = {'concurrency_exceeded', 'admission_limit_reached'}
MAX_READ_RECONNECTS = 3


def transport_disconnect(error):
    """Only retry read-only observation after a recognizable transport failure."""
    if isinstance(error, BaseExceptionGroup):
        return bool(error.exceptions) and all(transport_disconnect(item) for item in error.exceptions)
    return isinstance(error, (httpx2.TransportError, ConnectionError, TimeoutError))


def prepare(plan):
    if plan.get('schema') != 'scientific-workflow/v1' or not plan.get('steps'):
        raise ValueError('Expected scientific-workflow/v1 with nonempty steps.')
    ids, outputs = set(), set()
    for step in plan['steps']:
        identifier = step.get('id', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identifier) or identifier in ids:
            raise ValueError('Step IDs must be unique and readable.')
        kind = step.get('kind', 'batch')
        if kind not in {'batch', 'native'}:
            raise ValueError('Step kind must be batch or native.')
        required = NATIVE_REQUIRED if kind == 'native' else REQUIRED
        optional = set() if kind == 'native' else OPTIONAL
        if set(step) - required - optional - {'id', 'kind'} or required - set(step):
            raise ValueError('Step must use exactly the documented client arguments.')
        ids.add(identifier)
        for field in ('source', 'parameters', 'input', 'output', 'source_artifact'):
            if field not in step:
                continue
            if not isinstance(step[field], str) or not Path(step[field]).is_absolute():
                raise ValueError(f"Step {identifier} {field} must be an absolute file/directory path string, not inline JSON.")
        output = str(Path(step['output']).resolve())
        if output in outputs:
            raise ValueError('Different steps must not share a receipt directory.')
        outputs.add(output)
    return plan


def validate_files(plan):
    """Catch misspelled source paths/invalid JSON before any step is admitted.

    Model fields remain validated by the existing live-schema clients. This is
    file preflight, not a fabricated model-capability or scientific-quality gate.
    """
    prepare(plan)
    files = []
    for step in plan['steps']:
        for field in ('source', 'parameters', 'input', 'source_artifact'):
            if field not in step:
                continue
            path = Path(step[field])
            if not path.is_file():
                raise ValueError(f"Step {step['id']} {field} is not an existing file: {path}")
            digest = hashlib.sha256()
            size = 0
            with path.open('rb') as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            if field != 'source':
                try:
                    value = json.loads(path.read_bytes())
                except ValueError as error:
                    raise ValueError(f"Step {step['id']} {field} is not valid JSON: {path}") from error
                if not isinstance(value, dict):
                    raise ValueError(f"Step {step['id']} {field} must contain a JSON object: {path}")
            files.append({'step': step['id'], 'field': field, 'path': str(path),
                          'size_bytes': size, 'sha256': digest.hexdigest()})
    return {'schema': 'scientific-workflow-file-preflight/v1', 'steps': len(plan['steps']), 'files': files}


async def run_native_step(arguments, execute):
    """Use the native client's immutable receipt, never a second transport."""
    try:
        result = await execute(arguments)
    except Exception:
        saved = load(arguments.output_dir / 'receipt.json') or {}
        rejection = saved.get('last_rejection', {})
        # Inspect only the receipt for this exact failed attempt. A historical
        # rejection must not turn a later ambiguous admission into a retry.
        if (saved.get('state') == 'rejected' and not saved.get('operation_id')
                and rejection.get('code') in CONCURRENCY_CODES
                and rejection.get('durable_admission') is False):
            raise batch.ExplicitRejection(rejection) from None
        raise
    if result['state'] in TERMINAL_FAILURES:
        raise RuntimeError('Native operation ended ' + result['state'] + '; inspect its retained receipt and operation.json.')
    if result['state'] == 'succeeded':
        # invoke-native marks success only after saving complete result bytes.
        return {**result, 'native_state': 'succeeded', 'state': 'verified'}
    return result


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
              sleep=asyncio.sleep, native_run_step=None):
    prepare(plan)
    run_step = run_step or batch.run
    native_run_step = native_run_step or native.run
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
        reconnects = 0
        recover_only = False
        while True:
            started = clock()
            remaining = deadline - started
            if remaining <= 0:
                receipt.update(state='observation_expired', current_step=step_id)
                save(receipt_path, receipt)
                return receipt
            native_step = step.get('kind') == 'native'
            if native_step:
                arguments = {'model': step['model'], 'input': Path(step['input']),
                             'output_dir': Path(step['output']),
                             'idempotency_key': step['idempotency_key'],
                             # Keep short native observations in one session;
                             # never hold it through an unbounded batch wait.
                             'wait_seconds': min(poll_seconds, remaining, 30),
                             'recover_only': recover_only}
            else:
                arguments = {**{'compression': 'none', 'service_class': 'customer-batch'},
                             **{key: value for key, value in step.items() if key not in {'id', 'kind'}},
                             'wait_seconds': 0, 'poll_seconds': poll_seconds}
                for key in ('source', 'parameters', 'output'):
                    arguments[key] = Path(arguments[key])
                if arguments.get('source_artifact'):
                    arguments['source_artifact'] = Path(arguments['source_artifact'])
            step_output = Path(step['output'])
            receipt.update(state='running', current_step=step_id)
            save(receipt_path, receipt)
            try:
                with receipt_lock(step_output):
                    if native_step:
                        result = await run_native_step(argparse.Namespace(**arguments), native_run_step)
                    else:
                        result = await run_step(argparse.Namespace(**arguments))
                state = result['state']
                receipt['step_states'][step_id] = {key: result[key] for key in
                    ('state', 'operation_id', 'verified_artifacts', 'result_path', 'native_state') if key in result}
            except batch.ExplicitRejection as error:
                if error.error.get('code') not in CONCURRENCY_CODES or error.error.get('durable_admission') is not False:
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
                if isinstance(leaf, batch.ExplicitRejection) and leaf.error.get('code') in CONCURRENCY_CODES and leaf.error.get('durable_admission') is False:
                    state = 'waiting_admission'
                    receipt['step_states'][step_id] = {'state': state, 'error': leaf.error}
                    receipt['state'] = state
                    save(receipt_path, receipt)
                    print(json.dumps({'workflow_state': state, 'step': step_id,
                                      'completed_steps': receipt['completed_steps']}), flush=True)
                    remaining = deadline - clock()
                    if remaining <= 0:
                        return receipt
                    await sleep(min(remaining, max(poll_seconds,
                        min(float(leaf.error.get('retry_after_seconds') or poll_seconds), 60))))
                    continue
                known = load(step_output / 'receipt.json') or {}
                if (native_step and transport_disconnect(error) and known.get('operation_id')
                        and known.get('state') not in TERMINAL_FAILURES | {'submitting', 'admission_unknown'}
                        and reconnects < MAX_READ_RECONNECTS):
                    reconnects += 1
                    recover_only = True
                    event = {'step': step_id, 'operation_id': known['operation_id'],
                             'error_type': type(leaf).__name__, 'recovery': 'read_only',
                             'attempt': reconnects}
                    receipt.setdefault('observation_errors', []).append(event)
                    receipt['step_states'][step_id] = {'state': 'observation_interrupted',
                        'operation_id': known['operation_id']}
                    receipt.update(state='observation_interrupted', current_step=step_id)
                    save(receipt_path, receipt)
                    print(json.dumps(event), flush=True)
                    remaining = deadline - clock()
                    if remaining <= 0:
                        return receipt
                    await sleep(min(poll_seconds, remaining))
                    continue
                state = 'admission_unknown' if known.get('state') in {'submitting', 'admission_unknown'} else 'failed'
                receipt['step_states'][step_id] = {key: known[key] for key in
                    ('state', 'operation_id', 'last_rejection') if key in known}
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
            observed_at = clock()
            if observed_at >= deadline:
                return receipt
            delay = receipt['step_states'][step_id].get('error', {}).get('retry_after_seconds') or poll_seconds
            delay = max(poll_seconds, min(float(delay), 60))
            # Native.run already waited/polled within this same session. Do not
            # add another full sleep merely because its bounded wait elapsed.
            if native_step and state != 'waiting_admission':
                delay = max(0, delay - (observed_at - started))
            if delay:
                await sleep(min(delay, deadline - observed_at))
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
    parser.add_argument('--validate-only', action='store_true',
                        help='Read and hash every referenced source/input/parameter file; no uploads or inference.')
    args = parser.parse_args()
    if args.wait_seconds < 0 or args.poll_seconds < 1:
        parser.error('wait-seconds must be nonnegative and poll-seconds at least 1.')
    plan = json.loads(args.plan.read_text())
    preflight = validate_files(plan)
    if args.validate_only:
        print(json.dumps(preflight))
        return
    with receipt_lock(args.output):
        save(args.output / 'file-preflight.json', preflight)
        save(args.output / 'caller-policy.json', asyncio.run(caller_policy()))
        result = asyncio.run(run(plan, args.output,
                                 args.wait_seconds, args.poll_seconds))
    print(json.dumps({'state': result['state'], 'completed_steps': result['completed_steps'],
                      'resume': str(args.output)}))
    # An incomplete observation must not allow an && chain to claim completion.
    raise SystemExit(0 if result['state'] == 'completed' else 75)


if __name__ == '__main__':
    main()
