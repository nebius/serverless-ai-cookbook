#!/usr/bin/env python3
"""Animate one caller-owned image with the Wan2.2 NVIDIA NIM App."""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import subprocess

from recording_pipeline import (file_identity, immutable_input, invoke, native_file,
                                operation_metadata, publish_copy, timing, upload_source,
                                workspace_urls)
from scientific_receipts import save


def probe(path: Path) -> dict:
    completed = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames,codec_name:format=duration',
        '-of', 'json', str(path),
    ], capture_output=True, text=True, check=False, timeout=120)
    if completed.returncode:
        raise ValueError('Wan output could not be inspected with ffprobe.')
    value = json.loads(completed.stdout)
    streams = value.get('streams')
    if not isinstance(streams, list) or len(streams) != 1:
        raise ValueError('Wan output must contain exactly one video stream.')
    stream = streams[0]
    rate = Fraction(stream['avg_frame_rate'])
    result = {
        'codec': stream.get('codec_name'), 'width': int(stream['width']),
        'height': int(stream['height']), 'frame_rate': float(rate),
        'frame_rate_fraction': str(rate), 'frame_count': int(stream['nb_read_frames']),
        'duration_seconds': float(value['format']['duration']),
    }
    if result['frame_count'] < 1 or result['duration_seconds'] <= 0:
        raise ValueError('Wan output has no measurable video duration.')
    return result


def run(args, runner=subprocess.run):
    source = args.source.resolve()
    media_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
    media_type = media_types.get(source.suffix.lower())
    if (not source.is_file() or media_type is None
            or not 16 <= source.stat().st_size <= 16 * 1024 * 1024):
        raise ValueError('Wan image input must be a caller-owned PNG or JPEG from 16 bytes through 16 MiB.')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    upload_dir, run_dir, analysis = output / 'upload', output / 'run', output / 'analysis'
    artifact, code = upload_source(
        source=source, model=args.model, media_type=media_type, directory=upload_dir,
        idempotency_key=args.idempotency_key + '-source', runner=runner)
    if code == 75:
        return {'state': 'upload_pending', 'output_dir': str(output)}, 75
    payload = {
        'prompt': args.prompt, 'input_reference': artifact, 'size': args.size,
        'seconds': args.seconds, 'seed': args.seed, 'steps': args.steps,
        'cfg_scale': args.cfg_scale,
    }
    input_path = output / 'input.json'
    immutable_input(input_path, payload)
    receipt, code = invoke(
        model=args.model, tool=args.tool, input_path=input_path, directory=run_dir,
        idempotency_key=args.idempotency_key, wait_seconds=args.wait_seconds,
        recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {**receipt, 'output_dir': str(output)}, code
    generated = native_file(run_dir / 'result.json', 'video/mp4')
    media = probe(generated)
    expected_width, expected_height = (int(value) for value in args.size.split('x'))
    if (media['width'], media['height']) != (expected_width, expected_height):
        raise ValueError('Wan output geometry differs from the exact requested size.')
    if media['duration_seconds'] > args.seconds + 1:
        raise ValueError('Wan output exceeds the bounded requested duration.')
    analysis.mkdir(parents=True, exist_ok=True, mode=0o700)
    video_receipt = publish_copy(generated, analysis / 'animation.mp4')
    operation = operation_metadata(run_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/wan-image-to-video/v1', 'state': 'succeeded',
        'model': args.model, 'operation_id': operation.get('id') or receipt.get('operation_id'),
        'input': {'path': str(source), 'media_type': media_type, **file_identity(source)},
        'parameters': {key: value for key, value in payload.items() if key != 'input_reference'},
        'output': {**video_receipt, **media}, 'timing': timing(operation),
        'limitations': ['Generated media is not physical ground truth or validated annotation.',
                        'Identity, motion and scene fidelity require human review.',
                        'The NVIDIA NIM content filter remains enabled.'],
    }
    summary_path, video_path = analysis / 'summary.json', analysis / 'animation.mp4'
    save(summary_path, summary)
    return {**summary, 'source_path': str(source), 'generated_path': str(video_path),
            'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(source=source, generated=video_path,
                                             summary=summary_path)}, 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--size', choices=('832x480', '480x832'), default='832x480')
    parser.add_argument('--seconds', type=int, default=4)
    parser.add_argument('--seed', type=int, default=2701)
    parser.add_argument('--steps', type=int, default=50)
    parser.add_argument('--cfg-scale', type=float, default=5)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=900)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='wan2-2-i2v-nim')
    parser.add_argument('--tool', default='animate_image_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not args.prompt.strip()
            or not 1 <= args.seconds <= 12 or not 0 <= args.seed <= 4_294_967_295
            or not 1 <= args.steps <= 100 or not 1 < args.cfg_scale <= 20
            or not 0 <= args.wait_seconds <= 3600):
        parser.error('Invalid Wan prompt, key, duration, seed, steps, guidance or wait.')
    try:
        value, code = run(args)
        print(json.dumps(value, separators=(',', ':')))
        raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained upload/run/analysis receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
