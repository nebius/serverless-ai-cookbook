"""Measured clinical evidence and explicit safe customer artifact registration."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from scientific_clinical import customer_artifacts, outcome_documents
from scientific_study import measure

HERE = Path(__file__).parent


@pytest.fixture
def outcome(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_CLINICAL_SCRIPT', str(HERE / 'skills/clinical-documentation/scripts/clinical_report.py'))
    source = 'I feel tired. Teaching narration.'
    quote = 'I feel tired.'
    document = {'schema': 'clinical-documentation/v11', 'transcript_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'facts': [{'id': 'fact-1', 'section': 'history', 'statement': quote,
                   'source_phrases': [{'quote': quote, 'spans': [{'start': 0, 'end': len(quote)}]}],
                   'evidence': [{'quote': quote, 'spans': [{'start': 0, 'end': len(quote)}]}]}],
        'source_excerpts': [], 'rejected': [{'reason': 'retained for review'}],
        'source_coverage': [{'final': [{'start': 0, 'end': len(quote)}, {'start': len(quote), 'end': len(source)}]}]}
    contents = {'transcript.txt': source, 'document.json': json.dumps(document),
                'report.md': '# Original draft\n', 'review.md': '# Original review\n',
                'review.json': '{"rejected":[{}]}', 'coverage.json': json.dumps(document['source_coverage']),
                'follow-up.md': '# Original questions\n', 'run.json': '{"model":"unchanged"}',
                'catalog.json': '{"internal":"not a customer deliverable"}'}
    files = {}
    for name, value in contents.items():
        path = tmp_path / name
        path.write_text(value)
        files[name] = measure(path)
    return {'schema': 'scientific-clinical-outcome/v1', 'outcome': 'completed',
            'report_produced': True, 'clinical_validation': False, 'no_report_explicitly_allowed': False,
            'files': files}


def test_measured_outcome_reuses_exact_source_reader_without_mutating_inputs(outcome):
    before = {name: Path(info['path']).read_bytes() for name, info in outcome['files'].items()}
    first = outcome_documents(outcome)
    assert first == outcome_documents(outcome)
    assessment = json.loads(first['clinical-outcome.json'])['source_assessment']
    assert assessment['accepted_facts'] == assessment['selected_phrases'] == 1
    assert assessment['declared_segments'] == 2 and assessment['segments_with_selected_phrase'] == 1
    assert assessment['withheld_candidates'] == 1
    assert assessment['clinical_completeness'] == assessment['speaker_attribution'] == 'not_established'
    assert 'Segments without a selected report phrase' in first['clinical-outcome.md'].decode()
    assert 'not clinical correctness' in first['clinical-outcome.md'].decode()
    assert before == {name: Path(info['path']).read_bytes() for name, info in outcome['files'].items()}


def register(outcome):
    files = outcome['files'].copy()
    for name, raw in outcome_documents(outcome).items():
        path = Path(files['transcript.txt']['path']).parent / name
        path.write_bytes(raw)
        files[name] = measure(path)
    return files


def test_customer_registration_excludes_calls_catalog_and_checkpoint(outcome):
    files = register(outcome)
    files['calls/provider/response.json'] = files['run.json']
    files['receipt.json'] = files['run.json']
    selected = customer_artifacts(files, True)
    assert set(selected) == set(files) - {'catalog.json', 'calls/provider/response.json', 'receipt.json'}
    assert selected['report.md']['role'] == 'report'
    assert selected['run.json']['role'] == 'provenance'


@pytest.mark.parametrize('name', ['report.md', 'review.md', 'document.json', 'transcript.txt', 'follow-up.md'])
def test_positive_missing_required_customer_file_fails_before_publication(outcome, name):
    del outcome['files'][name]
    with pytest.raises(ValueError, match='missing required'):
        outcome_documents(outcome)


@pytest.mark.parametrize('defect', ['hash', 'offset', 'identity'])
def test_bad_evidence_is_not_measured_as_success(outcome, defect):
    info = outcome['files']['document.json']
    path = Path(info['path'])
    document = json.loads(path.read_bytes())
    if defect == 'identity':
        document['transcript_sha256'] = '0' * 64
    else:
        document['facts'][0]['source_phrases'][0]['spans'][0]['end'] -= 1
    path.write_text(json.dumps(document))
    if defect != 'hash':
        outcome['files']['document.json'] = measure(path)
    with pytest.raises((ValueError, RuntimeError)):
        outcome_documents(outcome)


def test_explicit_negative_registers_source_and_review_without_invented_report(outcome):
    outcome.update(outcome='no_supported_clinical_facts', report_produced=False, no_report_explicitly_allowed=True)
    for name in ['report.md', 'document.json', 'follow-up.md']:
        del outcome['files'][name]
    files = register(outcome)
    selected = customer_artifacts(files, False)
    assert 'review.md' in selected and not {'report.md', 'document.json', 'follow-up.md'} & selected.keys()
    assessment = json.loads(Path(files['clinical-outcome.json']['path']).read_bytes())['source_assessment']
    assert assessment['status'] == 'no_report' and assessment['accepted_facts'] == 0
    assert assessment['clinical_completeness'] == 'not_established'
    assert 'not a finding of absent illness' in Path(files['clinical-outcome.md']['path']).read_text()


def test_negative_does_not_register_positive_artifacts(outcome):
    outcome.update(outcome='no_supported_clinical_facts', report_produced=False, no_report_explicitly_allowed=True)
    with pytest.raises(ValueError, match='unexpectedly'):
        outcome_documents(outcome)
