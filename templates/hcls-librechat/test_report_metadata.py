"""Heading formatting is shared preflight, not an arbitrary length budget."""
import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import scientific_study as study
import scientific_workflow_draft as draft
from scientific_study_schema import REPORT_HEADING, describe_workflow
from test_study_semantic_preflight import files, plan, record, report


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-only')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'metadata-preflight@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model transport is needed'))
    return tmp_path


def heading(length):
    return ('Descriptive comparison of retained scientific measurements and limitations. ' * length)[:length]


def report_plan(folder):
    source = folder / 'source.csv'
    source.write_text('measurement,value\nactual,7\n')
    value = plan([])
    value['steps'] = [{'id': 'analysis', 'kind': 'analysis', 'method': 'report', 'arguments': {
        'title': 'Measured report', 'sections': [{'title': 'Data', 'file': str(source), 'format': 'csv'}]}}]
    return value


@pytest.mark.parametrize('length', [381, 4097])
def test_long_document_and_section_titles_preserved_without_length_cap(mounted, length):
    value = report_plan(mounted)
    title = heading(length)
    value['steps'][0]['arguments']['title'] = title
    value['steps'][0]['arguments']['sections'][0]['title'] = title
    assert Draft202012Validator(REPORT_HEADING).is_valid(title)
    saved = study.submit(value, mounted / 'complete')
    asyncio.run(study.advance(saved['id']))
    completed = asyncio.run(study.advance(saved['id']))
    assert completed['state'] == 'completed'
    output = Path(completed['artifacts'][0]['path']).read_text()
    assert output.startswith(f'# {title}\n\n## {title}\n\n')
    assert '| actual | 7 |' in output


def test_381_character_mindeval_heading_completes_preserving_numeric_and_full_records(mounted):
    paths = files(mounted, [record('first'), record('second')])
    value = plan(paths)
    short_plan = mounted / 'normal.json'
    short_plan.write_text(json.dumps(value['steps'][0]['arguments']))
    report.publish_mindeval(short_plan, mounted / 'normal')
    value['steps'][0]['arguments']['title'] = heading(381)
    composed = draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
                             'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    assert composed['finalized'] and not composed['inference_submitted']
    assert json.loads(Path(composed['plan_file']).read_bytes()) == value
    accepted = study.submit(value, mounted / 'complete')
    assert study.submit(value, mounted / 'complete')['id'] == accepted['id']
    asyncio.run(study.advance(accepted['id']))
    completed = asyncio.run(study.advance(accepted['id']))
    assert completed['state'] == 'completed'
    output = completed['steps']['analysis']['files']
    for name in ['methods.md', 'measurements.json', 'records.json', 'runs.csv', 'scores.csv',
                 'records/000.json', 'records/001.json', 'transcripts/000.txt', 'transcripts/001.txt']:
        assert Path(output[name]['path']).read_bytes() == (mounted / 'normal' / name).read_bytes()
    assert Path(output['report.md']['path']).read_text().startswith('# ' + heading(381) + '\n\n')


INVALID_HEADINGS = ['', ' ', '\t', '\r', '\n', 'two\nlines', 'trailing\n', 'two\rlines', 'trailing\r', 'two\r\nlines']


@pytest.mark.parametrize('title', INVALID_HEADINGS)
def test_helper_and_typed_heading_reject_same_blank_or_cr_lf_input(title):
    assert not Draft202012Validator(REPORT_HEADING).is_valid(title)
    with pytest.raises(ValueError, match='nonempty one-line document'):
        report.validate_report_metadata(title)
    with pytest.raises(ValueError, match='nonempty one-line section'):
        report.validate_report_metadata('Valid report', [{'title': title}])


@pytest.mark.parametrize('method', ['report', 'mindeval', 'section'])
@pytest.mark.parametrize('title', ['', '   ', 'line\nbreak', 'trailing\r'])
def test_invalid_heading_never_admits_or_finalizes(mounted, method, title):
    value = plan(files(mounted, [record()])) if method == 'mindeval' else report_plan(mounted)
    args = value['steps'][0]['arguments']
    if method == 'section':
        args['sections'][0]['title'] = title
    else:
        args['title'] = title
    with pytest.raises(ValueError):
        study.submit(value, mounted / 'rejected')
    assert study.list_studies() == [] and not (mounted / 'rejected').exists()
    with pytest.raises(ValueError):
        draft.compose({'draft_directory': str(mounted / 'draft'), 'title': value['title'],
                       'steps': value['steps'], 'deliverables': value['deliverables'], 'finalize': True})
    assert not (mounted / 'draft').exists()


@pytest.mark.parametrize('sections', [None, [], {}, False, [{'title': 'Section'}] * 17])
def test_metadata_retains_existing_section_cardinality_and_type(sections):
    with pytest.raises(ValueError, match='one to sixteen'):
        report.validate_report_metadata('Report', sections)


@pytest.mark.parametrize('count', [0, 1, 16, 17])
def test_typed_report_cardinality_matches_existing_helper_before_admission(mounted, count):
    value = report_plan(mounted)
    args = value['steps'][0]['arguments']
    args['sections'] *= count
    descriptor = describe_workflow(['report'])['phases']['report']['step_schema']['properties']['arguments']
    assert descriptor['properties']['sections']['maxItems'] == 16
    assert all(descriptor['properties']['title'][key] == value
               for key, value in REPORT_HEADING.items() if key != 'description')
    assert 'maxLength' not in REPORT_HEADING
    if 1 <= count <= 16:
        assert Draft202012Validator(descriptor).is_valid(args)
        report.validate_report_metadata(args['title'], args['sections'])
        assert study.validate(value)
    else:
        assert not Draft202012Validator(descriptor).is_valid(args)
        with pytest.raises(ValueError):
            study.submit(value, mounted / 'invalid')
        assert not (mounted / 'invalid').exists() and study.list_studies() == []


def test_publish_checks_format_before_reading_missing_sources(mounted):
    invalid = mounted / 'invalid-report.json'
    invalid.write_text(json.dumps({'title': 'invalid\nheading', 'sections': [
        {'title': 'Section', 'file': 'does-not-exist.md', 'format': 'markdown'}]}))
    with pytest.raises(ValueError, match='one-line document'):
        report.publish_bundle(invalid, mounted / 'unpublished')
    invalid.write_text(json.dumps({'title': 'invalid\rheading', 'records': ['does-not-exist.json']}))
    with pytest.raises(ValueError, match='one-line document'):
        report.publish_mindeval(invalid, mounted / 'unpublished')
    assert not (mounted / 'unpublished').exists()
