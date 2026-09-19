"""Explicit negative clinical outcomes, without swallowing genuine failures."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import scientific_study as study
from scientific_receipts import verify_file
from scientific_study_schema import PHASE_OUTPUTS

HERE = Path(__file__).parent


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    for name, value in {
        'SCIENTIFIC_WORKSPACE': str(tmp_path),
        'SCIENTIFIC_MODELS_MCP_URL': 'https://platform.test/mcp',
        'SCIENTIFIC_MODELS_API_KEY': 'private-fixture',
        'SEED_DEFAULT_USER_EMAIL': 'clinical@example.test',
        'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
        'CLINICAL_REPORT_API_KEY': 'private-provider-fixture',
        'SCIENTIFIC_CLINICAL_SCRIPT': str(HERE / 'skills/clinical-documentation/scripts/clinical_report.py'),
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / 'source.txt').write_text('Unclear fragment, retained exactly.\n')
    return tmp_path


def clinical_step(root, allowed=None):
    value = {'id': 'clinical', 'kind': 'clinical', 'source': str(root / 'source.txt'),
             'source_type': 'transcript', 'language': 'de',
             'report_model': 'Qwen/Qwen3-235B-A22B-Instruct-2507'}
    if allowed is not None:
        value['allow_no_report'] = allowed
    return value


def fixture_outcome(root, state='no_supported_clinical_facts'):
    checkpoint = root / 'fixture-checkpoint'
    checkpoint.mkdir(exist_ok=True)
    contents = {'transcript.txt': (root / 'source.txt').read_bytes(),
                'review.json': b'{"withheld":[{"source":"Unclear fragment"}]}\n',
                'coverage.json': b'{"supported_facts":0,"complete":false}\n',
                'run.json': json.dumps({'status': state, 'clinical_validation': False}).encode()}
    if state == 'completed':
        contents.update({'report.md': b'# Unchanged draft\n', 'document.json': b'{"facts":[]}\n',
                         'follow-up.md': b'# Review required\n'})
    files = {}
    for name, raw in contents.items():
        path = checkpoint / name
        path.write_bytes(raw)
        files[name] = study.measure(path)
    return {'state': state, 'files': files, 'operations': [], 'active_operations': []}


def install_boundary(monkeypatch, outcome, returncode=0):
    actual_run = subprocess.run
    calls = []

    def boundary(command, *args, **kwargs):
        if len(command) > 1 and str(command[1]).endswith('/scientific_clinical.py'):
            calls.append(command)
            return SimpleNamespace(returncode=returncode, stdout=json.dumps(outcome).encode())
        return actual_run(command, *args, **kwargs)

    monkeypatch.setattr(study.subprocess, 'run', boundary)
    return calls


def record(root):
    return {'id': 'c56a08bf-e3f8-4683-83ed-e039354fba44', 'output_directory': str(root / 'output')}


@pytest.mark.parametrize('allowed', [None, False])
def test_default_negative_remains_failure(mounted, monkeypatch, allowed):
    install_boundary(monkeypatch, fixture_outcome(mounted))
    result = study.run_clinical(clinical_step(mounted, allowed), record(mounted))
    assert result['state'] == 'failed'
    assert 'no report was produced' in result['failure']['message']
    assert not list((mounted / 'output').glob('**/clinical-outcome.json'))


def test_explicit_negative_preserves_evidence_and_publishes_distinct_outcome(mounted, monkeypatch):
    original = fixture_outcome(mounted)
    calls = install_boundary(monkeypatch, original)
    result = study.run_clinical(clinical_step(mounted, True), record(mounted))
    assert len(calls) == 1
    assert result['state'] == 'completed' and result['report_produced'] is False
    assert set(result['files']) == set(original['files']) | {'clinical-outcome.json', 'clinical-outcome.md'}
    for name, info in result['files'].items():
        verify_file(Path(info['path']), info)
        if name in original['files']:
            assert Path(info['path']).read_bytes() == Path(original['files'][name]['path']).read_bytes()
    outcome = json.loads(Path(result['files']['clinical-outcome.json']['path']).read_bytes())
    assert outcome['schema'] == 'scientific-clinical-outcome/v1'
    assert outcome['outcome'] == 'no_supported_clinical_facts'
    assert outcome['no_report_explicitly_allowed'] is True
    assert outcome['clinical_validation'] is False
    assert outcome['source'] == study.measure(mounted / 'source.txt')
    assert set(outcome['files']) == set(original['files'])
    assert 'not a finding of absent illness' in Path(result['files']['clinical-outcome.md']['path']).read_text()
    assert set(PHASE_OUTPUTS['clinical'][0]) <= result['files'].keys()


@pytest.mark.parametrize('allowed', [False, True])
def test_normal_draft_bytes_are_unchanged(mounted, monkeypatch, allowed):
    original = fixture_outcome(mounted, 'completed')
    install_boundary(monkeypatch, original)
    result = study.run_clinical(clinical_step(mounted, allowed), record(mounted))
    assert result['state'] == 'completed' and result['report_produced'] is True
    for name, info in original['files'].items():
        assert Path(result['files'][name]['path']).read_bytes() == Path(info['path']).read_bytes()


@pytest.mark.parametrize('state,expected', [('failed', 'failed'), ('cancelled', 'cancelled'),
    ('pending', 'clinical_pending'), ('admission_unknown', 'needs_attention')])
def test_opt_in_never_converts_other_states(mounted, monkeypatch, state, expected):
    install_boundary(monkeypatch, fixture_outcome(mounted, state))
    result = study.run_clinical(clinical_step(mounted, True), record(mounted))
    assert result['state'] == expected
    assert not list((mounted / 'output').glob('**/clinical-outcome.json'))


@pytest.mark.parametrize('defect', ['missing', 'corrupt', 'report', 'active', 'runner'])
def test_opt_in_requires_complete_verified_negative_evidence(mounted, monkeypatch, defect):
    original = fixture_outcome(mounted)
    if defect == 'missing':
        del original['files']['review.json']
    elif defect == 'corrupt':
        Path(original['files']['review.json']['path']).write_text('changed')
    elif defect == 'report':
        original['files']['report.md'] = original['files']['transcript.txt']
    elif defect == 'active':
        original['active_operations'] = [{'operation_id': 'still-running'}]
    install_boundary(monkeypatch, original, int(defect == 'runner'))
    with pytest.raises((ValueError, RuntimeError)):
        study.run_clinical(clinical_step(mounted, True), record(mounted))


def whole_plan(root, allowed=True):
    return {'schema': study.SCHEMA, 'title': 'Explicit source-only negative outcome',
            'steps': [clinical_step(root, allowed),
                      {'id': 'report', 'kind': 'analysis', 'method': 'report',
                       'arguments': {'title': 'Observed clinical outcome', 'sections': [
                           {'title': 'Unchanged negative outcome', 'format': 'markdown',
                            'file': {'step': 'clinical', 'file': 'clinical-outcome.md'}}]}}],
            'deliverables': [{'name': name, 'role': 'report' if name == 'report.md' else 'provenance',
                              'source': {'step': 'report' if name == 'report.md' else 'clinical', 'file': name}}
                             for name in ['report.md', 'clinical-outcome.json', 'transcript.txt', 'review.json']]}


def test_nonboolean_permission_rejected_before_admission(mounted):
    with pytest.raises(ValueError, match='Study shape'):
        study.submit(whole_plan(mounted, 'true'), mounted / 'invalid')
    assert not study.list_studies()


def test_full_study_resumes_in_new_process_and_publishes_without_another_clinical_call(mounted, monkeypatch):
    original = fixture_outcome(mounted)
    calls = install_boundary(monkeypatch, original)
    started = study.submit(whole_plan(mounted), mounted / 'complete-study')
    first = asyncio.run(study.advance(started['id']))
    assert first['completed_steps'] == ['clinical'] and first['state'] == 'running'
    assert len(calls) == 1
    driver = '''import asyncio,json,sys
import scientific_study as study
def unexpected(*args,**kwargs):
    raise AssertionError("Completed clinical stage must not run again")
study.run_clinical=unexpected
result=asyncio.run(study.advance(sys.argv[1]))
print(json.dumps(result))
'''
    env = {**os.environ, 'PYTHONPATH': str(HERE)}
    for _ in range(2):
        process = subprocess.run([sys.executable, '-c', driver, started['id']], env=env,
                                 capture_output=True, text=True, check=True)
        terminal = json.loads(process.stdout)
    assert terminal['state'] == 'completed', terminal.get('failure')
    assert terminal['completed_steps'] == ['clinical', 'report']
    assert len(terminal['artifacts']) == 4
    for info in terminal['artifacts']:
        verify_file(Path(info['path']), info)
        assert info['size_bytes'] > 0
    report = next(item for item in terminal['artifacts'] if item['name'] == 'report.md')
    assert 'No supported clinical facts' in Path(report['path']).read_text()
    assert 'not a finding of absent illness' in Path(report['path']).read_text()
    manifest = json.loads(Path(terminal['manifest']['path']).read_bytes())
    assert manifest['clinical_operations'] == []
    assert manifest['scientific_validity_claim'] is False
    assert len(calls) == 1
    assert study.get(started['id'])['state'] == 'completed'
