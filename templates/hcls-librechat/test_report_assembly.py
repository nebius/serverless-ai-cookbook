import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location('report_assembly', Path(__file__).with_name('report-assembly.py'))
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


def test_assembly_preserves_numeric_strings_unicode_and_actual_column_width(tmp_path):
    markdown = tmp_path / 'method.md'
    markdown.write_bytes('Méthode — Å\r\nOriginal paragraph.\r\n'.encode())
    csv = tmp_path / 'rows.csv'
    csv.write_text('run,top_rank,best_overlap,notes\na,1,false,"two|pipes\nand newline"\nb,1,true,1.21090000000\n')
    report, provenance = assembly.assemble('Research result', [
        {'title': 'Method', 'format': 'markdown', 'file': str(markdown)},
        {'title': 'Exact table', 'format': 'csv', 'file': str(csv)}])
    assert markdown.read_bytes() in report
    assert b'| a | 1 | false | two\\|pipes<br>and newline |' in report
    assert b'1.21090000000' in report
    assert provenance['sections'][1]['column_count'] == 4
    assert provenance['sections'][1]['row_count'] == 2
    assert provenance['report_size_bytes'] == len(report) != len(report.decode())
    assert provenance['sections'][0]['source_sha256'] == assembly.digest(markdown.read_bytes())
    assert not provenance['scientific_claims_validated']
    assert not provenance['inference_submitted']


def test_malformed_table_is_not_relabelled_as_success(tmp_path):
    source = tmp_path / 'broken.csv'
    source.write_text('run,top_rank,best_overlap\nrun-a,false\n')
    with pytest.raises(ValueError, match='row width'):
        assembly.assemble('Report', [{'title': 'Rows', 'format': 'csv', 'file': str(source)}])


def plan(tmp_path):
    source = tmp_path / 'measurement.csv'
    source.write_bytes(b'metric,value,unit\nrmsd,18.50753674331944,angstrom\nrecovered_contacts,0,count\n')
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps({'title': 'Negative result retained', 'sections': [
        {'title': 'Actual metrics', 'format': 'csv', 'file': source.name}]}))
    return manifest, source


def test_complete_bundle_retains_sources_units_and_exact_hashes(tmp_path):
    manifest, source = plan(tmp_path)
    directory = tmp_path / 'result'
    receipt = assembly.publish_bundle(manifest, directory)
    completion = json.loads((directory / 'completion-manifest.json').read_bytes())
    assert completion['schema'] == 'scientific-ai/report-artifacts/v1'
    assert completion['state'] == 'complete' and not completion['scientific_claims_validated']
    assert completion['section_count'] == 1
    assert len(completion['artifacts']) == 5
    assert receipt['completion_manifest_sha256'] == assembly.digest((directory / 'completion-manifest.json').read_bytes())
    for artifact in completion['artifacts']:
        data = (directory / artifact['path']).read_bytes()
        assert len(data) == artifact['size_bytes']
        assert assembly.digest(data) == artifact['sha256']
    assert (directory / 'sources/000.csv').read_bytes() == source.read_bytes()
    text = (directory / 'report.md').read_text()
    assert '| rmsd | 18.50753674331944 | angstrom |' in text
    assert '| recovered_contacts | 0 | count |' in text
    assert 'not scientific truth' in text
    assert assembly.publish_bundle(manifest, directory) == receipt


def test_different_prior_report_is_preserved_not_published_as_complete(tmp_path):
    manifest, _ = plan(tmp_path)
    directory = tmp_path / 'result'
    directory.mkdir()
    (directory / 'report.md').write_bytes(b'earlier evidence')
    with pytest.raises(RuntimeError, match='differ'):
        assembly.publish_bundle(manifest, directory)
    assert (directory / 'report.md').read_bytes() == b'earlier evidence'
    assert not (directory / 'completion-manifest.json').exists()


