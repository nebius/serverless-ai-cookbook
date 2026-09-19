"""A report heading is presentation metadata, not a scientific prerequisite."""
import asyncio
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import scientific_study as study
import scientific_workflow_draft as draft
from scientific_study_schema import DEFAULT_REPORT_TITLE, DRAFT_SCHEMA, STUDY_SCHEMA, describe_workflow


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    for name, value in {'SCIENTIFIC_WORKSPACE': str(tmp_path),
                        'SCIENTIFIC_MODELS_MCP_URL': 'https://platform.test/mcp',
                        'SCIENTIFIC_MODELS_API_KEY': 'cpu-fixture-only',
                        'SEED_DEFAULT_USER_EMAIL': 'heading@example.test',
                        'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance'}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model transport'))
    return tmp_path


def plan(folder):
    source = folder / 'measurements.csv'
    source.write_bytes(b'identity,value\nfirst,4.55\nsecond,4.325\n')
    return {'schema': study.SCHEMA, 'title': 'Independent study heading', 'steps': [
        {'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
            'sections': [{'title': 'Exact stored measurements', 'file': str(source), 'format': 'csv'}]}}],
        'deliverables': [{'name': name, 'role': role, 'source': {'step': 'report', 'file': name}}
                         for name, role in [('report.md', 'report'), ('provenance.json', 'provenance')]]}


@pytest.mark.parametrize('title', [None, 'Explicit heading — kept verbatim', 'A descriptive heading ' * 30])
def test_composer_admission_render_and_publication_preserve_numbers_and_plan(mounted, title):
    value = plan(mounted)
    if title is not None:
        value['steps'][0]['arguments']['title'] = title
    original = copy.deepcopy(value)
    args = {'draft_directory': str(mounted / 'draft'), 'title': value['title'],
            'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True}
    Draft202012Validator(DRAFT_SCHEMA).validate(args)
    Draft202012Validator(STUDY_SCHEMA).validate(value)
    composed = draft.compose(args)
    assert composed['finalized'] and not composed['inference_submitted']
    assert json.loads(Path(composed['plan_file']).read_bytes()) == original
    accepted = study.submit(value, mounted / 'final')
    assert study.submit(value, mounted / 'final')['id'] == accepted['id']
    asyncio.run(study.advance(accepted['id']))
    finished = asyncio.run(study.advance(accepted['id']))
    assert finished['state'] == 'completed' and value == original
    assert json.loads((study.directory(accepted['id']) / 'plan.json').read_bytes()) == original
    files = finished['steps']['report']['files']
    output = Path(files['report.md']['path']).read_text()
    assert output.startswith('# ' + (DEFAULT_REPORT_TITLE if title is None else title) + '\n\n')
    assert '| first | 4.55 |' in output and '| second | 4.325 |' in output
    assert Path(files['sources/000.csv']['path']).read_bytes() == (mounted / 'measurements.csv').read_bytes()
    helper_plan = json.loads(Path(files['assembly-plan.json']['path']).read_bytes())
    assert helper_plan['title'] == (DEFAULT_REPORT_TITLE if title is None else title)
    assert finished['manifest']['size_bytes'] > 0 and len(finished['artifacts']) == 2


@pytest.mark.parametrize('invalid', [None, False, 7, {}, [], '', '   ', 'line\nbreak', 'trailing\r'])
def test_explicit_invalid_document_title_is_not_defaulted_or_admitted(mounted, invalid):
    value = plan(mounted)
    value['steps'][0]['arguments']['title'] = invalid
    with pytest.raises(ValueError):
        study.submit(value, mounted / 'rejected')
    with pytest.raises(ValueError):
        draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
                       'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    assert not study.list_studies() and not (mounted / 'rejected').exists()
    assert not (mounted / 'draft').exists()


@pytest.mark.parametrize('missing', ['title', 'file', 'format'])
def test_section_contract_remains_required(mounted, missing):
    value = plan(mounted)
    del value['steps'][0]['arguments']['sections'][0][missing]
    with pytest.raises(ValueError):
        study.submit(value, mounted / 'rejected')
    assert not study.list_studies()


def test_discovery_and_composer_share_exact_optional_presentation_contract():
    contract = describe_workflow(['report'])['phases']['report']['step_schema']
    args = contract['properties']['arguments']
    assert args['required'] == ['sections']
    assert args['properties']['title']['default'] == DEFAULT_REPORT_TITLE
    assert 'Explicit titles are preserved' in args['properties']['title']['description']
    assert contract in DRAFT_SCHEMA['properties']['steps']['items']['oneOf']
    assert contract in STUDY_SCHEMA['properties']['steps']['items']['oneOf']
