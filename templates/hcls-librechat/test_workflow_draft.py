"""Grouped draft edits use the same immutable scientific study admission."""
import asyncio
import copy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent))
import scientific_study as study
import scientific_workflow_draft as draft
from scientific_preparation import canonical
from scientific_receipts import load
from scientific_study_schema import DRAFT_SCHEMA, DELIVERABLE, STEPS, STUDY_SCHEMA, describe_workflow

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('draft_execution', ROOT / 'execution-mcp.py')
execution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution)


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'draft-test-secret')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'draft@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    return tmp_path


def report_step(source):
    return {'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
        'title': 'Measured results', 'sections': [{'title': 'Data', 'file': source, 'format': 'csv'}]}}


def deliverables():
    return [{'name': name, 'role': role, 'source': {'step': 'report', 'file': name}}
            for name, role in [('report.md', 'report'), ('provenance.json', 'provenance')]]


def initial(folder):
    source = folder / 'rows.csv'
    source.write_text('measurement,value\nactual,7\n')
    return {'draft_directory': str(folder / 'draft'), 'title': 'A measured study',
            'steps': [report_step(str(source))], 'deliverables': deliverables()}


def test_shared_schema_and_seed_installation():
    assert DRAFT_SCHEMA['properties']['steps']['items']['oneOf'] is STEPS
    assert DRAFT_SCHEMA['properties']['deliverables']['items'] is DELIVERABLE
    assert STUDY_SCHEMA['properties']['deliverables']['items'] is DELIVERABLE
    assert next(tool['inputSchema'] for tool in execution.TOOLS if tool['name'] == 'compose_scientific_workflow') is DRAFT_SCHEMA
    assert 'scientific_workflow_draft.py' in (ROOT / 'Dockerfile').read_text()
    for path in (ROOT / 'seed-workbench.js', ROOT.parents[1] / 'life-science/bionemo-librechat/scientific-agent-instructions.md'):
        content = path.read_text()
        assert 'compose_scientific_workflow_mcp_environment-execution' in content
        assert 'several related steps per edit' in content.lower()
    selected = describe_workflow(['mindeval'])
    text = json.dumps(selected)
    assert 'state.judgment.judgment' in text and 'do NOT transform' in text
    assert selected['draft_composer']['tool'] == 'compose_scientific_workflow_mcp_environment-execution'


