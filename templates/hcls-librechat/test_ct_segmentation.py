import hashlib
import importlib.util
import json
from pathlib import Path
import types

import pytest

spec = importlib.util.spec_from_file_location('ct_segmentation', Path(__file__).with_name('ct-segmentation.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def args(tmp_path):
    source = tmp_path / 'source.nii.gz'
    source.write_bytes(b'fixture-nifti-bytes')
    return types.SimpleNamespace(
        source=source, output_dir=tmp_path / 'output', label_prompt=[1],
        idempotency_key='ct-pipeline-test', model='nv-segment-ct', tool='segment_ct_native',
        media_type='application/gzip', wait_seconds=30, recover_only=False,
    )


def artifact(source):
    data = source.read_bytes()
    return {'artifact_id': '11111111-1111-4111-8111-111111111111',
            'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
            'media_type': 'application/gzip', 'compression': 'none', 'private_extra': 'excluded'}


def test_pipeline_composes_upload_native_and_analysis_without_file_bytes_in_arguments(tmp_path):
    options = args(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[1].endswith('upload-artifact.py'):
            target = Path(command[command.index('--output-dir') + 1])
            target.mkdir(parents=True)
            pipeline.save(target / 'artifact.json', artifact(options.source))
        elif command[1].endswith('invoke-native.py'):
            target = Path(command[command.index('--output-dir') + 1])
            target.mkdir(parents=True)
            pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'operation-1'})
            pipeline.save(target / 'result.json', {'output_nifti_base64': 'fixture'})
        elif command[1].endswith('imaging-analysis.py'):
            target = Path(command[command.index('--output-dir') + 1])
            target.mkdir(parents=True)
            pipeline.save(target / 'metrics.json', {
                'model': 'nv-segment-ct', 'source': {'shape': [64, 64, 64]},
                'prediction': {'shape': [96, 96, 96], 'label_voxel_counts': {'0': 10, '1': 2},
                               'model_seconds': 0.1},
            })
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, exit_code = pipeline.run(options, runner)
    assert exit_code == 0
    assert result['operation_id'] == 'operation-1'
    assert result['input_grid'] == [64, 64, 64]
    assert result['prediction_grid'] == [96, 96, 96]
    assert [Path(command[1]).name for command in commands] == [
        'upload-artifact.py', 'invoke-native.py', 'imaging-analysis.py']
    request = json.loads((options.output_dir / 'input.json').read_text())
    assert request == {'input_nifti_base64': {key: artifact(options.source)[key]
        for key in pipeline.ARTIFACT_FIELDS}, 'label_prompt': [1]}
    assert all(str(options.source.read_bytes()) not in part for command in commands for part in command)


def test_pending_native_operation_is_returned_without_analysis_or_resubmission(tmp_path):
    options = args(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[1].endswith('upload-artifact.py'):
            target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True)
            pipeline.save(target / 'artifact.json', artifact(options.source))
            return types.SimpleNamespace(returncode=0, stdout='', stderr='')
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True)
        pipeline.save(target / 'receipt.json', {'state': 'queued', 'operation_id': 'operation-queued'})
        return types.SimpleNamespace(returncode=75, stdout='', stderr='')

    result, exit_code = pipeline.run(options, runner)
    assert exit_code == 75 and result['operation_id'] == 'operation-queued'
    assert len(commands) == 2


@pytest.mark.parametrize('change,match', [
    (lambda value: value.update(sha256='0' * 64), 'differs'),
    (lambda value: value.update(size_bytes=1), 'differs'),
    (lambda value: value.update(compression='gzip'), 'compression'),
    (lambda value: value.pop('artifact_id'), 'missing'),
])
def test_artifact_mismatch_is_rejected(change, match, tmp_path):
    options = args(tmp_path)
    value = artifact(options.source)
    change(value)
    path = tmp_path / 'artifact.json'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match=match):
        pipeline.verified_artifact_reference(path, options.source)
