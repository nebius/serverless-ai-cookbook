import hashlib
import importlib.util
from pathlib import Path
import types
import wave


spec = importlib.util.spec_from_file_location('speech_analysis', Path(__file__).with_name('speech-analysis.py'))
pipeline = importlib.util.module_from_spec(spec); spec.loader.exec_module(pipeline)


def make_wav(path, seconds=1, rate=16000):
    frames = (b'\x00\x00' + b'\x30\x00') * (seconds * rate // 2)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(rate); audio.writeframes(frames)


def test_two_model_speech_pipeline_admits_each_model_once_and_preserves_full_events(tmp_path):
    source = tmp_path / 'conversation.wav'; make_wav(source)
    args = types.SimpleNamespace(source=source, output_dir=tmp_path / 'output',
                                 idempotency_key='speech-recording-test', wait_seconds=30,
                                 recover_only=False)
    commands = []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        model = command[command.index('--model') + 1]
        if command[1].endswith('upload-artifact.py'):
            raw = source.read_bytes(); pipeline.save(target / 'artifact.json', {
                'artifact_id': ('11111111-1111-4111-8111-111111111111' if model.startswith('parakeet')
                                else '22222222-2222-4222-8222-222222222222'),
                'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'media_type': 'audio/wav', 'compression': 'none'})
        else:
            if model.startswith('parakeet'):
                events = [{'type': 'transcript.final', 'segment': 0, 'text': 'Hello doctor.'},
                          {'type': 'turn.eou', 'segment': 0, 'source': 'model_token',
                           'probability': 0.9, 'audio_offset_seconds': 0.8}]
                text = 'Hello doctor.'
            else:
                events = [{'type': 'speaker.activity', 'start_seconds': 0,
                           'frame_duration_seconds': 0.08,
                           'speakers': ['speaker_0', 'speaker_1', 'speaker_2', 'speaker_3'],
                           'probabilities': [[0.9, 0.05, 0.03, 0.02] for _ in range(13)]}]
                text = ''
            pipeline.save(target / 'result.json', {'model': model, 'audio_seconds': 1.0,
                                                   'events': events, 'text': text,
                                                   'processing_seconds': 0.5})
            identifier = 'asr-operation' if model.startswith('parakeet') else 'diar-operation'
            pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': identifier})
            pipeline.save(target / 'operation.json', {'structuredContent': {'id': identifier,
                'accepted_at': '2026-09-21T00:00:00Z', 'completed_at': '2026-09-21T00:00:01Z'}})
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0
    assert result['transcription']['text'] == 'Hello doctor.'
    assert result['transcription']['operation_id'] == 'asr-operation'
    assert result['diarization']['operation_id'] == 'diar-operation'
    assert result['timeline_metrics']['eou_marker_count'] == 1
    assert [Path(command[1]).name for command in commands] == [
        'upload-artifact.py', 'invoke-native.py', 'upload-artifact.py', 'invoke-native.py']
    assert Path(result['timeline_path']).read_bytes().startswith(b'\x89PNG')
    assert Path(result['transcript_path']).read_text() == 'Hello doctor.\n'
