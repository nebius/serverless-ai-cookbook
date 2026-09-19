import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from scientific_clinical import AdmissionUnknown, Checkpoint, guarded_classes
from scientific_receipts import verify_file


def test_checkpoint_restores_exact_files_and_never_mutates_previous_published_inode(tmp_path):
    scratch = tmp_path / 'local'
    scratch.mkdir()
    checkpoint = Checkpoint(tmp_path / 'bucket', scratch)
    checkpoint.persist(scratch / 'run.json', {'status': 'running'})
    original = checkpoint.index['files']['run.json'].copy()
    checkpoint.persist(scratch / 'run.json', {'status': 'completed'})
    verify_file(Path(original['path']), original)
    assert json.loads(Path(original['path']).read_text())['status'] == 'running'
    restored = Checkpoint(tmp_path / 'bucket', tmp_path / 'new-process')
    assert json.loads((restored.local / 'run.json').read_text())['status'] == 'completed'


def fixture_module(checkpoint, provider_calls):
    class Platform:
        def __init__(self, output):
            self.output = output

        def operation(self, stage, endpoint, payload):
            provider_calls.append('observe-platform')
            return {'same_operation': json.loads((self.output / 'calls' / stage / 'state.json').read_text())['operation_id']}

    class Reporter:
        def __init__(self, platform):
            self.platform, self.provider = platform, True

        def complete(self, stage, prompt, data):
            folder = self.platform.output / 'calls' / stage
            if (folder / 'response.json').exists():
                return json.loads((folder / 'response.json').read_text())
            checkpoint.persist(folder / 'request.json', {'prompt': prompt, 'data': data})
            provider_calls.append('provider-call')
            if data.get('crash'):
                raise SystemExit('lost response after submission')
            result = {'facts': ['literal test phrase']}
            checkpoint.persist(folder / 'response.json', result)
            return result

    return SimpleNamespace(Platform=Platform, Reporter=Reporter,
                           read=lambda path: json.loads(path.read_text()))


def test_provider_completed_response_reused_after_restart_without_another_call(tmp_path):
    first = Checkpoint(tmp_path / 'bucket', tmp_path / 'local')
    calls = []
    module = fixture_module(first, calls)
    platform, reporter = guarded_classes(module, first, lambda: False)
    assert reporter(platform(first.local)).complete('extract', 'original prompt', {})['facts']
    second = Checkpoint(tmp_path / 'bucket', tmp_path / 'restarted')
    module = fixture_module(second, calls)
    platform, reporter = guarded_classes(module, second, lambda: False)
    assert reporter(platform(second.local)).complete('extract', 'original prompt', {})['facts']
    assert calls == ['provider-call']


def test_lost_provider_response_blocks_duplicate_and_platform_confirmed_id_is_observed(tmp_path):
    first = Checkpoint(tmp_path / 'bucket', tmp_path / 'local')
    calls = []
    module = fixture_module(first, calls)
    platform, reporter = guarded_classes(module, first, lambda: False)
    with pytest.raises(SystemExit):
        reporter(platform(first.local)).complete('extract', 'prompt', {'crash': True})
    restarted = Checkpoint(tmp_path / 'bucket', tmp_path / 'restart')
    module = fixture_module(restarted, calls)
    platform, reporter = guarded_classes(module, restarted, lambda: False)
    with pytest.raises(AdmissionUnknown):
        reporter(platform(restarted.local)).complete('extract', 'prompt', {'crash': True})
    assert calls == ['provider-call']
    restarted.persist(restarted.local / 'calls/asr/request.json', {'payload': 'same'})
    with pytest.raises(AdmissionUnknown):
        platform(restarted.local).operation('asr', '/same', {})
    restarted.persist(restarted.local / 'calls/asr/state.json', {'operation_id': 'original-op'})
    assert platform(restarted.local).operation('asr', '/same', {}) == {'same_operation': 'original-op'}
    assert calls == ['provider-call', 'observe-platform']


def test_cancel_prevents_next_provider_call(tmp_path):
    checkpoint = Checkpoint(tmp_path / 'bucket', tmp_path / 'local')
    calls = []
    module = fixture_module(checkpoint, calls)
    platform, reporter = guarded_classes(module, checkpoint, lambda: True)
    with pytest.raises(InterruptedError):
        reporter(platform(checkpoint.local)).complete('extract', 'prompt', {})
    assert calls == []
