#!/usr/bin/env python3
"""Root command execution for the operator-owned scientific workbench.

Stdio only. Detached workers keep running when the MCP connection closes;
receipts and output live on disk and can be polled from a new connection.
"""
import json
import fcntl
import hashlib
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(os.environ.get('SCIENTIFIC_EXECUTION_DIR', '/data/hcls-execution'))
WORKSPACE = os.environ.get('SCIENTIFIC_WORKSPACE', '/workspace')


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def worker(directory):
    request = json.loads((directory / 'request.json').read_text())
    status = {'job_id': directory.name, 'status': 'running', 'cwd': request['cwd'],
              'uid': os.geteuid(), 'started_at': time.time(),
              'worker_pid': os.getpid(), 'worker_start': Path('/proc/self/stat').read_text().split()[21]}
    save(directory / 'status.json', status)
    try:
        with (directory / 'output.log').open('wb') as output:
            process = subprocess.Popen(['/bin/bash', '-lc', request['command']],
                cwd=request['cwd'], stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=request['timeout_seconds'] or None)
                status.update(status='completed' if code == 0 else 'failed', exit_code=code)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                status.update(status='timed_out', exit_code=process.returncode)
    except Exception as error:
        status.update(status='failed', error=str(error))
    status['finished_at'] = time.time()
    save(directory / 'status.json', status)


def bounded_number(args, name, default, maximum):
    value = args.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f'{name} must be an integer from 0 to {maximum}.')
    return value


def read_job(args):
    job_id = str(uuid.UUID(args['job_id']))
    directory = ROOT / job_id
    if not (directory / 'request.json').is_file():
        raise ValueError('Unknown execution job ID.')
    offset = bounded_number(args, 'offset', 0, 2**63 - 1)
    wait = bounded_number(args, 'wait_seconds', 0, 10)
    limit = bounded_number(args, 'max_bytes', 4000, 32000)
    deadline = time.monotonic() + wait
    while True:
        path = directory / 'status.json'
        status = json.loads(path.read_text()) if path.exists() else {'job_id': job_id, 'status': 'starting'}
        if status['status'] == 'running':
            try:
                alive = Path(f"/proc/{status['worker_pid']}/stat").read_text().split()[21] == status['worker_start']
            except (OSError, KeyError, IndexError):
                alive = False
            if not alive:
                status = json.loads(path.read_text())
                if status['status'] == 'running':
                    status.update(status='interrupted', error='Execution worker exited without a final receipt; inspect saved output before rerunning.')
        if status['status'] not in ('starting', 'running') or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    output = directory / 'output.log'
    data = b''
    if output.exists():
        with output.open('rb') as stream:
            stream.seek(offset)
            data = stream.read(limit)
    total_bytes = output.stat().st_size if output.exists() else 0
    status.update(output=data.decode('utf-8', errors='replace'), next_offset=offset + len(data),
                  output_size_bytes=total_bytes, returned_bytes=len(data),
                  output_path=str(output), more_output=output.exists() and output.stat().st_size > offset + len(data))
    if status['more_output']:
        status['output_guidance'] = ('Full output is retained at output_path. Analyze that file locally and print concise metrics; '
                                     'read another chunk only when its text is needed. Never paste whole datasets or helper source into chat.')
    return status


def execute(args):
    command = args.get('command')
    if not isinstance(command, str) or not command.strip():
        raise ValueError('command must be a nonempty Bash command or script.')
    cwd = args.get('cwd', WORKSPACE)
    if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
        raise ValueError('cwd must be an existing absolute directory.')
    timeout = bounded_number(args, 'timeout_seconds', 300, 604800)
    wait = bounded_number(args, 'wait_seconds', 5, 10)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = ROOT / str(uuid.uuid4())
    directory.mkdir(mode=0o700)
    save(directory / 'request.json', {'command': command, 'cwd': cwd, 'timeout_seconds': timeout})
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(directory)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    return read_job({'job_id': directory.name, 'wait_seconds': wait})


