"""Independent contracts for reused full MindEval records; no provider calls."""
import csv
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    'mindeval_report_adapter', Path(__file__).with_name('report-assembly.py'))
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(identity='run-a', profile='profile-a', clinician='clinician-a', scores=None):
    return {
        'id': identity, 'status': 'completed',
        'state': {
            'config': {'profile_id': profile, 'clinician_model': clinician,
                       'patient_model': 'fixed-patient', 'max_turns': 1},
            'transcript': [
                {'role': 'clinician', 'content': 'Original seed — do not summarize.', 'seed': True},
                {'role': 'patient', 'content': 'Literal paragraph\r\nwith Å and pipes | intact.'},
                {'role': 'clinician', 'content': 'Question, not an established patient fact.'}],
            'judgment': {'model': 'fixed-judge', 'provider_model': 'exact-provider-id',
                         'judgment': {'elicitation': 2, 'empathy': 4} if scores is None else scores},
            'intervened': False,
        },
    }


def plan(tmp_path, records):
    paths = []
    for index, item in enumerate(records):
        path = tmp_path / f'original-{index}.json'
        # Distinct whitespace and Unicode bytes are intentionally preserved.
        path.write_bytes((json.dumps(item, ensure_ascii=False, indent=3) + '\r\n').encode())
        paths.append(path)
    source = tmp_path / 'plan.json'
    source.write_text(json.dumps({'title': 'Reused conversations — descriptive only',
                                  'records': [p.name for p in paths]}))
    return source, paths


def measurements(output):
    data = json.loads((output / 'measurements.json').read_bytes())
    return data, {row['measurement']: row['value'] for row in data['measurements']}


def assert_closed_manifest(output):
    document = json.loads((output / 'completion-manifest.json').read_bytes())
    assert document['state'] == 'complete'
    assert document['inference_submitted'] is False
    assert document['scientific_claims_validated'] is False
    names = [row['path'] for row in document['artifacts']]
    assert len(names) == len(set(names))
    for row in document['artifacts']:
        data = (output / row['path']).read_bytes()
        assert len(data) == row['size_bytes']
        assert sha(data) == row['sha256']
    return document


def test_full_records_transcripts_sections_and_provenance_remain_replayable(tmp_path):
    originals = [record(), record('run-b', 'profile-b', 'clinician-b')]
    source, paths = plan(tmp_path, originals)
    before = {p: p.read_bytes() for p in paths}
    output = tmp_path / 'report'
    receipt = adapter.publish_mindeval(source, output)
    completion = assert_closed_manifest(output)
    assert receipt['record_count'] == completion['record_count'] == 2
    assert receipt['message_count'] == 6
    provenance = json.loads((output / 'provenance.json').read_bytes())
    assert provenance['reused_results'] is True
    assert provenance['manifest_sha256'] == sha(source.read_bytes())
    assert provenance['helper_sha256'] == sha((output / 'helper.py').read_bytes())
    for index, (original, path) in enumerate(zip(originals, paths)):
        assert path.read_bytes() == before[path]
        assert (output / f'records/{index:03d}.json').read_bytes() == before[path]
        rendered = ''.join(f'[{i + 1}] {m["role"]}\n{m["content"]}\n\n'
                           for i, m in enumerate(original['state']['transcript'])).encode()
        assert (output / f'transcripts/{index:03d}.txt').read_bytes() == rendered
        assert provenance['inputs'][index]['sha256'] == sha(before[path])
    # Every source named in the actual report lineage must itself be published.
    for section in provenance['sections']:
        assert sha((output / section['source_file']).read_bytes()) == section['source_sha256']
    methods = (output / 'methods.md').read_text()
    assert 'no new consultations' in methods
    assert 'not the configured number' in methods
    assert 'clinical efficacy' in methods
    assert adapter.publish_mindeval(source, output) == receipt


@pytest.mark.parametrize('count', [1, 3, 7])
def test_counts_derive_from_actual_records_not_campaign_constants(tmp_path, count):
    source, _ = plan(tmp_path, [record(f'run-{i}', f'profile-{i}', f'clinician-{i}')
                                for i in range(count)])
    output = tmp_path / 'report'
    adapter.publish_mindeval(source, output)
    data, values = measurements(output)
    assert values['consultations'] == count
    assert values['scored_consultations'] == count
    assert values['distinct_criteria'] == 2
    assert values['distinct_profiles'] == count
    assert values['distinct_clinicians'] == count
    assert values['profile_criterion_cells'] == 2 * count
    assert data['message_count'] == 3 * count
    assert data['supplied_score_rows'] == data['score_rows'] == 2 * count