def test_partial_publication_resumes_exact_bytes_and_changed_input_rejected(tmp_path, monkeypatch):
    manifest, source = plan(tmp_path)
    directory = tmp_path / 'result'
    actual_publisher = assembly.staged_output
    def interrupted(target):
        if target.name == 'provenance.json':
            raise OSError('simulated interrupted storage')
        return actual_publisher(target)
    monkeypatch.setattr(assembly, 'staged_output', interrupted)
    with pytest.raises(OSError, match='interrupted'):
        assembly.publish_bundle(manifest, directory)
    original = (directory / 'report.md').read_bytes()
    assert not (directory / 'completion-manifest.json').exists()
    monkeypatch.setattr(assembly, 'staged_output', actual_publisher)
    assembly.publish_bundle(manifest, directory)
    assert (directory / 'report.md').read_bytes() == original
    before = (directory / 'completion-manifest.json').read_bytes()
    source.write_text('metric,value,unit\nrmsd,0,angstrom\n')
    with pytest.raises(RuntimeError, match='differ'):
        assembly.publish_bundle(manifest, directory)
    assert (directory / 'completion-manifest.json').read_bytes() == before


def test_empty_or_invalid_report_rejected_before_any_publication(tmp_path):
    manifest, source = plan(tmp_path)
    source.write_bytes(b'')
    directory = tmp_path / 'result'
    with pytest.raises(ValueError, match='empty source'):
        assembly.publish_bundle(manifest, directory)
    assert not directory.exists()


def test_cli_produces_same_contract_without_an_llm_turn(tmp_path):
    manifest, _ = plan(tmp_path)
    output = tmp_path / 'result'
    completed = subprocess.run([sys.executable, spec.origin, '--manifest', str(manifest),
        '--output-dir', str(output)], capture_output=True, text=True, check=True)
    receipt = json.loads(completed.stdout)
    assert receipt['section_count'] == 1 and not receipt['inference_submitted']
    assert Path(receipt['completion_manifest']).is_file()


def values(kind, document):
    text, measurements = assembly.measurement_section(kind, json.dumps(document).encode())
    return text, {row['measurement']: row for row in measurements['measurements']}


def test_evo_milliseconds_are_explicitly_converted_not_called_gpu_time():
    text, rows = values('operation-timing', {'elapsed_ms': 2951.319835})
    assert rows['elapsed_ms']['value'] == 2951.319835 and rows['elapsed_ms']['unit'] == 'ms'
    assert rows['model_reported_elapsed_seconds']['value'] == '2.951319835'
    assert rows['accepted_to_completed']['value'] is None
    assert 'unavailable' in text and 'not pure cold start' in text
    assert '2951.319835 | ms' in text and '2.951319835 | s' in text


def test_waiting_service_and_explicit_cold_measurements_remain_separate():
    _, rows = values('operation-timing', {'structuredContent': {
        'created_at': '2026-09-19T12:00:00Z', 'started_at': '2026-09-19T12:00:10Z',
        'completed_at': '2026-09-19T12:00:14.5Z', 'cold_start_seconds': 8,
        'reserved_gpu_seconds': 50}})
    assert rows['accepted_to_started']['value'] == 10
    assert rows['started_to_completed']['value'] == 4.5
    assert rows['accepted_to_completed']['value'] == 14.5
    assert rows['cold_start_seconds']['value'] == 8
    assert 'reservation' in rows['reserved_gpu_seconds']['unit']


@pytest.mark.parametrize('document', [
    {'elapsed_ms': -1}, {'elapsed_ms': True}, {'elapsed_ms': float('nan')},
    {'created_at': '2026-09-19T12:00:10Z', 'started_at': '2026-09-19T12:00:00Z'},
    {'created_at': '2026-09-19T12:00:00', 'started_at': '2026-09-19T12:00:10'},
])
def test_invalid_or_negative_timing_never_published(document):
    with pytest.raises(ValueError):
        values('operation-timing', document)


def export_document(rows=128):
    fields = [
        {'name': 'state_action', 'dtype': '<f4', 'shape': [rows, 43], 'scalar_values': rows * 43},
        {'name': 'indexes', 'dtype': '<i8', 'shape': [rows, 4], 'scalar_values': rows * 4},
        {'name': 'valid', 'dtype': '|b1', 'shape': [rows], 'scalar_values': rows}]
    return {'schema': 'scientific-recorded-export/v1', 'row_count': rows, 'field_count': len(fields),
            'scalar_values': rows * 48, 'fields': fields}