def test_create_finalize_one_group_no_admission_then_existing_launcher(mounted, monkeypatch):
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('CPU phase must not load model transport'))
    args = {**initial(mounted), 'finalize': True}
    first = draft.compose(args)
    assert first['finalized'] is True and first['inference_submitted'] is False
    assert first['step_count'] == 1 and first['deliverable_count'] == 2
    assert study.list_studies() == []
    data = Path(first['plan_file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == first['sha256']
    assert len(data) == first['size_bytes']
    assert draft.compose(args)['replayed'] is True
    launched = execution.run_scientific_workflow({'plan_file': first['plan_file'], 'output_directory': str(mounted / 'final')})
    assert execution.run_scientific_workflow({'study': json.loads(data), 'output_directory': str(mounted / 'final')})['id'] == launched['id']
    # Finalized revisions are never rewritten by later draft edits.
    edited = draft.compose({'draft_directory': args['draft_directory'], 'expected_sha256': first['sha256'], 'title': 'New draft'})
    assert Path(first['plan_file']).read_bytes() == data
    assert edited['sha256'] != first['sha256'] and not edited['finalized']
    assert draft.compose(args)['current_sha256'] == edited['sha256']
    assert draft.compose({'draft_directory': args['draft_directory']})['sha256'] == edited['sha256']
    asyncio.run(study.advance(launched['id']))
    completed = asyncio.run(study.advance(launched['id']))
    assert completed['state'] == 'completed'
    report = next(item for item in completed['artifacts'] if item['name'] == 'report.md')
    assert Path(report['path']).stat().st_size > 0
    assert len(study.list_studies()) == 1
    assert 'draft-test-secret' not in (mounted / 'draft' / 'receipt.json').read_text()


def test_partial_forward_reference_later_group_then_same_validator(mounted):
    args = initial(mounted)
    first = draft.compose({key: value for key, value in args.items() if key != 'steps'})
    assert first['step_count'] == 0 and not first['finalized']
    incomplete = draft.compose({'draft_directory': args['draft_directory'], 'expected_sha256': first['sha256'], 'finalize': True})
    assert not incomplete['finalized'] and 'steps' in incomplete['validation_error']
    final = draft.compose({'draft_directory': args['draft_directory'], 'expected_sha256': incomplete['sha256'],
                           'steps': args['steps'], 'finalize': True})
    assert final['finalized'] and final['validation_error'] is None
    study.validate(json.loads(Path(final['plan_file']).read_bytes()))
    assert study.list_studies() == []


def test_finalization_reports_actual_missing_file_then_repairs(mounted):
    args = initial(mounted)
    Path(args['steps'][0]['arguments']['sections'][0]['file']).unlink()
    value = draft.compose({**args, 'finalize': True})
    assert not value['finalized'] and 'does not exist' in value['validation_error']
    (mounted / 'rows.csv').write_text('x,y\n1,2\n')
    final = draft.compose({'draft_directory': args['draft_directory'], 'expected_sha256': value['sha256'], 'finalize': True})
    assert final['finalized']
    (mounted / 'rows.csv').unlink()
    again = draft.compose({'draft_directory': args['draft_directory']})
    assert not again['finalized'] and 'does not exist' in again['validation_error']


def test_source_changes_after_admission_keep_existing_failure(mounted):
    value = draft.compose({**initial(mounted), 'finalize': True})
    saved = execution.run_scientific_workflow({'plan_file': value['plan_file'], 'output_directory': str(mounted / 'final')})
    (mounted / 'rows.csv').write_text('measurement,value\nchanged,8\n')
    assert asyncio.run(study.advance(saved['id']))['state'] == 'failed'
    assert not (mounted / 'final' / 'completion-manifest.json').exists()


@pytest.mark.parametrize('change', [
    {'title': 'missing expected'},
    {'expected_sha256': 'f' * 64, 'title': 'stale'},
    {'expected_sha256': 'bad', 'title': 'malformed'},
])
def test_stale_edits_do_not_touch_saved_plan(mounted, change):
    args = initial(mounted)
    value = draft.compose(args)
    before = load(mounted / 'draft' / 'receipt.json')
    with pytest.raises(ValueError):
        draft.compose({'draft_directory': args['draft_directory'], **change})
    assert load(mounted / 'draft' / 'receipt.json') == before
    assert Path(value['plan_file']).is_file()


@pytest.mark.parametrize('change', [
    {'steps': [{'id': 'bad', 'kind': 'unknown'}]},
    {'steps': [report_step('/workspace/a'), report_step('/workspace/b')]},
    {'remove_steps': ['missing']},
    {'remove_steps': ['report'], 'steps': [report_step('/workspace/a')]},
    {'title': '   '},
    {'unexpected': True},
])
def test_invalid_edit_preserves_prior_receipt(mounted, change):
    args = initial(mounted)
    value = draft.compose(args)
    before = load(mounted / 'draft' / 'receipt.json')
    with pytest.raises(ValueError):
        draft.compose({'draft_directory': args['draft_directory'], 'expected_sha256': value['sha256'], **change})
    assert load(mounted / 'draft' / 'receipt.json') == before


def test_upsert_remove_and_order_without_silent_append_duplicates(mounted):
    args = initial(mounted)
    second = {**copy.deepcopy(args['steps'][0]), 'id': 'second'}
    first = draft.compose({**args, 'steps': [args['steps'][0], second]})
    changed = copy.deepcopy(args['steps'][0])
    changed['arguments']['title'] = 'Changed'
    result = draft.compose({'draft_directory': args['draft_directory'], 'expected_sha256': first['sha256'],
                           'steps': [changed], 'remove_steps': ['second'], 'remove_deliverables': ['provenance.json']})
    plan = json.loads(Path(result['plan_file']).read_bytes())
    assert plan['steps'] == [changed] and len(plan['deliverables']) == 1


def test_latest_journal_recovers_after_canonical_write_failure(mounted, monkeypatch):
    args = initial(mounted)
    value = draft.compose(args)
    import scientific_receipts as receipts
    original = receipts._write_verified
    def interrupted(path, data):
        if path.name == 'receipt.json':
            raise OSError('simulated disconnect after immutable journal')
        original(path, data)
    monkeypatch.setattr(receipts, '_write_verified', interrupted)
    edit = {'draft_directory': args['draft_directory'], 'expected_sha256': value['sha256'], 'title': 'Recovered change'}
    with pytest.raises(OSError, match='simulated disconnect'):
        draft.compose(edit)
    monkeypatch.setattr(receipts, '_write_verified', original)
    importlib.reload(draft)
    recovered = draft.compose(edit)
    assert recovered['replayed'] and recovered['sha256'] != value['sha256']
    assert draft.compose({'draft_directory': args['draft_directory']})['sha256'] == recovered['sha256']


def test_restart_after_revision_publish_before_receipt_does_not_duplicate(mounted, monkeypatch):
    args = {**initial(mounted), 'finalize': True}
    original = draft.save
    def disconnected(*unused):
        raise OSError('lost process before receipt')
    monkeypatch.setattr(draft, 'save', disconnected)
    with pytest.raises(OSError, match='lost process'):
        draft.compose(args)
    files = list((mounted / 'draft' / 'revisions').glob('*.json'))
    assert len(files) == 1
    before = files[0].read_bytes()
    monkeypatch.setattr(draft, 'save', original)
    final = draft.compose(args)
    assert final['finalized'] and Path(final['plan_file']).read_bytes() == before
    assert list((mounted / 'draft' / 'revisions').glob('*.json')) == files
    assert study.list_studies() == []


def test_tampered_revision_is_not_read_or_revalidated(mounted):
    args = {**initial(mounted), 'finalize': True}
    value = draft.compose(args)
    Path(value['plan_file']).write_text('{}')
    for attempt in (args, {'draft_directory': args['draft_directory']}):
        with pytest.raises(RuntimeError, match='artifact bytes differ'):
            draft.compose(attempt)


def test_workspace_escape_and_missing_draft_do_not_publish(mounted):
    with pytest.raises(ValueError, match='workspace'):
        draft.compose({'draft_directory': str(mounted.parent / 'escape'), 'title': 'No'})
    with pytest.raises(ValueError, match='does not exist'):
        draft.compose({'draft_directory': str(mounted / 'absent')})
    assert not (mounted / 'absent').exists()


def test_actual_stdio_composer_then_disconnect_readback(mounted):
    args = {**initial(mounted), 'finalize': True}
    def request(arguments):
        data = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'compose_scientific_workflow', 'arguments': arguments}}
        result = subprocess.run([sys.executable, str(ROOT / 'execution-mcp.py')],
                                input=json.dumps(data) + '\n', text=True, capture_output=True,
                                env=os.environ.copy(), check=True)
        reply = json.loads(result.stdout)['result']
        assert reply['isError'] is False
        return json.loads(reply['content'][0]['text'])
    saved = request(args)
    assert saved['finalized']
    assert request({'draft_directory': args['draft_directory']})['sha256'] == saved['sha256']
    assert study.list_studies() == []


