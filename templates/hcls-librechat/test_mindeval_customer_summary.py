"""Stored overall scores stay attached to exact run identities through Runs."""
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import scientific_study as study
from scientific_receipts import load
import test_scientific_study as study_tests

mounted = study_tests.mounted

spec = importlib.util.spec_from_file_location('summary_report', study.HERE / 'report-assembly.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def records(root):
    paths = []
    for index, (profile, overall) in enumerate([('profile-000', 4.325), ('profile-032', 4.55)]):
        item = {'id': f'run-{index}', 'status': 'completed', 'state': {
            'config': {'profile_id': profile, 'clinician_model': 'same-clinician',
                       'patient_model': 'patient', 'max_turns': 1},
            'transcript': [{'role': 'patient', 'content': 'Literal unchanged source.'}],
            # Deliberately not the mean of these criteria: never recalculate.
            'judgment': {'model': 'judge', 'judgment': {'first': 1, 'second': 2},
                         'overall_score': overall}}}
        path = root / f'record-{index}.json'
        path.write_text(json.dumps(item))
        paths.append(path)
    return paths


def make_plan(root, paths):
    return {'schema': study.SCHEMA, 'title': 'Retained comparison', 'steps': [
        {'id': 'analysis', 'kind': 'analysis', 'method': 'mindeval',
         'arguments': {'title': 'Measured comparison', 'records': list(map(str, paths))}}],
        'deliverables': [{'name': name, 'role': 'report' if name == 'report.md' else 'data',
                          'source': {'step': 'analysis', 'file': name}}
                         for name in ['report.md', 'scores.csv', 'runs.csv', 'measurements.json', 'provenance.json']]}


def test_real_durable_publication_adds_summary_preserving_five_promised_outputs(mounted):
    paths = records(mounted)
    originals = [path.read_bytes() for path in paths]
    started = study.submit(make_plan(mounted, paths), mounted / 'output')
    asyncio.run(study.advance(started['id']))
    done = asyncio.run(study.advance(started['id']))
    assert done['state'] == 'completed'
    assert [a['name'] for a in done['artifacts']] == ['report.md', 'scores.csv', 'runs.csv',
        'measurements.json', 'provenance.json', 'steps/analysis/customer-summary.json']
    published = done['artifacts'][-1]
    raw = Path(published['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == published['sha256']
    document = json.loads(raw)
    assert [(r['profile_id'], r['clinician_model'], r['run_id'], r['overall_score']) for r in document['rows']] == [
        ('profile-000', 'same-clinician', 'run-0', 4.325), ('profile-032', 'same-clinician', 'run-1', 4.55)]
    assert document['counts']['distinct_criteria'] == 2
    assert document['counts']['profile_criterion_cells'] == 4
    assert document['inference_submitted'] is False
    assert document['scientific_claims_validated'] is False
    assert len(done['completion_summaries']) == 1
    projection = done['completion_summaries'][0]
    assert projection['state'] == 'verified'
    assert projection['text'] == document['text']
    assert projection['download_url'] == published['download_url']
    assert 'profile_id: profile-032 | clinician_model: same-clinician | run_id: run-1 | overall_score: 4.55' in projection['text']
    assert study.get(started['id'])['completion_summaries'] == done['completion_summaries']
    assert [path.read_bytes() for path in paths] == originals
    manifest = json.loads(Path(done['manifest']['path']).read_bytes())
    assert len(manifest['artifacts']) == 6 and manifest['operations'] == []


@pytest.mark.parametrize('value', [None, '4.55', False, {}, []])
def test_unavailable_overall_is_never_replaced_by_criterion_mean(mounted, value):
    paths = records(mounted)
    item = json.loads(paths[0].read_bytes())
    item['state']['judgment']['overall_score'] = value
    paths[0].write_text(json.dumps(item))
    plan = mounted / 'plan.json'
    plan.write_text(json.dumps({'title': 'Stored only', 'records': list(map(str, paths))}))
    helper.publish_mindeval(plan, mounted / 'report')
    row = json.loads((mounted / 'report/customer-summary.json').read_bytes())['rows'][0]
    assert row['overall_score'] is None and row['measurement_state'] == 'unavailable'


def test_missing_overall_is_unavailable_and_numeric_zero_is_preserved(mounted):
    paths = records(mounted)
    first, second = [json.loads(p.read_bytes()) for p in paths]
    del first['state']['judgment']['overall_score']
    second['state']['judgment']['overall_score'] = 0
    for path, value in zip(paths, [first, second]):
        path.write_text(json.dumps(value))
    plan = mounted / 'plan.json'
    plan.write_text(json.dumps({'title': 'Stored only', 'records': list(map(str, paths))}))
    helper.publish_mindeval(plan, mounted / 'report')
    rows = json.loads((mounted / 'report/customer-summary.json').read_bytes())['rows']
    assert rows[0]['overall_score'] is None
    assert rows[1]['overall_score'] == 0 and rows[1]['measurement_state'] == 'supplied'


def projection_fixture(root):
    file = root / 'customer-summary.json'
    file.write_text(json.dumps({'schema': 'scientific-study-summary/v1', 'text': 'Exact saved values.'}))
    info = study.measure(file)
    step = {'state': 'completed', 'files': {file.name: info}, 'customer_summary': file.name,
            'customer_artifacts': {file.name: {**info, 'role': 'metrics'}}}
    record = {'state': 'completed', 'steps': {'analysis': step}}
    artifact = {**info, 'name': 'summary.json', 'download_url': '/demos?tab=workspace&file=summary.json'}
    return record, [artifact], file


@pytest.mark.parametrize('defect', ['changed_bytes', 'missing', 'not_published', 'not_selected', 'unregistered', 'unfinished', 'invalid_json', 'wrong_schema'])
def test_unverified_summary_never_projects_text_or_changes_saved_state(mounted, defect):
    record, artifacts, file = projection_fixture(mounted)
    if defect == 'changed_bytes':
        file.write_text('Different')
    elif defect == 'missing':
        file.unlink()
    elif defect == 'not_published':
        artifacts = []
    elif defect == 'not_selected':
        record['steps']['analysis']['customer_artifacts'] = {}
    elif defect == 'unregistered':
        record['steps']['analysis']['files'] = {}
    elif defect == 'unfinished':
        record['steps']['analysis']['state'] = 'running'
    else:
        file.write_text('not json' if defect == 'invalid_json' else '{"schema":"other","text":"Incorrect"}')
        info = study.measure(file)
        artifacts[0].update(info)
        record['steps']['analysis']['files'][file.name] = info
        record['steps']['analysis']['customer_artifacts'][file.name].update(info)
    before = copy.deepcopy(record)
    result = study.completion_summaries(record, artifacts)
    assert result[0]['state'] == 'unavailable' and 'text' not in result[0]
    assert record == before


def test_preview_limit_does_not_truncate_table_or_reject_study(mounted):
    record, artifacts, file = projection_fixture(mounted)
    file.write_text(json.dumps({'schema': 'scientific-study-summary/v1', 'text': 'x' * 65536}))
    info = study.measure(file)
    artifacts[0].update(info)
    record['steps']['analysis']['files'][file.name] = info
    record['steps']['analysis']['customer_artifacts'][file.name].update(info)
    result = study.completion_summaries(record, artifacts)
    assert result[0]['state'] == 'unavailable' and 'text' not in result[0]
    assert 'No rows are truncated' in result[0]['notice']
    assert result[0]['download_url'] == artifacts[0]['download_url']
    assert record['state'] == 'completed' and file.stat().st_size > 65536


def test_legacy_and_pending_studies_are_unchanged(mounted):
    record, artifacts, _ = projection_fixture(mounted)
    record['state'] = 'running'
    assert study.completion_summaries(record, artifacts) == []
    record['state'] = 'completed'
    del record['steps']['analysis']['customer_summary']
    assert study.completion_summaries(record, artifacts) == []


def test_summary_is_hash_bound_in_both_helper_and_study_manifests(mounted):
    started = study.submit(make_plan(mounted, records(mounted)), mounted / 'output')
    asyncio.run(study.advance(started['id']))
    done = asyncio.run(study.advance(started['id']))
    record = load(study.directory(started['id']) / 'receipt.json')
    files = record['steps']['analysis']['files']
    helper_manifest = json.loads(Path(files['completion-manifest.json']['path']).read_bytes())
    entry = next(a for a in helper_manifest['artifacts'] if a['path'] == 'customer-summary.json')
    assert entry['sha256'] == done['artifacts'][-1]['sha256'] == files['customer-summary.json']['sha256']
