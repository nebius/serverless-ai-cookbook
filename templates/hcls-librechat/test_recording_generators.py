import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import types
import wave


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


cosmos = load('cosmos_transfer', 'cosmos-transfer.py')
music = load('ace_step_music', 'ace-step-music.py')


def operation(module, path, identifier):
    module.save(path, {'structuredContent': {'id': identifier,
        'accepted_at': '2026-09-21T00:00:00Z', 'completed_at': '2026-09-21T00:00:04Z'}})


def native_file(module, target, filename, media_type):
    path = target / filename; raw = path.read_bytes()
    identity = {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}
    module.save(target / 'result.json', {'schema': 'scientific-native-file/v1',
        'content_type': media_type, 'artifact': identity, 'file': {'path': str(path), **identity}})


def make_video(path):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=128x96:r=24', '-frames:v', '96', '-an', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(path)], check=True)


def test_cosmos_pipeline_has_one_upload_and_one_admission_and_verifies_geometry(tmp_path):
    source = tmp_path / 'source.mp4'; make_video(source)
    args = types.SimpleNamespace(source=source, prompt='Modern robotics laboratory', negative_prompt='',
        seed=11, num_steps=35, guidance=7, control_weight=1.0, output_dir=tmp_path / 'output',
        idempotency_key='cosmos-recording-test', wait_seconds=30, recover_only=False,
        model='cosmos-transfer2-5-2b', tool='infer_cosmos_transfer2_5_2b_native')
    commands = []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            raw = source.read_bytes(); cosmos.save(target / 'artifact.json', {
                'artifact_id': '11111111-1111-4111-8111-111111111111',
                'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'media_type': 'video/mp4', 'compression': 'none'})
        else:
            (target / 'result.mp4').write_bytes(source.read_bytes())
            native_file(cosmos, target, 'result.mp4', 'video/mp4')
            cosmos.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'cosmos-operation'})
            operation(cosmos, target / 'operation.json', 'cosmos-operation')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = cosmos.run(args, runner)
    assert code == 0 and result['operation_id'] == 'cosmos-operation'
    assert result['input']['frame_count'] == result['output']['frame_count'] == 96
    assert result['verified_invariants'] == ['width', 'height', 'frame_count', 'frame_rate_fraction']
    assert [Path(command[1]).name for command in commands] == ['upload-artifact.py', 'invoke-native.py']
    assert Path(result['generated_path']).read_bytes() == source.read_bytes()


def make_wav(path, seconds=1, rate=16000):
    frames = (b'\x00\x00' + b'\x20\x00') * (seconds * rate // 2)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(rate); audio.writeframes(frames)


def test_ace_step_pipeline_has_one_admission_and_measures_returned_wav(tmp_path):
    args = types.SimpleNamespace(prompt='Instrumental scientific technology', duration_seconds=45.0,
        thinking=True, seed=7, bpm=None, key_scale='', time_signature='', output_dir=tmp_path / 'output',
        idempotency_key='ace-step-recording-test', wait_seconds=30, recover_only=False,
        model='ace-step-1-5', tool='generate_music_native')
    commands = []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True); make_wav(target / 'result.wav')
        native_file(music, target, 'result.wav', 'audio/wav')
        music.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'music-operation'})
        operation(music, target / 'operation.json', 'music-operation')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = music.run(args, runner)
    assert code == 0 and result['operation_id'] == 'music-operation'
    assert result['parameters']['lyrics'] == '[Instrumental]'
    assert result['output']['duration_seconds'] == 1.0
    assert len(commands) == 1 and Path(commands[0][1]).name == 'invoke-native.py'
    assert Path(result['audio_path']).read_bytes()[:4] == b'RIFF'
