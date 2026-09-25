import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from clinical_asr.cloud import smoke_evaluation_arguments, training_arguments


@pytest.mark.parametrize('family,base', [('nemotron35', 'evaluate'), ('english_specialist', 'evaluate-english')])
def test_cloud_run_preserves_explicit_family_and_same_smoke_membership(tmp_path, family, base):
    args = SimpleNamespace(model_family=family, max_steps=20, val_every=20,
                           batch_duration=120, accumulate_grad_batches=1,
                           learning_rate=3e-5, checkpoint_every=0, seed=20260926,
                           resume_pointer=None)
    train = training_arguments(args, tmp_path)
    assert train[train.index('--model-family') + 1] == family
    assert train[train.index('--learning-rate') + 1] == '3e-05'
    assert '--resume-pointer' not in train
    calls = smoke_evaluation_arguments(tmp_path, 'a' * 64, family)
    assert calls[0][1][0] == base and calls[1][1][0] == 'evaluate'
    assert all(call[call.index('--limit') + 1] == '12' for _, call in calls)
    assert len({call[call.index('--manifest') + 1] for _, call in calls}) == 1
    tuned = calls[1][1]
    assert tuned[tuned.index('--model-family') + 1] == family
    assert tuned[tuned.index('--checkpoint-sha') + 1] == 'a' * 64
    assert '--checkpoint' not in calls[0][1]


@pytest.mark.parametrize('limit,expected', [(None, 14), (12, 12), (1, 1)])
def test_actual_english_evaluator_cli_honors_smoke_limit_without_default_truncation(monkeypatch, tmp_path, limit, expected):
    from clinical_asr import evaluate_english as module
    manifest = tmp_path / 'refs.jsonl'
    output = tmp_path / 'predictions.jsonl'
    rows = [{'id': str(i), 'audio_filepath': str(tmp_path / f'{i}.wav')} for i in range(14)]
    manifest.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(hf_hub_download=lambda *a, **kw: 'pinned.nemo'))
    monkeypatch.setattr(module, 'sha256_file', lambda path: module.CHECKPOINT_SHA)
    fake_runtime = SimpleNamespace(load=lambda: None, identity={'fine_tuned': False})
    monkeypatch.setattr(module, 'NeMoRuntime', lambda **kw: fake_runtime)
    observed = []
    def transcribe(runtime, path, options):
        observed.append(path)
        return {'text': '', 'runtime': runtime.identity}
    monkeypatch.setattr(module, 'transcribe_wav', transcribe)
    argv = ['evaluate-english', '--manifest', str(manifest), '--output', str(output)]
    if limit is not None:
        argv += ['--limit', str(limit)]
    monkeypatch.setattr(sys, 'argv', argv)
    module.main()
    predictions = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row['id'] for row in predictions] == [str(i) for i in range(expected)]
    assert len(observed) == expected
    assert all(row['collapse_warning'] for row in predictions)
    provenance = json.loads(output.with_suffix('.provenance.json').read_text())
    assert provenance['rows'] == expected and provenance['requested_limit'] == limit


@pytest.mark.parametrize('limit', ['0', '-1'])
def test_english_smoke_invalid_limit_fails_before_model_download(monkeypatch, limit):
    from clinical_asr import evaluate_english as module
    monkeypatch.setattr(sys, 'argv', ['evaluate-english', '--manifest', 'unused', '--output', 'unused', '--limit', limit])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('explicit_family', [None, 'english_specialist'])
def test_actual_cloud_run_cli_propagates_family_and_publishes_identity(monkeypatch, tmp_path, explicit_family):
    """Real orchestration entrypoint; cloud transport/GPU subprocesses are fake."""
    import boto3
    from botocore.exceptions import ClientError
    from clinical_asr import cloud, environment
    source_root = tmp_path / 'source'
    output_root = tmp_path / 'output'
    family = explicit_family or 'nemotron35'
    audio_path = source_root / 'audio/a.wav'
    source_rows = [{'id': 'a', 'conversation_id': 'train-a', 'split': 'train',
                    'text': 'original source', 'audio_filepath': str(audio_path)}]
    calls, uploaded = [], []

    class FakeS3:
        def head_object(self, **kwargs):
            raise ClientError({'Error': {'Code': '404'}}, 'HeadObject')

        def download_file(self, bucket, key, destination):
            value = json.dumps(source_rows[0]) + '\n' if key.endswith('.jsonl') else 'fake audio, never inferred'
            Path(destination).write_text(value)

        def upload_file(self, path, bucket, key):
            uploaded.append((key, json.loads(Path(path).read_text())))

    class FakeProcess:
        def __init__(self, argv, **kwargs):
            arguments = argv[3:]
            calls.append(arguments)
            self.stdout = []
            if arguments[0] == 'segment':
                directory = Path(arguments[arguments.index('--output') + 1])
                directory.mkdir(parents=True)
                for label in ('train', 'dev'):
                    (directory / (label + '.jsonl')).write_text(json.dumps(source_rows[0]) + '\n')
            if arguments[0] == 'train':
                directory = Path(arguments[arguments.index('--output') + 1])
                directory.mkdir(parents=True)
                (directory / 'training-provenance.json').write_text(json.dumps({'checkpoint_sha256': 'a' * 64}))

        def wait(self):
            return 0

    def scoped_path(value):
        return {'/data/clinical-speech': source_root, '/output': output_root}.get(str(value), Path(value))

    monkeypatch.setattr(cloud, 'Path', scoped_path)
    monkeypatch.setattr(boto3, 'client', lambda *a, **kw: FakeS3())
    monkeypatch.setattr(cloud.subprocess, 'Popen', FakeProcess)
    monkeypatch.setattr(cloud, 'upload_outputs', lambda *a, **kw: [])
    monkeypatch.setattr(environment, 'collect', lambda: {'scope': 'CPU orchestration fixture only'})
    monkeypatch.setenv('AWS_ENDPOINT_URL', 'https://fixture.invalid')
    argv = ['cloud-run', '--bucket', 'fake-bucket', '--run-id', 'fixture-run']
    if explicit_family:
        argv += ['--model-family', explicit_family]
    monkeypatch.setattr(sys, 'argv', argv)
    cloud.main()
    assert [call[0] for call in calls] == ['align', 'segment', 'train',
        'evaluate-english' if explicit_family else 'evaluate', 'evaluate']
    for call in (calls[2], calls[4]):
        assert call[call.index('--model-family') + 1] == family
    assert uploaded[-1][0] == 'runs/fixture-run/completed.json'
    assert uploaded[-1][1]['model_family'] == family
