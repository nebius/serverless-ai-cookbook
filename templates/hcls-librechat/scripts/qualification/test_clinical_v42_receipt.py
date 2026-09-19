"""Keep the historical scoped evidence distinct from readiness or fresh ASR."""
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / 'demos/evidence/20260919-natural-clinical-v42/receipt.json'


def test_receipt_identity_and_nonreadiness():
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest() == 'd93ad8ee30b4414f3e2eb1493de5ddb1ceac73d37f060aa79ed68b4a2ec04d11'
    value = json.loads(RECEIPT.read_text())
    assert not value['clinical_ready'] and not value['platform_ready']
    assert value['source_commit'] == '7674a107eeeb2fce5782030c872adad91e966add'
    assert value['counts'] == {'new_native_asr': 0, 'reused_prior_native_asr': 4,
        'new_artifact_uploads': 2, 'new_clinical_jobs': 3, 'completed_drafts': 2,
        'expected_no_report': 1, 'actual_browser_downloads': 24}


def test_real_timings_and_user_interventions_are_retained():
    value = json.loads(RECEIPT.read_text())
    expected = {'english': (3, 810.688), 'german_full': (1, 130.983),
                'german_negative': (1, 70.097)}
    for row in value['cohorts']:
        start = datetime.fromisoformat(row['first_user_at'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(row['final_assistant_at'].replace('Z', '+00:00'))
        assert (end-start).total_seconds() == row['user_to_final_seconds']
        assert (row['user_turns'], row['user_to_final_seconds']) == expected[row['name']]
        assert row['ordinary_continuations'] == row['user_turns'] - 1
        assert row['job_duration_seconds'] < row['user_to_final_seconds']
        assert all(x['bytes'] > 0 and x['equals_retained_api_or_workspace']
                   for x in row['browser_downloads'])


def test_expected_negative_and_method_failures_not_erased():
    value = json.loads(RECEIPT.read_text())
    negative = next(row for row in value['cohorts'] if row['name'] == 'german_negative')
    assert negative['status'] == 'incomplete'
    assert negative['error_code'] == 'no_supported_clinical_facts'
    assert negative['outcome'] == 'expected_no_supported_facts_no_provider_report'
    assert len(value['measurement_replays']) == 5
    assert all(row['exact_bytes_reproduced'] for row in value['measurement_replays'])
    kinds = {row['kind'] for row in value['residuals']}
    assert {'client_delivery', 'incorrect_ad_hoc_analysis', 'coverage_method_confusion',
            'unsupported_omission_claim', 'unsupported_causal_explanation',
            'clinical_utility_limits'} <= kinds
