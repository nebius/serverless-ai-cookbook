#!/usr/bin/env python3
"""Dedicated-user whole-study queue and application supervisor.

This is one worker for one LibreChat instance, not a shared multiuser service or
an agent loop. Only saved typed phases run. Local process locking does not claim
distributed bucket locking; do not run overlapping copies for the same user.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import scientific_study as studies
from scientific_receipts import receipt_lock, save


def next_study(items):
    """Never overlap an unresolved/ambiguous admission with a later study."""
    for item in sorted(items, key=lambda item: item['created_at']):
        if item.get('queue_blocked') and (item.get('admission_unknown') or item.get('cancellation_unknown') or not (studies.directory(item['id']) / 'cancel-request.json').exists()):
            return None, item['id']
        if item['state'] not in studies.FINAL or (
                item.get('queue_blocked') and (studies.directory(item['id']) / 'cancel-request.json').exists()):
            return item['id'], None
    return None, None


async def cycle():
    identifier, blocked = next_study(studies.list_studies())
    # Health is non-secret local state. Durable study receipts live in the bucket.
    health = Path(os.environ.get('SCIENTIFIC_EXECUTION_DIR', '/data/hcls-execution')) / 'study-worker.json'
    health.parent.mkdir(parents=True, exist_ok=True)
    save(health, {'updated_at': time.time(), 'pid': os.getpid(), 'current_study': identifier,
                  'process_start': Path('/proc/self/stat').read_text().split()[21],
                  'blocked_by_study': blocked, 'owner_namespace': studies.owner_identity()})
    return await studies.advance(identifier) if identifier else None


def worker():
    while True:
        try:
            # Also excludes duplicate workers caused by MCP/browser reconnect.
            with receipt_lock(studies.registry() / 'queue-worker'):
                asyncio.run(cycle())
        except Exception as error:
            # No phase resubmission here: advance() persists application errors;
            # storage/identity failures stop this observation until accessible.
            print(json.dumps({'event': 'study_worker_observation_failed',
                              'error_type': type(error).__name__}), flush=True)
        time.sleep(2)


def supervise(command):
    """Restart only the receipt worker; API termination remains container exit."""
    stopping = False
    children = []

    def stop(_signal=None, _frame=None):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    api = subprocess.Popen(command, start_new_session=True, preexec_fn=studies.stop_with_parent)
    children.append(api)
    runner = None
    enabled = os.environ.get('SCIENTIFIC_STUDY_OWNER_MODE') in {'first-instance', 'stopped-predecessor'}
    try:
        while not stopping and api.poll() is None:
            if enabled and (runner is None or runner.poll() is not None):
                runner = subprocess.Popen([sys.executable, __file__, '--worker'], start_new_session=True,
                                          preexec_fn=studies.stop_with_parent)
                children.append(runner)
            time.sleep(0.25)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    return api.returncode or 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.worker:
        worker()
    else:
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not command:
            parser.error('Provide the existing API command after --.')
        raise SystemExit(supervise(command))
