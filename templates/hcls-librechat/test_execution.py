"""Exercise actual shell jobs and reconnects over the stdio protocol."""
import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).with_name('execution-mcp.py')


def call(tmp_path, name, args):
    env = dict(os.environ, SCIENTIFIC_EXECUTION_DIR=str(tmp_path / 'jobs'),
               SCIENTIFIC_WORKSPACE=str(tmp_path))
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': name, 'arguments': args}}
    proc = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(request) + '\n',
                          env=env, text=True, capture_output=True, check=True)
    result = json.loads(proc.stdout)['result']
    return result, json.loads(result['content'][0]['text'])


def test_actual_python_file_and_failed_exit(tmp_path):
    _, result = call(tmp_path, 'execute_command', {
        'command': "python3 -c \"from pathlib import Path; Path('result.txt').write_text(str(6 * 7))\""})
    assert result['status'] == 'completed'
    assert (tmp_path / 'result.txt').read_text() == '42'
    envelope, result = call(tmp_path, 'execute_command', {'command': 'echo failure; exit 7'})
    assert envelope['isError'] is True
    assert result['exit_code'] == 7
    assert result['output'] == 'failure\n'


def test_job_continues_after_mcp_disconnect_and_output_is_paged(tmp_path):
    _, started = call(tmp_path, 'execute_command', {
        'command': "sleep 0.3; python3 -c \"print('x' * 40000, end='')\"", 'wait_seconds': 0})
    _, result = call(tmp_path, 'read_execution', {'job_id': started['job_id'], 'wait_seconds': 3})
    assert result['status'] == 'completed'
    assert len(result['output']) == 12000
    assert result['more_output'] is True
    _, rest = call(tmp_path, 'read_execution', {'job_id': started['job_id'],
        'offset': result['next_offset'], 'max_bytes': 32000})
    assert len(rest['output']) == 28000
    assert rest['more_output'] is False


def test_command_deadline(tmp_path):
    envelope, result = call(tmp_path, 'execute_command', {
        'command': 'sleep 30', 'timeout_seconds': 1, 'wait_seconds': 3})
    assert envelope['isError'] is True
    assert result['status'] == 'timed_out'

