import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import types

from PIL import Image


spec = importlib.util.spec_from_file_location(
    'wan_image_to_video', Path(__file__).with_name('wan-image-to-video.py'))
wan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wan)


def make_video(path):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=832x480:r=16', '-frames:v', '64', '-an',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)


def test_wan_pipeline_uploads_once_admits_once_and_verifies_mp4(tmp_path):
    source = tmp_path / 'robot.png'; Image.new('RGB', (96, 64), 'gray').save(source)
    args = types.SimpleNamespace(
        source=source, prompt='One precise pick and place motion', size='832x480', seconds=4,
        seed=2701, steps=50, cfg_scale=5.0, output_dir=tmp_path / 'output',
        idempotency_key='wan-recording-test', wait_seconds=30, recover_only=False,
        model='wan2-2-i2v-nim', tool='animate_image_native')
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            raw = source.read_bytes()
            wan.save(target / 'artifact.json', {
                'artifact_id': '11111111-1111-4111-8111-111111111111',
                'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'media_type': 'image/png', 'compression': 'none'})
        else:
            make_video(target / 'result.mp4')
            raw = (target / 'result.mp4').read_bytes()
            identity = {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}
            wan.save(target / 'result.json', {'schema': 'scientific-native-file/v1',
                'content_type': 'video/mp4', 'artifact': identity,
                'file': {'path': str(target / 'result.mp4'), **identity}})
            wan.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'wan-operation'})
            wan.save(target / 'operation.json', {'structuredContent': {'id': 'wan-operation',
                'accepted_at': '2026-09-21T00:00:00Z', 'completed_at': '2026-09-21T00:04:03Z'}})
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = wan.run(args, runner)
    assert code == 0 and result['operation_id'] == 'wan-operation'
    assert result['output']['width'] == 832 and result['output']['height'] == 480
    assert [Path(command[1]).name for command in commands] == [
        'upload-artifact.py', 'invoke-native.py']
    payload = json.loads((args.output_dir / 'input.json').read_text())
    assert payload['input_reference']['media_type'] == 'image/png'
    assert payload['prompt'] == args.prompt
    assert Path(result['generated_path']).is_file()
