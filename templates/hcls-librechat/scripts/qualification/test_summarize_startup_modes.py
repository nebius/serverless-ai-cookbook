import json

import numpy as np
import pytest

from summarize_startup_modes import analyze, distribution, json_log_records, mechanism, seconds, sha, structure_comparison, structure_data


def pdb(translation=0):
    coordinates = [(0, 0, 0), (3.8, 0, 0), (3.8, 3.8, 0), (0, 3.8, 1)]
    return '\n'.join(f'ATOM  {i:5d}  CA  ALA A{i:4d}    {x + translation:8.3f}{y:8.3f}{z:8.3f}  1.00 90.00           C  '
                     for i, (x, y, z) in enumerate(coordinates, 1)) + '\nEND\n'


def test_actual_mechanism_does_not_pool_mixed_or_unknown_workers():
    pods = {'a': {'attempt_id': 'first'}, 'b': {'attempt_id': 'second'}}
    records = [{'pod_uid': 'a', 'mechanism': 'cuda-criu-restored'},
               {'pod_uid': 'b', 'mechanism': 'normal-load-fallback'}]
    assert mechanism('cuda-criu', pods, records) == 'mixed-restore-and-normal-fallback'
    assert mechanism('cuda-criu', pods, records[:1]) == 'unknown-or-incomplete-worker-mechanism'
    assert mechanism('cuda-criu', {'a': pods['a']}, records[:1], expected_attempt_ids=['first', 'second']) == 'unknown-or-incomplete-worker-mechanism'
    records[1]['mechanism'] = 'cuda-criu-restored'
    assert mechanism('cuda-criu', pods, records) == 'all-observed-workers-restored'
    assert mechanism('normal-load', pods, []) == 'normal-load-requested; no restore observed'


def test_multiline_restore_record_and_repeated_log_shapes_are_parsed():
    text = '\n'.join('2026-09-19T13:00:00.123456789Z ' + line for line in [
        'not JSON {broken', '{', '"action":"restore",', '"records":[{"seconds":12.3}],',
        '"runtime_identity":{"driver_version":"580.159.04"}', '}',
        '{"event":"scientific_snapshot_request","mechanism":"cuda-criu-restored"}'])
    parsed = list(json_log_records(text))
    assert len(parsed) == 2
    assert parsed[0]['runtime_identity']['driver_version'] == '580.159.04'
    assert parsed[1]['mechanism'] == 'cuda-criu-restored'


def test_durations_keep_missing_not_zero_and_reject_negative_or_naive():
    assert seconds(None, '2026-09-19T13:00:00Z') is None
    assert seconds('2026-09-19T13:00:00Z', '2026-09-19T13:00:01.5Z') == 1.5
    with pytest.raises(ValueError, match='Negative'):
        seconds('2026-09-19T13:00:02Z', '2026-09-19T13:00:01Z')
    with pytest.raises(ValueError, match='timezone'):
        seconds('2026-09-19T13:00:00', '2026-09-19T13:00:01')
    assert distribution([None, 1, 3]) == {'n': 2, 'missing': 1, 'min': 1, 'median': 2,
        'max': 3, 'population_stddev': 1, 'unit': 'seconds', 'qualification': 'exploratory, not a percentile SLO'}


def test_structure_comparison_preserves_frame_shift_and_no_unstated_tolerance():
    _, _, geometry = structure_data(pdb())
    assert geometry['protein_ca_count'] == 4 and geometry['finite_coordinates']
    result = structure_comparison(pdb(), pdb(translation=5))
    assert result['raw_ca_rmsd_angstrom'] == pytest.approx(5)
    assert result['jointly_fitted_ca_rmsd_angstrom'] < 1e-6
    assert not result['identical_coordinate_bytes']
    assert 'descriptive_only' in result['equivalence_verdict']
    mismatch = structure_comparison(pdb(), pdb().replace('ALA', 'GLY'))
    assert mismatch['comparable'] is False


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_summary_preserves_failed_and_partial_samples_and_does_not_sum_overlapping_phases(tmp_path):
    save(tmp_path / 'comparison.json', {'identity': {'stage': 'fold', 'model': 'example'},
        'samples': [], 'measurement_scope': 'warm-node-fresh-pod-not-cold-node', 'policy_active': True})
    folder = tmp_path / 'experiment-r1-normal-load'
    save(folder / 'receipt.json', {'identity': {'request_sha256': 'a' * 64}, 'state': 'failed',
        'started_at': '2026-09-19T13:00:00Z', 'finished_at': '2026-09-19T13:00:10Z'})
    save(folder / 'operator-accounting.json', {'data': {'lifecycle_phases': [
        {'phase': 'restore', 'duration': {'value': 7, 'unit': 'seconds', 'evidence': 'estimated'}},
        {'phase': 'active-compute', 'duration': {'value': 8, 'unit': 'seconds', 'evidence': 'estimated'}}]}})
    other = tmp_path / 'experiment-r1-cuda-criu'
    save(other / 'receipt.json', {'identity': {'request_sha256': 'a' * 64}, 'state': 'accepted',
        'started_at': '2026-09-19T13:00:11Z'})
    summary = analyze(tmp_path)
    assert {row['state'] for row in summary['samples']} == {'failed', 'accepted'}
    assert not summary['policy_restored']
    assert summary['samples'][0]['client_wall_seconds'] is None
    normal = next(row for row in summary['samples'] if row['state'] == 'failed')
    assert normal['client_wall_seconds'] == 10
    assert normal['lifecycle_phase_estimates'][0]['duration']['evidence'] == 'estimated'
    assert 'gpu_seconds' not in normal  # Overlapping 7+8 must not become utilization.
    assert summary['matched_repetition_pairs'][0]['same_request_identity']
    assert not summary['matched_repetition_pairs'][0]['same_named_structure_set']


def test_bad_hash_is_independent_failure_and_no_coordinates_leak_into_summary(tmp_path):
    save(tmp_path / 'comparison.json', {'identity': {'stage': 'fold', 'model': 'example'},
        'samples': [], 'measurement_scope': 'warm-node-fresh-pod-not-cold-node', 'policy_active': False})
    folder = tmp_path / 'experiment-r1-normal-load'
    save(folder / 'receipt.json', {'identity': {'request_sha256': 'b' * 64}, 'state': 'verified'})
    save(folder / 'verified-artifacts.json', {'outputs': [
        {'artifact_name': 'prediction', 'structure': pdb(), 'verified_sha256': '0' * 64}]})
    summary = analyze(tmp_path)
    result = summary['samples'][0]['independent_structure_checks'][0]
    assert result['parsed'] is False and 'hash differs' in result['error']
    assert result['text_sha256'] == sha(pdb().encode())
    assert 'ATOM  ' not in json.dumps(summary)


@pytest.mark.parametrize('values', [[np.nan], [np.inf], [-1]])
def test_bad_distribution_measurements_fail(values):
    with pytest.raises(ValueError):
        distribution(values)