def representative_plan(mounted):
    """Twelve model phases, saved custom analysis, and deterministic publication."""
    script = mounted / 'analysis.py'
    script.write_text('print("saved scientific analysis source")\n')
    preparation = {'id': 'prepare', 'kind': 'preparation', 'method': 'write-json',
                   'arguments': {'filename': 'input.json', 'value': {'sequence': 'ACGTACGT', 'num_tokens': 8}}}
    native = [{'id': f'generate-{number}', 'kind': 'native', 'model': 'evo2',
               'input': {'step': 'prepare', 'file': 'input.json'},
               'idempotency_key': f'explicit-frozen-call-{number:02}'} for number in range(12)]
    analysis = {'id': 'analysis', 'kind': 'analysis', 'method': 'python-script', 'arguments': {
        'script': str(script), 'inputs': [{'name': step['id'], 'file': {'step': step['id'], 'file': 'result.json'}} for step in native],
        'parameters': {'measurement': 'suffix-gc'}, 'outputs': ['measurements.csv']}}
    return {'schema': study.SCHEMA, 'title': 'Twelve authorized generation comparisons',
            'steps': [preparation, *native, analysis, report_step({'step': 'analysis', 'file': 'measurements.csv'})],
            'deliverables': deliverables()}


def test_grouped_plan_reduces_peak_arguments_without_one_call_per_step(mounted, monkeypatch):
    # The existing transport module constants are sufficient for offline shape
    # validation. No endpoint, model call, or scientific calculation is run.
    from types import SimpleNamespace
    monkeypatch.setattr(study, 'workflow_module', lambda: SimpleNamespace(
        NATIVE_REQUIRED={'kind', 'id', 'model', 'input', 'output', 'idempotency_key'}, REQUIRED=set(), OPTIONAL=set()))
    plan = representative_plan(mounted)
    Draft202012Validator(STUDY_SCHEMA).validate(plan)
    study.validate(plan)
    calls, value = [], None
    for index, group in enumerate((plan['steps'][:5], plan['steps'][5:10], plan['steps'][10:])):
        args = {'draft_directory': str(mounted / 'draft'), 'steps': group}
        if index == 0:
            args.update(title=plan['title'], deliverables=plan['deliverables'])
        else:
            args['expected_sha256'] = value['current_sha256']
        if index == 2:
            args['finalize'] = True
        calls.append(args)
        value = draft.compose(args)
    assert value['finalized'] and value['step_count'] == 15
    assert json.loads(Path(value['plan_file']).read_bytes()) == plan
    launch = {'plan_file': value['plan_file'], 'output_directory': str(mounted / 'final')}
    one_shot = {'study': plan, 'output_directory': str(mounted / 'final')}
    metrics = {'schema': 'workflow-composition-size-measurement/v1',
        'comparison': 'Equivalent representative plan, not the unknown truncated v49 payload size',
        'step_count': 15, 'one_shot_launch_rounds': 1, 'grouped_composer_rounds': len(calls),
        'grouped_total_with_launch': len(calls) + 1,
        'one_shot_argument_bytes': len(canonical(one_shot)),
        'grouped_argument_bytes': [len(canonical(call)) for call in calls + [launch]]}
    assert metrics['grouped_total_with_launch'] == 4
    assert max(metrics['grouped_argument_bytes']) < metrics['one_shot_argument_bytes'] * 0.65
    assert study.list_studies() == []
    (mounted / 'composition-measurement.json').write_bytes(canonical(metrics))