def test_partial_and_absent_scores_stay_unavailable_not_zero(tmp_path):
    missing = record('run-c', 'profile-b', 'clinician-c')
    missing['status'] = 'failed'
    missing['state']['judgment'] = None
    missing['state']['intervened'] = True
    source, _ = plan(tmp_path, [record(), record('run-b', scores={'elicitation': 5}), missing])
    output = tmp_path / 'report'
    adapter.publish_mindeval(source, output)
    data, values = measurements(output)
    assert values['consultations'] == 3 and values['scored_consultations'] == 2
    assert data['score_rows'] == 6 and data['supplied_score_rows'] == 3
    with (output / 'scores.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert {(r['run_id'], r['criterion']) for r in rows if r['measurement_state'] == 'unavailable'} == {
        ('run-b', 'empathy'), ('run-c', 'elicitation'), ('run-c', 'empathy')}
    assert all(row['score'] == '' for row in rows if row['measurement_state'] == 'unavailable')
    with (output / 'runs.csv').open() as stream:
        runs = list(csv.DictReader(stream))
    assert runs[2]['status'] == 'failed' and runs[2]['intervened'] == 'True'
    assert runs[2]['judgment_state'] == 'unavailable'
    assert all(r['message_count'] == '3' and r['seed_message_count'] == '1' for r in runs)
    assert_closed_manifest(output)


def test_no_judgments_does_not_invent_criteria_or_scores(tmp_path):
    item = record()
    item['state'].pop('judgment')
    source, _ = plan(tmp_path, [item])
    output = tmp_path / 'report'
    adapter.publish_mindeval(source, output)
    data, values = measurements(output)
    assert values['scored_consultations'] == 0
    assert values['distinct_criteria'] is None
    assert values['profile_criterion_cells'] is None
    assert data['score_rows'] == data['supplied_score_rows'] == 0
    assert 'unavailable' in (output / 'report.md').read_text()


@pytest.mark.parametrize('envelope', [[], False, 0, '', 'summary'])
def test_malformed_judgment_envelope_is_not_silently_treated_as_missing(tmp_path, envelope):
    item = record()
    item['state']['judgment'] = envelope
    source, _ = plan(tmp_path, [item])
    output = tmp_path / 'report'
    with pytest.raises(ValueError, match='envelope'):
        adapter.publish_mindeval(source, output)
    assert not output.exists()


@pytest.mark.parametrize('score', [True, None, 0, 7, '5', float('nan')])
def test_invalid_score_is_not_relabelled_as_a_measured_number(tmp_path, score):
    source, _ = plan(tmp_path, [record(scores={'elicitation': score})])
    output = tmp_path / 'report'
    with pytest.raises(ValueError):
        adapter.publish_mindeval(source, output)
    assert not output.exists()


def test_duplicate_run_ids_are_not_independent_observations(tmp_path):
    source, _ = plan(tmp_path, [record(), record()])
    output = tmp_path / 'report'
    with pytest.raises(ValueError, match='unique'):
        adapter.publish_mindeval(source, output)
    assert not output.exists()


@pytest.mark.parametrize('change', ['compact', 'empty', 'no_config', 'bad_message'])
def test_compact_or_invalid_transcript_is_not_a_full_retained_record(tmp_path, change):
    item = record()
    if change == 'compact':
        item = {'id': 'run-a', 'status': 'completed', 'summary': 'Not the full conversation.'}
    elif change == 'empty':
        item['state']['transcript'] = []
    elif change == 'no_config':
        item['state'].pop('config')
    else:
        item['state']['transcript'][0]['content'] = {'not': 'literal text'}
    source, _ = plan(tmp_path, [item])
    output = tmp_path / 'report'
    with pytest.raises(ValueError):
        adapter.publish_mindeval(source, output)
    assert not output.exists()


def test_long_transcripts_and_source_bytes_are_not_truncated(tmp_path):
    item = record()
    item['state']['transcript'][1]['content'] = 'Long original Å paragraph.\n' * 20000
    source, paths = plan(tmp_path, [item])
    output = tmp_path / 'report'
    adapter.publish_mindeval(source, output)
    assert (output / 'records/000.json').read_bytes() == paths[0].read_bytes()
    assert item['state']['transcript'][1]['content'].encode() in (output / 'transcripts/000.txt').read_bytes()
    assert_closed_manifest(output)


