"""Deterministic GenMol result/report contracts, without hosted model calls."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from rdkit import Chem
from rdkit.Chem import Crippen, QED

spec = importlib.util.spec_from_file_location('genmol_analysis', Path(__file__).with_name('molecule-analysis.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def request(count=1, **kwargs):
    return {'smiles': '[*{20-30}]', 'num_molecules': count, **kwargs}


def result(smiles=('CCO',), scoring='QED', **kwargs):
    score = QED.qed if scoring == 'QED' else Crippen.MolLogP
    return {'status': 'success', 'molecules': [
        {'smiles': value, 'score': float(score(Chem.MolFromSmiles(value)))} for value in smiles], **kwargs}


@pytest.mark.parametrize('count', [1, 3, 16])
def test_counts_and_order_are_measured_not_campaign_constants(count):
    report = analysis.analyze_genmol(request(count), result(['C' * n for n in range(1, count + 1)]))
    assert report['requested_count'] == report['returned_count'] == report['valid_count'] == count
    assert report['canonical_unique_valid'] == count
    assert [row['row'] for row in report['rows']] == list(range(1, count + 1))
    assert report['heavy_atom_distribution']['minimum'] == 1
    assert report['heavy_atom_distribution']['maximum'] == count
    assert all(row['score_absolute_error'] == 0 for row in report['rows'])
    assert report['quality_flags'] == []
    assert report['inference_submitted'] is False and report['scientific_claims_validated'] is False


def test_defaults_match_current_hosted_contract_and_mask_is_not_atom_count():
    report = analysis.analyze_genmol({'smiles': '[*{20-30}]'}, result())
    assert report['requested_count'] == 1 and report['scoring'] == 'QED'
    assert report['unique_requested'] is False
    assert report['rows'][0]['heavy_atoms'] == 3  # Not forced into mask range.
    assert 'not a heavy-atom bound' in report['limitations'][0]


def test_invalid_empty_and_canonical_duplicate_rows_remain_visible():
    data = result(['CCO', 'OCC'])
    data['molecules'] += [{'smiles': 'not-a-smiles', 'score': .5}, {'smiles': '', 'score': .2}]
    report = analysis.analyze_genmol(request(5, unique=True), data)
    assert report['returned_count'] == 4 and report['valid_count'] == 2 and report['invalid_count'] == 2
    assert report['canonical_unique_valid'] == 1 and report['canonical_duplicate_valid_count'] == 1
    assert report['rows'][1]['canonical_duplicate_of_row'] == 1
    assert report['rows'][2]['raw_smiles'] == 'not-a-smiles'
    assert report['rows'][2]['independent_qed'] is None
    assert report['rows'][2]['model_score'] == .5
    assert set(report['quality_flags']) == {'underfilled', 'invalid_molecules_retained', 'canonical_duplicates_despite_unique_request'}


def test_missing_scores_and_empty_result_are_not_zero_measurements():
    report = analysis.analyze_genmol(request(), {'molecules': [{'smiles': 'CCO'}]})
    assert report['rows'][0]['model_score'] is None
    assert report['rows'][0]['score_comparison_state'] == 'unavailable'
    assert report['score_compared_count'] == 0
    empty = analysis.analyze_genmol(request(4), {'status': 'failed', 'molecules': []})
    assert empty['underfilled'] and empty['runtime_status'] == 'failed'
    assert empty['qed_distribution'] == {'count': 0, 'minimum': None, 'maximum': None, 'mean': None}


def test_negative_logp_and_score_disagreement_are_unrounded_not_relabelled_qed():
    data = result(scoring='LOGP')
    data['molecules'][0]['score'] -= .000123456789
    report = analysis.analyze_genmol(request(scoring='LogP'), data)
    row = report['rows'][0]
    assert row['independent_logp'] < 0 and row['model_score'] < 0
    assert row['score_absolute_error'] == pytest.approx(.000123456789)
    assert row['independent_qed'] == QED.qed(Chem.MolFromSmiles('CCO'))
    assert report['score_comparison_tolerance'] is None


def test_overfill_and_inconsistent_runtime_counts_stay_flagged():
    report = analysis.analyze_genmol(request(), result(['CC', 'CCC'], metrics={
        'requested_molecules': 2, 'returned_molecules': 99, 'accepted_molecules': True}))
    assert report['overfilled'] and not report['underfilled']
    assert report['returned_count'] == 2
    assert report['quality_flags'] == ['overfilled', 'runtime_count_mismatch']
    assert not any(row['matches'] for row in report['runtime_count_comparisons'].values())


@pytest.mark.parametrize('data', [None, [], {'data': {'molecules': []}}, {'molecules': ['CCO']},
                                  {'molecules': [{}]}, {'molecules': [], 'metrics': []}])
def test_malformed_envelopes_are_not_heuristically_reinterpreted(data):
    with pytest.raises(ValueError):
        analysis.analyze_genmol(request(), data)


@pytest.mark.parametrize('kwargs', [{'num_molecules': True}, {'num_molecules': 0}, {'unique': 'true'},
                                    {'scoring': 'affinity'}, {'smiles': ''}])
def test_malformed_request_fails_explicitly(kwargs):
    original = request()
    original.update(kwargs)
    with pytest.raises(ValueError):
        analysis.analyze_genmol(original, result())


@pytest.mark.parametrize('score', [True, '0.5', float('nan'), float('inf')])
def test_non_numeric_or_nonfinite_supplied_scores_are_not_fabricated(score):
    with pytest.raises(ValueError, match='finite numeric'):
        analysis.analyze_genmol(request(), {'molecules': [{'smiles': 'CCO', 'score': score}]})


def sources(tmp_path):
    request_file, result_file = tmp_path / 'request.json', tmp_path / 'result.json'
    request_file.write_bytes((json.dumps(request(2, unique=True), indent=3) + '\r\n').encode())
    result_file.write_bytes((json.dumps(result(['CCO', 'CCN']), indent=1) + '\n').encode())
    return request_file, result_file


def test_cli_actual_files_closed_manifest_csv_and_provenance(tmp_path):
    request_file, result_file = sources(tmp_path)
    originals = {p: p.read_bytes() for p in (request_file, result_file)}
    output = tmp_path / 'out/metrics.json'
    command = [sys.executable, spec.origin, '--genmol-result', str(result_file),
               '--request', str(request_file), '--output', str(output)]
    subprocess.run(command, check=True, capture_output=True)
    report = json.loads(output.read_bytes())
    completion = json.loads(output.with_name('completion-manifest.json').read_bytes())
    assert sorted(p.name for p in output.parent.iterdir()) == ['completion-manifest.json', 'metrics.json', 'report.md', 'rows.csv']
    assert completion['state'] == 'complete' and completion['inference_submitted'] is False
    for row in completion['artifacts']:
        raw = (output.parent / row['path']).read_bytes()
        assert len(raw) == row['size_bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    for name, path in [('request', request_file), ('result', result_file)]:
        assert path.read_bytes() == originals[path]
        assert report['provenance'][name + '_sha256'] == hashlib.sha256(originals[path]).hexdigest()
    with output.with_name('rows.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert [float(row['independent_qed']) for row in rows] == [row['independent_qed'] for row in report['rows']]
    assert 'not measured affinity' in output.with_name('report.md').read_text()
    before = {p: p.read_bytes() for p in output.parent.iterdir()}
    subprocess.run(command, check=True, capture_output=True)
    assert {p: p.read_bytes() for p in output.parent.iterdir()} == before


def test_cli_never_requires_or_accepts_docking_geometry_for_genmol(tmp_path):
    request_file, result_file = sources(tmp_path)
    base = [sys.executable, spec.origin, '--genmol-result', str(result_file), '--output', str(tmp_path / 'out/metrics.json')]
    assert subprocess.run(base, capture_output=True).returncode != 0
    assert subprocess.run(base + ['--request', str(request_file), '--same-coordinate-frame'], capture_output=True).returncode != 0
    assert not (tmp_path / 'out').exists()


def test_conflicting_output_is_preserved_and_completion_is_not_published(tmp_path):
    request_file, result_file = sources(tmp_path)
    output = tmp_path / 'out/metrics.json'
    output.parent.mkdir()
    output.with_name('report.md').write_bytes(b'Original scientist evidence')
    report = analysis.analyze_genmol_files(request_file, result_file)
    with pytest.raises(RuntimeError, match='differ'):
        analysis.write_genmol_report(report, output)
    assert output.with_name('report.md').read_bytes() == b'Original scientist evidence'
    assert not output.with_name('completion-manifest.json').exists()


def test_invalid_json_number_is_rejected_before_output(tmp_path):
    request_file, result_file = sources(tmp_path)
    result_file.write_text('{"molecules":[{"smiles":"CCO","score":NaN}]}')
    with pytest.raises(ValueError, match='Nonfinite JSON'):
        analysis.analyze_genmol_files(request_file, result_file)
