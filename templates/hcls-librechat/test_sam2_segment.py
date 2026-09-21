import hashlib
import importlib.util
import io
import json
from pathlib import Path
import types
import zipfile

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location('sam2_segment', Path(__file__).with_name('sam2-segment.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def png_bytes(values):
    target = io.BytesIO(); Image.fromarray(np.asarray(values, dtype=np.uint16)).save(target, format='PNG')
    return target.getvalue()


def options(tmp_path):
    source = tmp_path / 'source.png'; Image.new('RGB', (4, 3), color=(20, 40, 60)).save(source)
    return types.SimpleNamespace(
        source=source, mode='automatic-image', output_dir=tmp_path / 'output',
        idempotency_key='sam2-recording-test', max_masks=32, point_x=None, point_y=None,
        object_id=1, prompt_frame=0, wait_seconds=30, recover_only=False,
        model='sam2-1-hiera-large', tool='segment_track_media_native')


def artifact(source):
    raw = source.read_bytes()
    return {'artifact_id': '11111111-1111-4111-8111-111111111111',
            'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
            'media_type': 'image/png', 'compression': 'none'}


def result_zip(path, source):
    manifest = {'schema': 'fs2.nebius.ai/sam2-result/v1', 'model': 'sam2-1-hiera-large',
                'revision': 'sam2.1-hiera-large', 'mode': 'automatic-image',
                'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'width': 4, 'height': 3,
                'objects': [{'object_id': 1, 'score': 0.9, 'stability_score': 0.95, 'area_px': 3},
                            {'object_id': 2, 'score': 0.8, 'stability_score': 0.94, 'area_px': 2}]}
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('mask.png', png_bytes([[0, 1, 1, 0], [0, 1, 2, 2], [0, 0, 0, 0]]))
        archive.writestr('overlay.png', png_bytes([[0, 1, 1, 0], [0, 1, 2, 2], [0, 0, 0, 0]]))


def test_pipeline_uploads_and_admits_once_then_verifies_mask_areas(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            pipeline.save(target / 'artifact.json', artifact(args.source))
        else:
            archive = target / 'result.zip'; result_zip(archive, args.source)
            identity = pipeline.file_identity(archive)
            pipeline.save(target / 'result.json', {
                'schema': 'scientific-native-file/v1', 'content_type': 'application/zip',
                'artifact': identity, 'file': {'path': str(archive), **identity}})
            pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'sam2-operation'})
            pipeline.save(target / 'operation.json', {'structuredContent': {
                'id': 'sam2-operation', 'accepted_at': '2026-09-21T00:00:00Z',
                'completed_at': '2026-09-21T00:00:02Z'}})
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0 and result['operation_id'] == 'sam2-operation'
    assert result['metrics'] == {'object_count': 2, 'mask_area_pixels': [3, 2],
                                 'mask_area_distribution': {'minimum': 2, 'median': 2.5,
                                                            'maximum': 3, 'total': 5}}
    assert result['license'] == 'Apache-2.0'
    assert [Path(command[1]).name for command in commands] == ['upload-artifact.py', 'invoke-native.py']
    payload = json.loads((args.output_dir / 'input.json').read_text())
    assert payload['media_base64']['sha256'] == hashlib.sha256(args.source.read_bytes()).hexdigest()
    assert Path(result['overlay_path']).read_bytes().startswith(b'\x89PNG')


def test_pending_sam2_operation_is_not_resubmitted_or_extracted(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            pipeline.save(target / 'artifact.json', artifact(args.source)); code = 0
        else:
            pipeline.save(target / 'receipt.json', {'state': 'queued', 'operation_id': 'sam2-pending'}); code = 75
        return types.SimpleNamespace(returncode=code, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 75 and result['operation_id'] == 'sam2-pending'
    assert len(commands) == 2 and not (args.output_dir / 'analysis').exists()