def test_dependency_order_uses_existing_validator_without_reordering(mounted):
    first = {'id': 'prepare', 'kind': 'preparation', 'method': 'write-json',
             'arguments': {'filename': 'rows.csv', 'value': {'measured': 1}}}
    final = report_step({'step': 'prepare', 'file': 'rows.csv'})
    args = {'draft_directory': str(mounted / 'draft'), 'title': 'Ordering stays explicit',
            'steps': [final, first], 'deliverables': deliverables(), 'finalize': True}
    result = draft.compose(args)
    plan = json.loads(Path(result['plan_file']).read_bytes())
    assert plan['steps'] == [final, first]
    assert not result['finalized'] and 'earlier step ID' in result['validation_error']
    with pytest.raises(ValueError) as direct:
        study.validate(plan)
    assert result['validation_error'] == str(direct.value)


def test_native_mindeval_plan_needs_two_small_calls_not_custom_program(mounted):
    records = []
    for number in range(6):
        path = mounted / f'record-{number}.json'
        path.write_text(json.dumps({'id': f'run-{number}', 'state': {'config': {}, 'transcript': [{'role': 'patient', 'content': 'Retained'}],
                                                  'judgment': {'judgment': {'criterion': 4}}}}))
        records.append(str(path))
    plan = {'schema': study.SCHEMA, 'title': 'Retained consultation analysis',
        'steps': [{'id': 'analysis', 'kind': 'analysis', 'method': 'mindeval',
                   'arguments': {'title': 'Retained consultation analysis', 'records': records}}],
        'deliverables': [{'name': name, 'role': role, 'source': {'step': 'analysis', 'file': name}}
                         for name, role in [('report.md', 'report'), ('measurements.json', 'metrics'),
                                            ('provenance.json', 'provenance'), ('scores.csv', 'data')]]}
    arguments = {'draft_directory': str(mounted / 'draft'), 'title': plan['title'], 'steps': plan['steps'],
                 'deliverables': plan['deliverables'], 'finalize': True}
    result = draft.compose(arguments)
    assert result['finalized']
    assert json.loads(Path(result['plan_file']).read_bytes()) == plan
    launch = {'plan_file': result['plan_file'], 'output_directory': str(mounted / 'final')}
    measurement = {'schema': 'workflow-composition-size-measurement/v1', 'plan_kind': 'six-retained-native-mindeval-records',
                   'argument_bytes': [len(canonical(arguments)), len(canonical(launch))],
                   'composer_rounds': 1, 'total_with_launch': 2, 'custom_program_bytes': 0,
                   'historical_truncated_argument_bytes': None,
                   'historical_size_reason': 'The failed v49 final tool call retained empty incomplete arguments; its generated size is unknown.'}
    assert max(measurement['argument_bytes']) < 2500
    (mounted / 'mindeval-composition-measurement.json').write_bytes(canonical(measurement))
