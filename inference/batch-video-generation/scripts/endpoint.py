#!/usr/bin/env python3
"""Small, credential-safe launcher for the existing Nebius Endpoint templates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.state' / 'endpoint.json'
CLI = os.environ.get('NEBIUS_BIN', 'nebius')
# AI_AGENT identifies the CLI caller to Nebius; preserve an existing label or default to cookbook below.


def resource_id(prefix):
    def validate(value):
        suffix = value.removeprefix(prefix + '-')
        if (not re.fullmatch(re.escape(prefix) + r'-[a-z0-9]+', value)
                or suffix in {'id', 'placeholder', 'example', 'yourid', 'changeme'}):
            raise argparse.ArgumentTypeError(
                f'Copy a {prefix}-... ID from the Nebius console; empty values and placeholders are not valid.')
        return value
    return validate


def scrub(text):
    text = re.sub(r'(?i)\bBearer\s+[^\s,;"\']+', 'Bearer [redacted]', text)
    text = re.sub(r'\bhf_[A-Za-z0-9]{12,}\b', '[redacted]', text)
    text = re.sub(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b', '[redacted]', text)
    text = re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[redacted]', text)
    return '\n'.join(line for line in text.splitlines()
                     if not any(word in line.lower() for word in ('token:', 'auth_token', 'secret_access_key', 'password', 'authorization')))


def cli(args, *, required=True):
    env = os.environ.copy()
    env['AI_AGENT'] = env.get('AI_AGENT') or 'cookbook'
    try:
        proc = subprocess.run([CLI, *args, '--format', 'json', '--no-progress', '--no-browser'],
                              capture_output=True, text=True, env=env, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Nebius CLI did not finish. Check sign-in and inspect resource state before retrying a create.') from exc
    if proc.returncode:
        if not required and re.search(r'\b(?:NotFound|NOT_FOUND)\b|"code"\s*:\s*404\b', proc.stderr):
            return None
        # Never echo a raw resource or generated authentication token.
        lines = scrub(proc.stderr).splitlines()
        raise RuntimeError('\n'.join(lines[:8]) or 'Nebius request failed; check your sign-in, project, quota and CLI version.')
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        if '--dry-run' in args:
            return {}
        if args[:3] in (['ai', 'endpoint', 'start'], ['ai', 'endpoint', 'stop']) and '--async' in args:
            # Async lifecycle calls can return a plain operation ID; the caller polls the Endpoint state.
            return {}
        # Some versions prefix create output with a generated token. It remains in memory.
        for i, char in enumerate(proc.stdout if args[:3] == ['ai', 'endpoint', 'create'] else ''):
            if char == '{':
                try:
                    return json.JSONDecoder().raw_decode(proc.stdout[i:])[0]
                except json.JSONDecodeError:
                    pass
        raise RuntimeError('Nebius returned unexpected output. Inspect the resource before retrying a write.')


def load_state():
    if not STATE.exists():
        raise RuntimeError('No Endpoint selected. Run create or attach first.')
    return json.loads(STATE.read_text())


def save_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(STATE)


def summary(endpoint):
    return {'id': endpoint.get('metadata', {}).get('id'),
            'name': endpoint.get('metadata', {}).get('name'),
            'project_id': endpoint.get('metadata', {}).get('parent_id'),
            'state': endpoint.get('status', {}).get('state'),
            'spot': endpoint.get('spec', {}).get('preemptible', False),
            'platform': endpoint.get('spec', {}).get('platform'),
            'preset': endpoint.get('spec', {}).get('preset'),
            'urls': endpoint.get('status', {}).get('public_endpoints', [])}


def endpoint():
    state = load_state()
    result = cli(['ai', 'endpoint', 'get', '--id', state['id']])
    if result.get('metadata', {}).get('parent_id') != state['project_id']:
        raise RuntimeError('Endpoint project differs from the saved selection.')
    return result


def connection(ep):
    urls = ep.get('status', {}).get('public_endpoints', [])
    if not urls:
        raise RuntimeError('Endpoint has no managed URL yet. Run wait.')
    url = next((x for x in urls if isinstance(x, str) and x.startswith('https://')), None)
    if not url:
        raise RuntimeError('No managed HTTPS URL was returned.')
    token = ep.get('spec', {}).get('auth_token')
    if not token:
        raise RuntimeError('This recipe needs token authentication. Use its create command, or set BASE_URL and ENDPOINT_TOKEN yourself for an existing secret-backed Endpoint.')
    return url.rstrip('/'), token


def version_check():
    p = subprocess.run([CLI, 'version'], capture_output=True, text=True,
                       env={**os.environ, 'AI_AGENT': os.environ.get('AI_AGENT') or 'cookbook'})
    try:
        v = tuple(int(x) for x in p.stdout.strip().split('.')[:3])
    except ValueError:
        v = ()
    if p.returncode or v < (0, 12, 303):
        raise RuntimeError('Install/update Nebius CLI to 0.12.303 or newer: nebius update. Current Spot pricing flags are required.')


def create(args):
    version_check()
    config_bytes = (ROOT / 'config' / 'endpoint.json').read_bytes()
    config = json.loads(config_bytes)
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    launch_options = {'subnet_id': args.subnet_id, 'spot_pricing_policy_id': args.spot_pricing_policy_id}
    command = ['ai', 'endpoint', 'create', '--parent-id', args.project_id, '--name', args.name,
               '--image', config['image'], '--platform', config['platform'], '--preset', config['preset'],
               '--container-port', str(config.get('container_port', 8000)), '--auth', 'token',
               '--disk-size', config.get('disk_size', '500Gi'), '--shm-size', config.get('shm_size', '16Gi'),
               '--preemptible', '--container-command', config['container_command']]
    command += (['--spot-pricing-policy-id', args.spot_pricing_policy_id]
                if args.spot_pricing_policy_id else ['--follows-spot-price'])
    cmd_args = config.get('args', [])
    if isinstance(cmd_args, list):
        if any(any(c.isspace() for c in str(x)) for x in cmd_args):
            raise RuntimeError('Container arguments must be individual words; put complex logic in a script.')
        cmd_args = ' '.join(str(x) for x in cmd_args)
    if cmd_args:
        command += ['--args', cmd_args]
    if args.subnet_id:
        command += ['--subnet-id', args.subnet_id]
    print(shlex.join([CLI, *command, '--dry-run' if args.dry_run else '--async']))
    print('PREEMPTIBLE GPU: running compute is billed, including image/model loading and idle time. '
          + ('The selected policy caps the hourly market price; capacity is not guaranteed.' if args.spot_pricing_policy_id
             else 'Following the Spot market price without a price cap; capacity is not guaranteed.'))
    if args.dry_run:
        cli([*command, '--dry-run'])
        print('Configuration validated; no Endpoint was created.')
        return
    if not args.yes:
        raise RuntimeError('Review the command and current pricing, then add --yes to launch paid compute.')
    existing = cli(['ai', 'endpoint', 'get-by-name', '--parent-id', args.project_id,
                    '--name', args.name], required=False)
    if existing and existing.get('metadata', {}).get('id'):
        if not existing.get('spec', {}).get('preemptible'):
            raise RuntimeError('That name exists on regular compute; select a new name for this Spot recipe.')
        previous = load_state() if STATE.exists() else {}
        if (previous.get('id') != existing['metadata']['id'] or previous.get('config_sha256') != config_hash
                or previous.get('launch_options') != launch_options):
            raise RuntimeError('That name is already in use outside this exact tracked configuration. Choose a new name, or deliberately attach its ID.')
        ep = existing
        print('Using the existing Spot Endpoint with this exact name; no duplicate was created.')
    else:
        cli([*command, '--async', '--retries', '1'])
        ep = None
        for _ in range(12):
            ep = cli(['ai', 'endpoint', 'get-by-name', '--parent-id', args.project_id,
                      '--name', args.name], required=False)
            if ep and ep.get('metadata', {}).get('id'):
                break
            time.sleep(2)
        if not ep or not ep.get('metadata', {}).get('id'):
            raise RuntimeError('Creation submitted but ID is not visible. Inspect the console by name; do not repeat create blindly.')
    info = summary(ep)
    if info['project_id'] != args.project_id or not info['spot']:
        raise RuntimeError('Returned workload does not match the requested project/Spot configuration.')
    save_state({'id': info['id'], 'project_id': args.project_id, 'model': config['model'],
                'config_sha256': config_hash, 'launch_options': launch_options})
    print(json.dumps(info, indent=2))


def wait(args):
    deadline = time.monotonic() + args.timeout
    last = None
    while time.monotonic() < deadline:
        ep = endpoint()
        state = ep.get('status', {}).get('state')
        if state != last:
            print('Endpoint:', state, flush=True)
            last = state
        if state in {'STOPPED', 'STOPPING', 'ERROR', 'DELETING', 'DELETED'}:
            raise RuntimeError('Endpoint stopped or failed. Inspect logs/capacity; restart it explicitly to continue.')
        if not ep.get('status', {}).get('public_endpoints'):
            time.sleep(min(10, max(0, deadline - time.monotonic())))
            continue
        url, token = connection(ep)
        try:
            req = urllib.request.Request(url + '/v1/models', headers={'Authorization': 'Bearer ' + token})
            with urllib.request.urlopen(req, timeout=20) as response:
                models = json.load(response)
            expected = load_state().get('model')
            if expected not in [x.get('id') for x in models.get('data', [])]:
                raise RuntimeError('Ready API serves a different model from this recipe.')
            print('Model API ready:', expected)
            return
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError('Endpoint authentication failed. Check the selected Endpoint and auth mode.') from exc
            time.sleep(min(10, max(0, deadline - time.monotonic())))
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(min(10, max(0, deadline - time.monotonic())))
    raise RuntimeError('Readiness timed out. Inspect logs, then stop the Endpoint if you are not continuing.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    c = sub.add_parser('create')
    c.add_argument('--project-id', required=True, type=resource_id('project'))
    c.add_argument('--name', required=True)
    c.add_argument('--subnet-id', type=resource_id('vpcsubnet'))
    c.add_argument('--spot-pricing-policy-id')
    c.add_argument('--dry-run', action='store_true')
    c.add_argument('--yes', action='store_true')
    a = sub.add_parser('attach')
    a.add_argument('--project-id', required=True)
    a.add_argument('--id', required=True)
    w = sub.add_parser('wait')
    w.add_argument('--timeout', type=int, default=1800)
    sub.add_parser('status')
    for action in ('stop', 'start'):
        sub.add_parser(action)
    r = sub.add_parser('run')
    r.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == 'create':
            create(args)
        elif args.action == 'attach':
            ep = cli(['ai', 'endpoint', 'get', '--id', args.id])
            info = summary(ep)
            if info['project_id'] != args.project_id or not info['spot']:
                raise RuntimeError('Attach requires a Spot Endpoint in the specified project.')
            config = json.loads((ROOT / 'config' / 'endpoint.json').read_text())
            save_state({'id': args.id, 'project_id': args.project_id, 'model': config['model']})
            print(json.dumps(info, indent=2))
        elif args.action == 'status':
            print(json.dumps(summary(endpoint()), indent=2))
        elif args.action == 'wait':
            wait(args)
        elif args.action in ('stop', 'start'):
            ep = endpoint()
            current = ep.get('status', {}).get('state')
            target = 'STOPPED' if args.action == 'stop' else 'RUNNING'
            if current == target:
                print('Endpoint already', target)
                return
            cli(['ai', 'endpoint', args.action, '--id', load_state()['id'], '--async', '--retries', '1'])
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                info = summary(endpoint())
                if info['state'] == target:
                    print(json.dumps(info, indent=2))
                    return
                time.sleep(5)
            raise RuntimeError('Lifecycle operation still pending. Check status before another action.')
        elif args.action == 'run':
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            if not command:
                raise RuntimeError('Supply a command after run --.')
            url, token = connection(endpoint())
            env = {**os.environ, 'BASE_URL': url, 'ENDPOINT_TOKEN': token,
                   'TOKEN': token, 'AI_AGENT': os.environ.get('AI_AGENT') or 'cookbook'}
            sys.exit(subprocess.call(command, env=env, cwd=ROOT))
    except (RuntimeError, ValueError, OSError) as exc:
        print('Error:', exc, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