def test_existing_conflict_preserves_prior_bytes_without_new_completion(tmp_path):
    source, _ = plan(tmp_path, [record()])
    output = tmp_path / 'report'
    output.mkdir()
    (output / 'report.md').write_bytes(b'Original evidence must survive.')
    with pytest.raises(RuntimeError, match='differ'):
        adapter.publish_mindeval(source, output)
    assert (output / 'report.md').read_bytes() == b'Original evidence must survive.'
    assert not (output / 'completion-manifest.json').exists()


def test_interrupted_publication_resumes_only_identical_sources(tmp_path, monkeypatch):
    source, paths = plan(tmp_path, [record(), record('run-b')])
    output = tmp_path / 'report'
    original_publisher = adapter.staged_output
    def interrupt(target):
        if target.parent.name == 'records' and target.name == '001.json':
            raise OSError('simulated storage interruption')
        return original_publisher(target)
    monkeypatch.setattr(adapter, 'staged_output', interrupt)
    with pytest.raises(OSError, match='interruption'):
        adapter.publish_mindeval(source, output)
    assert not (output / 'completion-manifest.json').exists()
    before = (output / 'records/000.json').read_bytes()
    monkeypatch.setattr(adapter, 'staged_output', original_publisher)
    adapter.publish_mindeval(source, output)
    assert (output / 'records/000.json').read_bytes() == before
    original_manifest = (output / 'completion-manifest.json').read_bytes()
    changed = json.loads(paths[0].read_bytes())
    changed['state']['transcript'][0]['content'] = 'Changed original source.'
    paths[0].write_text(json.dumps(changed))
    with pytest.raises(RuntimeError, match='differ'):
        adapter.publish_mindeval(source, output)
    assert (output / 'completion-manifest.json').read_bytes() == original_manifest
    assert (output / 'records/000.json').read_bytes() == before


def test_bucket_readback_failure_never_publishes_completion(tmp_path, monkeypatch):
    import scientific_receipts
    source, _ = plan(tmp_path, [record()])
    output = tmp_path / 'report'
    original_measurement = scientific_receipts.file_measurement
    def cross_device(*_args, **_kwargs):
        raise OSError(errno.EXDEV, 'simulated bucket mount')
    def mismatch(path):
        if Path(path).parent.name == 'records':
            return 0, 'not-the-written-content'
        return original_measurement(path)
    monkeypatch.setattr(scientific_receipts.os, 'link', cross_device)
    monkeypatch.setattr(scientific_receipts, 'file_measurement', mismatch)
    with pytest.raises(RuntimeError, match='differ'):
        adapter.publish_mindeval(source, output)
    assert not (output / 'completion-manifest.json').exists()


def test_adapter_reuses_existing_score_measurements_exactly(tmp_path):
    records = [record(), record('run-b', scores={'elicitation': 5})]
    source, _ = plan(tmp_path, records)
    output = tmp_path / 'report'
    adapter.publish_mindeval(source, output)
    _, expected = adapter.measurement_section('mindeval-runs', json.dumps({'data': records}).encode())
    actual, _ = measurements(output)
    assert actual['measurements'] == expected['measurements']
    assert actual['limitations'] == expected['limitations']


def test_cli_publishes_full_file_contract_without_another_model_turn(tmp_path):
    source, _ = plan(tmp_path, [record()])
    output = tmp_path / 'report'
    response = subprocess.run([sys.executable, spec.origin, '--mindeval-plan', str(source),
                               '--output-dir', str(output)], capture_output=True, text=True, check=True)
    receipt = json.loads(response.stdout)
    assert receipt['state'] == 'complete' and receipt['inference_submitted'] is False
    assert receipt['record_count'] == 1 and receipt['message_count'] == 3
    assert_closed_manifest(output)


def test_workflow_advertised_mindeval_and_report_files_are_actually_published(tmp_path):
    from scientific_study_schema import PHASE_OUTPUTS
    source, _ = plan(tmp_path, [record()])
    output = tmp_path / 'mindeval'
    adapter.publish_mindeval(source, output)
    assert all((output / name).is_file() and (output / name).stat().st_size > 0
               for name in PHASE_OUTPUTS['mindeval'][0])
    generic_plan = tmp_path / 'generic-plan.json'
    generic_plan.write_text(json.dumps({'title': 'Retained report', 'sections': [
        {'title': 'Original methods', 'format': 'markdown', 'file': str(output / 'methods.md')}]}))
    generic = tmp_path / 'generic'
    adapter.publish_bundle(generic_plan, generic)
    assert all((generic / name).is_file() and (generic / name).stat().st_size > 0
               for name in PHASE_OUTPUTS['report'][0])
