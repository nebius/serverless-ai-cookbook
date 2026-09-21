#!/usr/bin/env python3
"""Run one ACE-Step 1.5 generation and retain a verified playable WAV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from recording_pipeline import immutable_input, invoke, native_file, operation_metadata, publish_copy, timing
from scientific_receipts import save


def inspect_wav(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 44 or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE' or int.from_bytes(raw[4:8], 'little') + 8 != len(raw):
        raise ValueError('ACE-Step returned an invalid or truncated RIFF/WAVE file.')
    completed = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_name,sample_fmt,sample_rate,channels,duration:format=duration',
        '-of', 'json', str(path),
    ], capture_output=True, text=True, check=False, timeout=60)
    if completed.returncode:
        raise ValueError('ACE-Step WAV could not be inspected with ffprobe.')
    value = json.loads(completed.stdout); streams = value.get('streams')
    if not isinstance(streams, list) or len(streams) != 1:
        raise ValueError('ACE-Step WAV must contain exactly one audio stream.')
    stream = streams[0]
    duration = stream.get('duration') or value.get('format', {}).get('duration')
    return {'codec': stream.get('codec_name'), 'sample_format': stream.get('sample_fmt'),
            'channels': int(stream['channels']), 'sample_rate_hz': int(stream['sample_rate']),
            'duration_seconds': float(duration)}


def run(args, runner=subprocess.run):
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir, analysis = output / 'run', output / 'analysis'
    payload = {'prompt': args.prompt, 'lyrics': '[Instrumental]',
               'duration_seconds': args.duration_seconds, 'thinking': args.thinking,
               'seed': args.seed, 'bpm': args.bpm, 'key_scale': args.key_scale,
               'time_signature': args.time_signature, 'vocal_language': 'en'}
    input_path = output / 'input.json'; immutable_input(input_path, payload)
    receipt, code = invoke(model=args.model, tool=args.tool, input_path=input_path,
                           directory=run_dir, idempotency_key=args.idempotency_key,
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {**receipt, 'output_dir': str(output)}, code
    generated = native_file(run_dir / 'result.json', 'audio/wav')
    media = inspect_wav(generated)
    if media['duration_seconds'] <= 0 or media['channels'] < 1 or media['sample_rate_hz'] < 1:
        raise ValueError('ACE-Step returned an invalid or empty WAV.')
    analysis.mkdir(parents=True, exist_ok=True, mode=0o700)
    audio_receipt = publish_copy(generated, analysis / 'soundtrack.wav')
    operation = operation_metadata(run_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/ace-step-music/v1', 'state': 'succeeded',
        'model': args.model, 'operation_id': operation.get('id') or receipt.get('operation_id'),
        'execution_identity': operation.get('execution_identity'), 'parameters': payload,
        'output': {**audio_receipt, **media}, 'timing': timing(operation),
        'limitations': ['Generated audio requires human review before publication.',
                        'The returned duration is measured from the WAV, not assumed from the request.'],
    }
    save(analysis / 'summary.json', summary)
    return {**summary, 'audio_path': str(analysis / 'soundtrack.wav'),
            'summary_path': str(analysis / 'summary.json')}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--duration-seconds', type=float, default=45)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--thinking', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--bpm', type=int)
    parser.add_argument('--key-scale', default='')
    parser.add_argument('--time-signature', default='')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=900)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='ace-step-1-5')
    parser.add_argument('--tool', default='generate_music_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not 1 <= len(args.prompt) <= 4096
            or not 10 <= args.duration_seconds <= 60 or not 0 <= args.seed <= 4_294_967_295
            or args.bpm is not None and not 30 <= args.bpm <= 300
            or args.time_signature not in ('', '2', '3', '4', '6', '2/4', '3/4', '4/4', '6/8')
            or not 0 <= args.wait_seconds <= 3600):
        parser.error('Invalid ACE-Step prompt, key, duration, seed, tempo, time signature or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained run/analysis receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
