"""Reuse the report validator before admission, not after a failed study."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import scientific_study as study
import scientific_workflow_draft as draft
from scientific_study_schema import PHASE_OUTPUT_DIRECTORIES, describe_workflow

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('preflight_report', ROOT / 'report-assembly.py')
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_EXECUTION_DIR', str(tmp_path / 'jobs'))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-only')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'semantic-preflight@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model transport is needed'))
    return tmp_path


def record(identity='a'):
    return {'id': identity, 'status': 'completed', 'state': {
        'config': {'profile_id': 'profile', 'clinician_model': 'clinician'},
        'transcript': [{'role': 'patient', 'content': 'Literal — unmodified source.'}],
        'judgment': {'model': 'retained-judge', 'judgment': {'named criterion': 4}}}}


def files(folder, values):
    paths = []
    for index, value in enumerate(values):
        path = folder / f'record-{index}.json'
        path.write_text(json.dumps(value, ensure_ascii=False, indent=3) + '\n')
        paths.append(str(path))
    return paths


def plan(paths):
    return {'schema': study.SCHEMA, 'title': 'Retained records', 'steps': [
        {'id': 'analysis', 'kind': 'analysis', 'method': 'mindeval',
         'arguments': {'title': 'Retained records', 'records': paths}}],
        'deliverables': [{'name': 'report', 'role': 'report', 'source': {'step': 'analysis', 'file': 'report.md'}}]}


def compose_args(folder, value):
    return {'draft_directory': str(folder / 'draft'), 'title': value['title'],
            'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True}


def call_stdio(name, arguments):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': name, 'arguments': arguments}}
    result = subprocess.run([sys.executable, str(ROOT / 'execution-mcp.py')],
                            input=json.dumps(request) + '\n', text=True, capture_output=True,
                            env=os.environ.copy(), check=True, timeout=20)
    return json.loads(result.stdout)['result']


@pytest.mark.parametrize('invalid_index', [0, 1, 5])
def test_every_existing_record_checked_before_draft_finalize_and_admission(mounted, invalid_index):
    values = [record(str(index)) for index in range(6)]
    values[invalid_index] = {'id': str(invalid_index), 'summary': 'Compact export, not a native record'}
    value = plan(files(mounted, values))
    before = copy.deepcopy(value)
    with pytest.raises(ValueError, match='full retained run.state/config') as failed:
        study.submit(value, mounted / 'final')
    assert f'records[{invalid_index}]' in str(failed.value)
    assert 'Select the full saved native record' in str(failed.value)
    assert value == before and study.list_studies() == [] and not (mounted / 'final').exists()
    saved = draft.compose(compose_args(mounted, value))
    assert saved['finalized'] is False and saved['inference_submitted'] is False
    assert saved['validation_error'] == str(failed.value)
    assert json.loads(Path(saved['plan_file']).read_bytes()) == before
    assert study.list_studies() == []


@pytest.mark.parametrize('judgment', [None, {}, {'judgment': {'native criterion': 2}},
                                     {'model': 'judge', 'judgment': {'first': 3, 'second': 6}}])
def test_valid_native_and_missing_judgments_are_unchanged(mounted, judgment):
    original = record()
    original['state']['judgment'] = judgment
    paths = files(mounted, [original])
    value = plan(paths)
    before = copy.deepcopy(value)
    frozen = study.validate(value)
    assert set(frozen) == set(paths) and value == before
    assert frozen[paths[0]]['sha256'] == hashlib.sha256(Path(paths[0]).read_bytes()).hexdigest()
    finalized = draft.compose(compose_args(mounted, value))
    assert finalized['finalized'] and finalized['validation_error'] is None
    saved = study.submit(value, mounted / 'final')
    assert study.submit(value, mounted / 'final')['id'] == saved['id']
    asyncio.run(study.advance(saved['id']))
    completed = asyncio.run(study.advance(saved['id']))
    assert completed['state'] == 'completed'
    outputs = completed['steps']['analysis']['files']
    assert Path(outputs['records/000.json']['path']).read_bytes() == Path(paths[0]).read_bytes()
    measured = json.loads(Path(outputs['measurements.json']['path']).read_bytes())
    _, _, expected = report.load_mindeval_records(paths, mounted)
    assert measured['measurements'] == expected['measurements']


@pytest.mark.parametrize('mutation,match', [
    (lambda item: item['state'].update(config=[]), 'state/config'),
    (lambda item: item['state'].update(transcript=[]), 'nonempty transcript'),
    (lambda item: item['state'].update(transcript=[{'role': 'patient', 'content': 7}]), 'literal content'),
    (lambda item: item['state'].update(judgment=[]), 'judgment envelope'),
    (lambda item: item['state'].update(judgment=False), 'judgment envelope'),
    (lambda item: item['state'].update(judgment=0), 'judgment envelope'),
    (lambda item: item['state'].update(judgment=''), 'judgment envelope'),
    (lambda item: item['state'].update(judgment={'judgment': []}), 'score mapping'),
    (lambda item: item['state'].update(judgment={'judgment': {'criterion': 7}}), '1–6'),
    (lambda item: item.pop('id'), 'IDs must be present'),
])
def test_same_existing_helper_failures_happen_before_admission(mounted, mutation, match):
    native = record()
    mutation(native)
    paths = files(mounted, [native])
    with pytest.raises(ValueError, match=match) as reference:
        report.load_mindeval_records(paths, mounted)
    with pytest.raises(ValueError, match=match) as admission:
        study.submit(plan(paths), mounted / 'final')
    assert str(admission.value) == 'Step analysis: ' + str(reference.value)
    assert study.list_studies() == [] and not (mounted / 'final').exists()


def test_duplicate_ids_fail_as_one_combined_record_set(mounted):
    paths = files(mounted, [record('same'), record('same')])
    with pytest.raises(ValueError, match='duplicate records are not independent'):
        study.submit(plan(paths), mounted / 'final')
    assert study.list_studies() == []


def test_report_publisher_uses_shared_read_only_loader(mounted, monkeypatch):
    paths = files(mounted, [record()])
    loader = report.load_mindeval_records
    seen = []
    def observed(records, base_directory):
        seen.append((records, base_directory))
        return loader(records, base_directory)
    monkeypatch.setattr(report, 'load_mindeval_records', observed)
    source = mounted / 'report-plan.json'
    source.write_text(json.dumps({'title': 'Retained records', 'records': paths}))
    report.publish_mindeval(source, mounted / 'published')
    assert seen == [(paths, mounted)]


def test_deferred_records_stay_deferred_but_literal_records_are_checked(mounted):
    paths = files(mounted, [record()])
    value = plan([{'step': 'prepare', 'file': 'future.json'}, *paths])
    value['steps'].insert(0, {'id': 'prepare', 'kind': 'preparation', 'method': 'write-json',
                            'arguments': {'filename': 'future.json', 'value': record('future')}})
    assert set(study.validate(value)) == set(paths)
    Path(paths[0]).write_text('{"summary":"not full"}')
    with pytest.raises(ValueError, match='state/config'):
        study.validate(value)


def test_changed_bytes_between_hash_and_semantic_read_are_rejected(mounted, monkeypatch):
    paths = files(mounted, [record()])
    measure = study.measure
    def changed(path):
        result = measure(path)
        Path(path).write_text(json.dumps(record('different-valid-run')))
        return result
    monkeypatch.setattr(study, 'measure', changed)
    with pytest.raises(ValueError, match='changed during preflight'):
        study.submit(plan(paths), mounted / 'final')
    assert study.list_studies() == []


@pytest.mark.parametrize('method,filename', [('mindeval', 'records'), ('mindeval', 'transcripts'),
    ('mindeval', 'records/'), ('mindeval', 'records/.'), ('mindeval', '.'),
    ('report', 'sources'), ('report', 'sources/.'), ('report', 'unknown/')])
def test_known_or_explicit_directory_deliverables_fail_before_admission(mounted, method, filename):
    if method == 'mindeval':
        value = plan(files(mounted, [record()]))
    else:
        source = mounted / 'source.md'
        source.write_text('Retained measurements only.\n')
        value = plan([])
        value['steps'] = [{'id': 'analysis', 'kind': 'analysis', 'method': 'report',
                          'arguments': {'title': 'Measured report', 'sections': [
                              {'title': 'Source', 'file': str(source), 'format': 'markdown'}]}}]
    value['deliverables'].append({'name': 'support', 'role': 'support',
                                  'source': {'step': 'analysis', 'file': filename}})
    with pytest.raises(ValueError, match='output directory'):
        study.submit(value, mounted / 'final')
    assert not (mounted / 'final').exists() and study.list_studies() == []
    assert not draft.compose(compose_args(mounted, value))['finalized']


def test_literal_directory_and_concrete_helper_files(mounted):
    value = plan(files(mounted, [record()]))
    value['deliverables'].append({'name': 'record', 'role': 'support',
                                  'source': {'step': 'analysis', 'file': 'records/000.json'}})
    assert study.validate(value)
    value['deliverables'][-1]['source'] = str(mounted)
    with pytest.raises(ValueError, match='directory, not a file'):
        study.validate(value)


def test_unknown_custom_outputs_are_not_guessed_from_helper_directories(mounted):
    script = mounted / 'analysis.py'
    script.write_text('# Saved user analysis, not executed during validation.\n')
    value = plan([])
    value['steps'] = [{'id': 'analysis', 'kind': 'analysis', 'method': 'python-script',
                      'arguments': {'script': str(script), 'inputs': [], 'parameters': {}, 'outputs': ['records']}}]
    value['deliverables'][0]['source']['file'] = 'records'
    assert set(study.validate(value)) == {str(script)}


def test_directory_discovery_matches_real_published_helper_outputs(mounted):
    paths = files(mounted, [record()])
    source = mounted / 'mindeval-plan.json'
    source.write_text(json.dumps({'title': 'Source report', 'records': paths}))
    report.publish_mindeval(source, mounted / 'native')
    assembly = mounted / 'assembly.json'
    assembly.write_text(json.dumps({'title': 'Combined report', 'sections': [
        {'title': 'Measured source', 'file': str(mounted / 'native' / 'report.md'), 'format': 'markdown'}]}))
    report.publish_bundle(assembly, mounted / 'combined')
    for method, folder in [('mindeval', mounted / 'native'), ('report', mounted / 'combined')]:
        known = describe_workflow([method])['phases'][method]['directories_not_deliverable_files']
        assert known == PHASE_OUTPUT_DIRECTORIES[method]
        assert all((folder / name).is_dir() for name in known)


def test_stdio_rejection_saved_draft_and_actionable_same_turn_repair(mounted):
    compact = files(mounted, [{'id': 'one', 'summary': 'Not a full record'}])
    value = plan(compact)
    arguments = compose_args(mounted, value)
    bad = call_stdio('compose_scientific_workflow', arguments)
    assert bad['isError'] is True
    saved = json.loads(bad['content'][0]['text'])
    assert not saved['finalized'] and not saved['inference_submitted']
    assert 'Select the full saved native record' in saved['validation_error']
    assert Path(saved['plan_file']).is_file() and study.list_studies() == []
    direct = call_stdio('run_scientific_workflow', {'plan_file': saved['plan_file'],
                                                  'output_directory': str(mounted / 'final')})
    assert direct['isError'] is True and 'state/config' in direct['content'][0]['text']
    full = mounted / 'full.json'
    full.write_text(json.dumps(record()))
    corrected = copy.deepcopy(value['steps'])
    corrected[0]['arguments']['records'] = [str(full)]
    good = call_stdio('compose_scientific_workflow', {'draft_directory': arguments['draft_directory'],
        'expected_sha256': saved['current_sha256'], 'steps': corrected, 'finalize': True})
    assert good['isError'] is False
    finalized = json.loads(good['content'][0]['text'])
    assert finalized['finalized'] and not finalized['inference_submitted']
    assert Path(compact[0]).read_text().find('Not a full record') >= 0
    assert json.loads(Path(saved['plan_file']).read_bytes()) == value
    assert study.list_studies() == []
