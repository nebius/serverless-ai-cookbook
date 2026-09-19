"""Typed file uploader delegates exact mounted bytes to one sequential client."""
import importlib.util
import json
import sys

import pytest

from test_execution import call, SCRIPT


def module(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('upload_execution_test', SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    monkeypatch.setattr(value, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(value, 'ROOT', tmp_path / 'jobs')
    return value


def fixture(tmp_path, monkeypatch):
    # A real subprocess fixture detects overlapping reservations. Network and
    # transfer correctness are covered separately by test_artifact_file_client.
    helper = tmp_path / 'fixture uploader.py'
    helper.write_text('''import argparse,hashlib,json,os,time
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('model','file','media-type','output-dir','idempotency-key'):p.add_argument('--'+k,required=True)
a=p.parse_args(); root=Path(a.file).parent; out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
dest=out/'artifact.json'
if dest.exists():print('reused original artifact');raise SystemExit(0)
active=root/'active-reservation'
fd=os.open(active,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
try:
    time.sleep(.05)
    if (root/'fail-second-once').exists() and a.model=='model-two':
        (root/'fail-second-once').unlink();raise SystemExit(11)
    data=Path(a.file).read_bytes()
    ref={'artifact_id':a.idempotency_key,'sha256':hashlib.sha256(data).hexdigest(),
         'size_bytes':len(data),'media_type':a.media_type,'compression':'none'}
    dest.write_text(json.dumps(ref))
    (out/'transferred-once').write_text(a.idempotency_key)
    print(json.dumps({'artifact':ref}))
finally:os.close(fd);active.unlink()
''')
    monkeypatch.setenv('SCIENTIFIC_CLIENT_PYTHON', sys.executable)
    monkeypatch.setenv('SCIENTIFIC_UPLOAD_HELPER', str(helper))
    (tmp_path / 'first actual α.bin').write_bytes(b'actual\x00bytes\r\n')
    (tmp_path / 'second.json').write_text('{"actual":"β"}')
    return {'output_directory': 'study uploads', 'files': [
        {'id': 'one', 'model': 'model-one', 'file': 'first actual α.bin',
         'media_type': 'application/octet-stream', 'idempotency_key': 'original-upload-one'},
        {'id': 'two', 'model': 'model-two', 'file': 'second.json',
         'media_type': 'application/json', 'idempotency_key': 'original-upload-two'}]}


def test_actual_paths_metadata_sequential_uploads_and_repeat_job(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    _, first = call(tmp_path, 'upload_workspace_files', args)
    assert first['status'] == 'completed' and first['preflight_files'] == 2
    _, second = call(tmp_path, 'upload_workspace_files', args)
    assert second['job_id'] == first['job_id'] and second['reused_existing_job']
    assert len(list((tmp_path / 'jobs').glob('*/request.json'))) == 1
    records = [json.loads((tmp_path / 'study uploads' / name / 'artifact.json').read_text()) for name in ('one', 'two')]
    assert records[0]['size_bytes'] == len(b'actual\x00bytes\r\n')
    assert records[1]['media_type'] == 'application/json'
    assert records[1]['artifact_id'] == 'original-upload-two'
    assert not (tmp_path / 'active-reservation').exists()


def test_all_files_preflight_before_first_reservation(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    args['files'][1]['file'] = 'missing second file'
    execution = module(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='not an existing file'):
        execution.upload_workspace_files(args)
    assert not (tmp_path / 'study uploads').exists()
    assert not list((tmp_path / 'jobs').glob('*/request.json'))


@pytest.mark.parametrize('change', ['bytes', 'media_type', 'idempotency_key'])
def test_changed_identity_never_implicitly_resubmits(tmp_path, monkeypatch, change):
    args = fixture(tmp_path, monkeypatch)
    _, first = call(tmp_path, 'upload_workspace_files', args)
    assert first['status'] == 'completed'
    if change == 'bytes':
        (tmp_path / 'first actual α.bin').write_bytes(b'different bytes')
    else:
        args['files'][0][change] = 'different-value'
    execution = module(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='bytes or metadata changed'):
        execution.upload_workspace_files(args)
    assert len(list((tmp_path / 'jobs').glob('*/request.json'))) == 1


def test_failed_sequence_stops_and_only_explicit_resume_reuses_receipts(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    (tmp_path / 'fail-second-once').touch()
    envelope, failed = call(tmp_path, 'upload_workspace_files', args)
    assert envelope['isError'] and failed['status'] == 'failed'
    original = (tmp_path / 'study uploads/one/artifact.json').read_bytes()
    _, unchanged = call(tmp_path, 'upload_workspace_files', args)
    assert unchanged['job_id'] == failed['job_id'] and unchanged['resume_required']
    _, recovered = call(tmp_path, 'upload_workspace_files', {**args, 'resume': True})
    assert recovered['status'] == 'completed' and recovered['job_id'] != failed['job_id']
    assert (tmp_path / 'study uploads/one/artifact.json').read_bytes() == original
    assert json.loads((tmp_path / 'study uploads/two/artifact.json').read_text())['artifact_id'] == 'original-upload-two'


def test_schema_is_typed_and_seeded_for_all_execution_agents(tmp_path, monkeypatch):
    from jsonschema import Draft202012Validator, ValidationError
    args = fixture(tmp_path, monkeypatch)
    execution = module(tmp_path, monkeypatch)
    schema = next(tool['inputSchema'] for tool in execution.TOOLS if tool['name'] == 'upload_workspace_files')
    Draft202012Validator(schema).validate(args)
    args['files'][0]['file'] = {'bytes': 'not a path'}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(args)
    assert 'upload_workspace_files_mcp_environment-execution' in SCRIPT.with_name('seed-workbench.js').read_text()


def test_worker_rechecks_frozen_bytes_before_any_client_call(tmp_path, monkeypatch):
    execution = module(tmp_path, monkeypatch)
    source = tmp_path / 'source.json'
    source.write_text('changed')
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'files': [{'file': str(source), 'size_bytes': 7,
        'mtime_ns': 0, 'id': 'one'}]}))
    monkeypatch.setattr(execution.subprocess, 'run', lambda *a, **k: pytest.fail('No reservation after source change'))
    with pytest.raises(ValueError, match='Source changed'):
        execution.upload_worker(plan)


def test_request_never_hashes_mounted_files_before_returning_job(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    execution = module(tmp_path, monkeypatch)
    monkeypatch.setattr(execution, 'file_digest', lambda _: pytest.fail('Hashing belongs to detached worker'))
    monkeypatch.setattr(execution, 'execute', lambda _: {'job_id': 'detached', 'status': 'running'})
    result = execution.upload_workspace_files(args)
    assert result['job_id'] == 'detached'
    plan = json.loads(next((tmp_path / 'jobs/upload-index').glob('*.plan.json')).read_text())
    assert all('sha256' not in item for item in plan['files'])


def test_worker_rejects_same_stat_changed_bytes_against_retained_identity(tmp_path, monkeypatch):
    import os
    args = fixture(tmp_path, monkeypatch)
    _, result = call(tmp_path, 'upload_workspace_files', args)
    assert result['status'] == 'completed'
    plan_path = next((tmp_path / 'jobs/upload-index').glob('*.plan.json'))
    frozen = json.loads(plan_path.with_suffix('.bytes.json').read_text())
    source = tmp_path / 'first actual α.bin'
    stat = source.stat()
    source.write_bytes(b'x' * stat.st_size)
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    execution = module(tmp_path, monkeypatch)
    monkeypatch.setattr(execution.subprocess, 'run', lambda *a, **k: pytest.fail('No new client call'))
    with pytest.raises(ValueError, match='retained upload plan'):
        execution.upload_worker(plan_path)
    assert json.loads(plan_path.with_suffix('.bytes.json').read_text()) == frozen
