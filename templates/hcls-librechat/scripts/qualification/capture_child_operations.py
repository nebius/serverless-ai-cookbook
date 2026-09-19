#!/usr/bin/env python3
"""Read exact campaign parent/child identities; no payloads or database writes."""
import argparse
import json
from pathlib import Path
import subprocess
from uuid import UUID

from manage_campaign import CONTEXT, KUBECONFIG, save

POD_READ = r'''
import asyncio, json, sys
from uuid import UUID
import asyncpg
from fs2_serve.settings import Settings

async def main():
    parent, principal, tenant = json.loads(sys.argv[1])
    connection = await asyncpg.connect(Settings().database_url.replace(
        'postgresql+asyncpg://', 'postgresql://', 1), timeout=15, command_timeout=15)
    try:
        async with connection.transaction(readonly=True, isolation='repeatable_read'):
            parent_row = await connection.fetchrow(
                'SELECT id, model_id, status FROM fs2_operations '
                'WHERE id=$1 AND principal_id=$2 AND tenant_id=$3',
                UUID(parent), principal, tenant)
            if parent_row is None:
                raise ValueError('Exact campaign parent not found')
            children = await connection.fetch(
                'SELECT id, parent_operation_id, model_id, protocol, operation, status, accepted_at, '
                'started_at, completed_at, error_code FROM fs2_operations '
                'WHERE parent_operation_id=$1 AND principal_id=$2 AND tenant_id=$3 '
                'ORDER BY accepted_at, id LIMIT 4097', UUID(parent), principal, tenant)
            if len(children) > 4096:
                raise ValueError('Child observation bound exceeded')
            print(json.dumps({'parent': dict(parent_row), 'readonly': True,
                'children': [dict(row) for row in children]}, default=str))
    finally:
        await connection.close()

asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', required=True, type=UUID)
    parser.add_argument('--scientist', required=True)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    person = next(p for p in json.loads(args.manifest.read_text())['scientists']
                  if p['id'] == args.scientist)
    if not person['tenant_id'].startswith('qualification-20260918-lab-'):
        raise ValueError('This reader is scoped to the campaign identities')
    result = subprocess.run(['kubectl', '--kubeconfig', KUBECONFIG, '--context', CONTEXT,
        '-n', 'fs2-system', 'exec', 'deployment/fs2-serve-control-plane', '-c', 'control-plane',
        '--', 'python', '-c', POD_READ,
        json.dumps([str(args.parent), person['principal_id'], person['tenant_id']])],
        capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Exact-parent read failed; credentials and stderr not disclosed')
    value = json.loads(result.stdout)
    save(args.output, value)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
