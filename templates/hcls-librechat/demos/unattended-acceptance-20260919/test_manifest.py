"""Offline prompt integrity checks; these are not natural-client acceptance."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST = json.loads((ROOT / 'manifest.json').read_text())


def test_exact_ten_frozen_natural_prompts_and_distinct_user_outputs():
    rows = MANIFEST['studies']
    assert [row['scientist'] for row in rows] == [f'scientist-{i:02}' for i in range(1, 11)]
    assert len({row['output_directory'] for row in rows}) == 10
    for row in rows:
        path = ROOT / row['prompt']
        assert path.parent == ROOT / 'prompts'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['prompt_sha256']
        text = data.decode()
        assert row['output_directory'] in text
        assert row['output_directory'].startswith(f"/workspace/{row['scientist']}/unattended-20260919/")
        assert 'close the browser' in text
        assert 'continue' in text or 'continuation' in text
        for coaching in ('run_scientific_workflow', 'scientific-workflow/v2', 'execute_command',
                         '/opt/scientific-client', 'study_report.py', 'report-assembly.py'):
            assert coaching not in text
        assert row['checks'] and row['required_inputs'] and row['origin'] and row['reuse']


def test_populations_are_bounded_separate_and_not_claimed_executed():
    rows = MANIFEST['studies']
    assert MANIFEST['state'] == 'prepared_not_executed'
    assert sum(row['new_model_operations_max'] for row in rows) == 33
    assert sum(row.get('new_clinical_draft_attempts_max', 0) for row in rows) == 3
    assert sum(row.get('new_workshop_consultations_max', 0) for row in rows) == 0
    assert MANIFEST['global_limits']['asr_calls'] == 0
    assert MANIFEST['global_limits']['existing_limits_unchanged'] is True


def test_reuse_and_prior_failure_gates_are_explicit_not_hidden():
    by_user = {row['scientist']: row for row in MANIFEST['studies']}
    assert 'no separate MindEval/workshop' in by_user['scientist-09']['explicit_gap']
    assert by_user['scientist-08']['new_model_operations_max'] == 0
    assert len(by_user['scientist-08']['frozen_source_hashes']) == 2
    assert '6144' in ' '.join(by_user['scientist-10']['checks'])
    assert '5504' in ' '.join(by_user['scientist-10']['checks'])
    assert 'time_in_ms divided by1000' in ' '.join(by_user['scientist-06']['checks'])
    assert 'not twelve axes' in ' '.join(by_user['scientist-09']['checks'])
    assert 'not an assumed field or fixed historical32' in ' '.join(by_user['scientist-08']['checks'])


def test_manifest_relative_markdown_links_resolve():
    import re
    for link in re.findall(r'\]\(([^)]+)\)', (ROOT / 'README.md').read_text()):
        if not link.startswith(('http:', 'https:')):
            assert (ROOT / link).exists(), link