@pytest.mark.parametrize('rows', [1, 3, 128, 256])
def test_export_total_is_not_float_only_and_generalizes(rows):
    text, measured = values('recorded-export', export_document(rows))
    assert measured['all_scalar_values']['value'] == rows * 48
    assert measured['floating_scalar_values']['value'] == rows * 43
    assert measured['integer_scalar_values']['value'] == rows * 4
    assert measured['boolean_scalar_values']['value'] == rows
    if rows == 128:
        assert '6144' in text and '5504' in text
    assert 'physical action-label validity' in text


def test_export_inconsistent_totals_shapes_and_dtype_rejected():
    for change in ('total', 'shape', 'dtype', 'name'):
        document = export_document()
        if change == 'total':
            document['scalar_values'] = 5504
        elif change == 'shape':
            document['fields'][0]['shape'] = [127, 43]
        elif change == 'dtype':
            document['fields'][0]['dtype'] = '|O'
        else:
            document['fields'][0]['name'] = 'valid'
        with pytest.raises(ValueError):
            values('recorded-export', document)


def test_rgb_mean_is_not_luminance_or_physical_validity():
    text, rows = values('rgb-statistics', {'results': [
        {'role': 'source', 'mean_rgb_float64': [0, 30, 60]},
        {'role': 'output', 'mean_rgb_float64': [90, 120, 150], 'weighted_rgb_601_proxy_float64': 114.45}]})
    assert rows['source.unweighted_RGB_mean']['value'] == 30
    assert rows['output.unweighted_RGB_mean']['value'] == 120
    assert rows['source.weighted_RGB_proxy']['value'] is None
    assert 'NOT luminance' in text and 'not a recomputation' in text
    assert 'no photometric or physical-action validation' in text


def test_rgb_rejects_ambiguous_unlabelled_average():
    with pytest.raises(ValueError):
        values('rgb-statistics', {'results': [{'role': 'source', 'mean': 120, 'luminance': 120}]})
    with pytest.raises(ValueError):
        values('rgb-statistics', {'results': [{'role': 'source', 'mean_rgb_float64': [0, 0, 256]}]})


def test_mindeval_counts_actual_axes_profiles_and_cells_not_a_guessed_dimension():
    document = {'data': [
        {'id': f'{profile}-{model}', 'state': {'config': {'profile_id': profile, 'clinician_model': model},
            'judgment': {'judgment': {f'axis-{i}': i + 1 for i in range(5)}}}}
        for profile in ['p1', 'p2'] for model in ['a', 'b', 'c']]}
    text, rows = values('mindeval-runs', document)
    assert rows['consultations']['value'] == 6
    assert rows['distinct_criteria']['value'] == 5
    assert rows['distinct_profiles']['value'] == 2
    assert rows['distinct_clinicians']['value'] == 3
    assert rows['profile_criterion_cells']['value'] == 10
    assert 'NOT criteria' in text and 'No missing rows are fabricated' in text
    document['data'].append(document['data'][0])
    with pytest.raises(ValueError, match='unique'):
        values('mindeval-runs', document)


def test_mindeval_missing_judge_is_unavailable_not_zero_axes():
    _, rows = values('mindeval-runs', {'data': [{'id': 'pending', 'state': {'config': {}}}]})
    assert rows['scored_consultations']['value'] == 0
    assert rows['distinct_criteria']['value'] is None
    assert rows['profile_criterion_cells']['value'] is None


def test_domain_adapter_outputs_are_retained_in_publication_manifest(tmp_path):
    source = tmp_path / 'elapsed.json'
    source.write_text('{"elapsed_ms":2951.319835}')
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps({'title': 'Measured duration', 'sections': [
        {'title': 'Evo2 model telemetry', 'format': 'operation-timing', 'file': source.name}]}))
    directory = tmp_path / 'output'
    assembly.publish_bundle(manifest, directory)
    provenance = json.loads((directory / 'provenance.json').read_bytes())
    assert provenance['sections'][0]['measurements']['kind'] == 'operation-timing'
    assert (directory / 'sources/000.json').read_bytes() == source.read_bytes()
    assert '2.951319835 | s' in (directory / 'report.md').read_text()