def run_scientific_workflow(args):
    """Typed launch of the existing durable client, not a new model transport."""
    workspace = Path(WORKSPACE).resolve()
    def local_path(name):
        value = args.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(name + ' must be a workspace-relative path.')
        path = (workspace / value).resolve()
        if not path.is_relative_to(workspace):
            raise ValueError(name + ' must be inside the mounted workspace.')
        return path
    plan_path, output = local_path('plan_file'), local_path('output_directory')
    if not plan_path.is_file():
        raise ValueError('plan_file does not exist: ' + str(plan_path))
    resume = args.get('resume', False)
    if not isinstance(resume, bool):
        raise ValueError('resume must be a boolean.')
    python = os.environ.get('SCIENTIFIC_CLIENT_PYTHON', '/opt/scientific-client/bin/python')
    runner = os.environ.get('SCIENTIFIC_WORKFLOW_RUNNER', '/opt/bionemo/scientific-workflow.py')
    command = [python, runner, '--plan', str(plan_path), '--output', str(output), '--wait-seconds', '0']
    plan_bytes = plan_path.read_bytes()
    identity = hashlib.sha256(plan_bytes + b'\0' + str(output).encode()).hexdigest()
    index_dir = ROOT / 'workflow-index'
    index_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    index = index_dir / (identity + '.json')
    with (index_dir / (identity + '.lock')).open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = json.loads(index.read_text()) if index.exists() else {}
        if previous.get('job_id'):
            current = read_job({'job_id': previous['job_id']})
            if current['status'] in ('starting', 'running', 'completed') or not resume:
                return {**current, 'workflow_identity': identity, 'reused_existing_job': True,
                        'resume_required': current['status'] not in ('starting', 'running', 'completed')}
        checked = subprocess.run(command + ['--validate-only'], capture_output=True, text=True, timeout=60)
        if checked.returncode:
            raise ValueError('Workflow file preflight failed before admission. ' + checked.stderr[-3000:])
        preflight = json.loads(checked.stdout)
        # Preserve the exact plan bytes used for the preflight and eventual job.
        if identity != hashlib.sha256(plan_path.read_bytes() + b'\0' + str(output).encode()).hexdigest():
            raise ValueError('Plan changed during preflight; no workflow was started.')
        frozen_plan = index_dir / (identity + '.plan.json')
        frozen_plan.write_bytes(plan_bytes)
        command[command.index('--plan') + 1] = str(frozen_plan)
        started = execute({'command': shlex.join(command), 'cwd': str(workspace),
                           'timeout_seconds': 0, 'wait_seconds': 1})
        save(index, {'job_id': started['job_id'], 'plan_file': str(plan_path),
                     'output_directory': str(output), 'previous_job_id': previous.get('job_id')})
        return {**started, 'workflow_identity': identity, 'preflight_steps': preflight['steps'],
                'preflight_files': len(preflight['files']), 'reused_existing_job': False,
                'guidance': 'Poll this execution job; model operations and exact receipts remain in the workflow output. Completion still requires scientific analysis.'}


TOOLS = [
    {'name': 'run_scientific_workflow',
     'description': 'Preferred launch for prepared scientific studies: give an existing workspace-relative scientific-workflow/v1 JSON plan file and output directory, not shell flags. Validates every input/source/parameter file before any upload or inference, then uses the existing native/batch clients sequentially under unchanged caller policy. Native input files may contain full inline arrays outside chat context. Saves one execution job; repeated calls return that existing job. Poll read_execution. Use resume=true only after inspecting an interrupted job; original model receipts/idempotency keys are preserved and ambiguous admissions are never silently retried. File preflight is not proof of scientific validity.',
     'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'openWorldHint': True},
     'inputSchema': {'type': 'object', 'additionalProperties': False,
        'required': ['plan_file', 'output_directory'], 'properties': {
            'plan_file': {'type': 'string'}, 'output_directory': {'type': 'string'},
            'resume': {'type': 'boolean', 'default': False}}}},
    {'name': 'execute_command',
     'description': 'Execute Bash as root in this application container. Install packages with apt-get/pip/npm, run Python, download internet resources, read/write any container path and mounted storage. /workspace is the team Object Storage bucket mount and the durable location for team files; use byte copies, not chmod/copystat. This is real execution, not a code suggestion. For long work save job_id and use read_execution; do not submit again. Returns 4000 output bytes by default with a full log file pointer; compute summaries locally instead of dumping source/data. timeout_seconds=0 disables the deadline. Root applies to the container and its mounts, not the cloud host. Never print credentials.',
     'annotations': {'readOnlyHint': False, 'destructiveHint': True, 'openWorldHint': True},
     'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['command'],
        'properties': {'command': {'type': 'string'}, 'cwd': {'type': 'string'},
            'timeout_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 604800, 'default': 300},
            'wait_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 10, 'default': 5}}}},
    {'name': 'read_execution',
     'description': 'Resume a command by its job_id, including after reconnecting. Returns status, exit code and a bounded output chunk. Pass next_offset as offset to read the next chunk; poll running jobs without resubmitting commands. Receipts survive MCP restarts; running processes do not survive a container restart.',
     'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False},
     'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['job_id'],
        'properties': {'job_id': {'type': 'string'}, 'offset': {'type': 'integer', 'minimum': 0},
            'max_bytes': {'type': 'integer', 'minimum': 0, 'maximum': 32000},
            'wait_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 10}}}},
]


def main():
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if 'id' not in request:
                continue
            method = request.get('method')
            if method == 'initialize':
                result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'environment-execution', 'version': '1.0'}}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': TOOLS}
            elif method == 'tools/call':
                params = request['params']
                handler = {'execute_command': execute, 'read_execution': read_job,
                           'run_scientific_workflow': run_scientific_workflow}[params['name']]
                try:
                    value = handler(params.get('arguments', {}))
                    result = {'content': [{'type': 'text', 'text': json.dumps(value)}],
                              'isError': value['status'] in ('failed', 'timed_out', 'interrupted')}
                except (ValueError, KeyError, OSError) as error:
                    result = {'isError': True, 'content': [{'type': 'text', 'text': str(error)}]}
            else:
                raise ValueError('Unknown MCP method.')
            reply = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
        except Exception:
            reply = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                     'error': {'code': -32602, 'message': 'Invalid execution request.'}}
        print(json.dumps(reply), flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]))
    else:
        main()
