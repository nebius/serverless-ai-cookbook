"""Generalized report contracts; synthetic fixtures are not clinical validation."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import study_report as report


def fixture(tmp_path, count=32):
    text = 'No fever now. An examination is planned.'
    phrase = {'quote': 'No fever now.', 'spans': [{'start': 0, 'end': 13}]}
    document = {'schema': 'clinical-documentation/v11', 'transcript_sha256': report.digest(text.encode()),
                'facts': [{'id': f'F{i:04}', 'section': 'history', 'statement': phrase['quote'],
                           'source_phrases': [copy.deepcopy(phrase)], 'evidence': [copy.deepcopy(phrase)]}
                          for i in range(count)],
                'source_excerpts': [{'quote': text[14:], 'spans': [{'start': 14, 'end': len(text)}]}],
                'rejected': [], 'source_coverage': [{'final': [{'start': 0, 'end': 13},
                                                              {'start': 14, 'end': len(text)}]}]}
    (tmp_path / 'transcript.txt').write_text(text)
    (tmp_path / 'document.json').write_text(json.dumps(document))
    plan = {'schema': report.PLAN_SCHEMA, 'cases': [
        {'id': 'full-source', 'transcript': 'transcript.txt', 'document': 'document.json',
         'provenance': {'language': 'en', 'transcription_reused': True}}]}
    file = tmp_path / 'plan.json'
    file.write_text(json.dumps(plan))
    return file, plan, document


@pytest.mark.parametrize('count', [0, 1, 17, 32, 47])
def test_actual_facts_count_is_schema_bound_and_independent_of_wer_reference(tmp_path, count):
    plan, _, _ = fixture(tmp_path, count)
    value, files = report.prepare_bundle(plan)
    case = value['cases'][0]
    assert case['source_selection']['measurement']['accepted_facts'] == count
    assert case['source_selection']['status'] == 'measured'
    assert case['wer']['status'] == 'not_measured'
    assert case['source_selection']['measurement']['clinical_completeness'] == 'not_established'
    assert f'| full-source | {count} |' in files['report.md'].decode()
    assert 'does not require a human WER reference' in files['report.md'].decode()
    assert value['clinical_validation'] is False


def test_missing_document_is_unknown_not_zero_and_normalization_explanation_is_honest(tmp_path):
    plan, value, _ = fixture(tmp_path)
    case = value['cases'][0]
    case.pop('document')
    case['reference'] = 'reference.txt'
    (tmp_path / 'reference.txt').write_text('NO FEVER NOW! an examination is planned.')
    plan.write_text(json.dumps(value))
    bundle, files = report.prepare_bundle(plan)
    result = bundle['cases'][0]
    assert result['source_selection']['status'] == 'not_measured'
    assert 'unknown, not zero' in result['source_selection']['reason']
    assert result['wer']['measurement']['wer'] == 0
    assert result['wer']['measurement']['reference_tokens'] == 7
    assert 'Case and declared edge punctuation are already ignored' in files['report.md'].decode()
    assert bundle['units']['wer'] == 'ratio'
    assert 'WER (%)' in files['report.md'].decode()


def test_exact_span_probes_expose_fact_ids_but_do_not_infer_semantic_omission(tmp_path):
    plan, value, _ = fixture(tmp_path, 2)
    value['cases'][0]['source_spans'] = 'probes.json'
    (tmp_path / 'probes.json').write_text(json.dumps([
        {'start': 0, 'end': 13, 'quote': 'No fever now.'},
        {'start': 14, 'end': len((tmp_path / 'transcript.txt').read_text()), 'quote': 'An examination is planned.'}]))
    plan.write_text(json.dumps(value))
    bundle, _ = report.prepare_bundle(plan)
    selected, context = bundle['cases'][0]['source_selection']['measurement']['source_span_probes']
    assert selected['accepted_fact_ids'] == ['F0000', 'F0001']
    assert context['accepted_fact_ids'] == []
    assert context['location'] == 'review_excerpt_only'
    assert selected['meaning_preserved'] == context['meaning_preserved'] == 'not_assessed'


def test_manifest_is_complete_verified_and_reentrant_without_rewriting_history(tmp_path):
    plan, _, _ = fixture(tmp_path)
    output = tmp_path / 'output'
    first = report.assemble(plan, output)
    assert first['reused_completed_output'] is False
    manifest_bytes = (output / 'completion-manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest['schema'] == 'clinical-study-artifacts/v1'
    assert manifest['state'] == 'complete'
    assert first['manifest_sha256'] == hashlib.sha256(manifest_bytes).hexdigest()
    for artifact in manifest['artifacts']:
        data = (output / artifact['path']).read_bytes()
        assert len(data) == artifact['size_bytes']
        assert hashlib.sha256(data).hexdigest() == artifact['sha256']
    second = report.assemble(plan, output)
    assert second['reused_completed_output'] is True
    assert first['manifest_sha256'] == second['manifest_sha256']
    assert (output / 'cases/full-source/document.json').read_bytes() == (tmp_path / 'document.json').read_bytes()
    assert (output / 'plan.json').read_bytes() == plan.read_bytes()


def test_partial_own_output_resumes_but_changed_inputs_or_artifacts_are_not_overwritten(tmp_path):
    plan, _, _ = fixture(tmp_path)
    output = tmp_path / 'output'
    report.assemble(plan, output)
    (output / 'completion-manifest.json').unlink()
    (output / 'report.md').unlink()
    assert report.assemble(plan, output)['reused_completed_output'] is False
    original = (output / 'measurement.json').read_bytes()
    (output / 'report.md').write_text('retained customer edits')
    with pytest.raises(ValueError, match='not overwritten'):
        report.assemble(plan, output)
    assert (output / 'report.md').read_text() == 'retained customer edits'
    assert (output / 'measurement.json').read_bytes() == original


@pytest.mark.parametrize('mutation', ['schema', 'duplicates', 'path_id', 'missing_transcript', 'secret_field', 'unknown_document'])
def test_invalid_plans_fail_before_output_publication(tmp_path, mutation):
    plan, value, _ = fixture(tmp_path)
    if mutation == 'schema':
        value['schema'] = 'unknown/v9'
    elif mutation == 'duplicates':
        value['cases'].append(copy.deepcopy(value['cases'][0]))
    elif mutation == 'path_id':
        value['cases'][0]['id'] = '../outside'
    elif mutation == 'missing_transcript':
        value['cases'][0].pop('transcript')
    elif mutation == 'secret_field':
        value['cases'][0]['provenance']['api_key'] = 'placeholder-not-a-secret'
    else:
        document = json.loads((tmp_path / 'document.json').read_text())
        document['schema'] = 'clinical-documentation/v99'
        (tmp_path / 'document.json').write_text(json.dumps(document))
    plan.write_text(json.dumps(value))
    output = tmp_path / 'output'
    with pytest.raises(ValueError):
        report.assemble(plan, output)
    assert not output.exists()


def test_cli_has_small_machine_readable_completion_contract(tmp_path):
    plan, _, _ = fixture(tmp_path)
    output = tmp_path / 'out'
    run = subprocess.run([sys.executable, str(Path(report.__file__)), 'assemble',
                          '--plan', str(plan), '--output', str(output)], capture_output=True, text=True, check=True)
    value = json.loads(run.stdout)
    assert value['schema'] == report.BUNDLE_SCHEMA
    assert value['state'] == 'complete'
    assert value['case_count'] == 1
    assert value['inference_submitted'] is False
    assert 'No fever' not in run.stdout
