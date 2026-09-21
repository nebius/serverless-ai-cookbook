#!/usr/bin/env python3
"""Run one Cosmos Transfer 2.5 video transformation with verified media output."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
import subprocess

from recording_pipeline import (file_identity, immutable_input, invoke, native_file,
                                operation_metadata, publish_copy, timing, upload_source,
                                workspace_urls)
from scientific_receipts import save


def probe(path: Path) -> dict:
    completed = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames:format=duration',
        '-of', 'json', str(path),
    ], capture_output=True, text=True, check=False, timeout=120)
    if completed.returncode:
        raise ValueError('Video could not be inspected with ffprobe.')
    value = json.loads(completed.stdout); streams = value.get('streams')
    if not isinstance(streams, list) or len(streams) != 1:
        raise ValueError('Video must contain exactly one inspectable video stream.')
    stream = streams[0]
    rate = Fraction(stream['avg_frame_rate'])
    return {'width': int(stream['width']), 'height': int(stream['height']),
            'frame_rate': float(rate), 'frame_rate_fraction': str(rate),
            'frame_count': int(stream['nb_read_frames']),
            'duration_seconds': float(value['format']['duration'])}


def run(args, runner=subprocess.run):
    source = args.source.resolve()
    if not source.is_file() or source.suffix.lower() != '.mp4' or not 16 <= source.stat().st_size <= 128 * 1024 * 1024:
        raise ValueError('Cosmos source must be a caller-owned MP4 from 16 bytes through 128 MiB.')
    source_media = probe(source)
    if not 93 <= source_media['frame_count'] <= 480:
        raise ValueError('Cosmos Transfer 2.5 source must contain 93–480 frames.')
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True, mode=0o700)
    upload_dir, run_dir, analysis = output / 'upload', output / 'run', output / 'analysis'
    artifact, code = upload_source(source=source, model=args.model, media_type='video/mp4',
                                   directory=upload_dir, idempotency_key=args.idempotency_key + '-source',
                                   runner=runner)
    if code == 75:
        return {'state': 'upload_pending', 'output_dir': str(output)}, 75
    payload = {'video': artifact, 'prompt': args.prompt, 'negative_prompt': args.negative_prompt,
               'seed': args.seed, 'num_steps': args.num_steps, 'guidance': args.guidance,
               'resolution': str(args.resolution), 'sigma_max': 90,
               'edge': {'control_weight': args.control_weight}, 'output_delivery': 'artifact'}
    input_path = output / 'input.json'; immutable_input(input_path, payload)
    receipt, code = invoke(model=args.model, tool=args.tool, input_path=input_path,
                           directory=run_dir, idempotency_key=args.idempotency_key,
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {**receipt, 'output_dir': str(output)}, code
    generated = native_file(run_dir / 'result.json', 'video/mp4')
    generated_media = probe(generated)
    for field in ('width', 'height', 'frame_count', 'frame_rate_fraction'):
        if generated_media[field] != source_media[field]:
            raise ValueError(f'Cosmos output differs from source {field}.')
    analysis.mkdir(parents=True, exist_ok=True, mode=0o700)
    generated_receipt = publish_copy(generated, analysis / 'transformed.mp4')
    operation = operation_metadata(run_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/cosmos-transfer/v1', 'state': 'succeeded',
        'model': args.model, 'operation_id': operation.get('id') or receipt.get('operation_id'),
        'execution_identity': operation.get('execution_identity'),
        'input': {'path': str(source), **file_identity(source), **source_media},
        'parameters': {key: value for key, value in payload.items() if key != 'video'},
        'output': {**generated_receipt, **generated_media}, 'timing': timing(operation),
        'verified_invariants': ['width', 'height', 'frame_count', 'frame_rate_fraction'],
        'limitations': ['Generated media is not physical ground truth or validated annotation.',
                        'Visual fidelity to prompt and motion requires human review.'],
    }
    save(analysis / 'summary.json', summary)
    generated_path, summary_path = analysis / 'transformed.mp4', analysis / 'summary.json'
    return {**summary, 'source_path': str(source), 'generated_path': str(generated_path),
            'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(source=source, generated=generated_path,
                                             summary=summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--negative-prompt', default='')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--num-steps', type=int, default=35)
    parser.add_argument('--guidance', type=int, default=7)
    parser.add_argument('--resolution', type=int, choices=(256, 480, 512, 720), default=720,
                        help='NIM internal processing resolution; output geometry follows the source video.')
    parser.add_argument('--control-weight', type=float, default=1.0)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=900)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='cosmos-transfer2-5-2b')
    parser.add_argument('--tool', default='infer_cosmos_transfer2_5_2b_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not args.prompt.strip()
            or not 0 <= args.seed <= 4_294_967_295 or args.num_steps < 1
            or not 0 <= args.guidance <= 7 or not 0 <= args.control_weight <= 1
            or not 0 <= args.wait_seconds <= 3600):
        parser.error('Invalid Cosmos prompt, key, seed, steps, guidance, control or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained upload/run/analysis receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
