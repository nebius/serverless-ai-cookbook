#!/usr/bin/env python3
"""Run one SAM2 image/video workflow and materialize its verified mask bundle."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import subprocess

from PIL import Image
import numpy as np

from recording_pipeline import (extract_verified_zip, file_identity, immutable_input, invoke,
                                native_file, operation_metadata, timing, upload_source,
                                workspace_urls)
from scientific_receipts import load, save


MEDIA_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.mp4': 'video/mp4'}


def validate_source(path: Path, mode: str) -> str:
    if not path.is_file() or path.stat().st_size < 16:
        raise ValueError('SAM2 source media is missing or empty.')
    media_type = MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None or (mode == 'prompted-video') != (media_type == 'video/mp4'):
        raise ValueError('SAM2 mode and source extension do not select a supported image/video contract.')
    if media_type.startswith('image/'):
        with Image.open(path) as image:
            image.verify()
    return media_type


def image_metrics(mask_path: Path, objects: list[dict]) -> dict:
    labels = np.asarray(Image.open(mask_path))
    if labels.ndim != 2:
        raise ValueError('SAM2 mask.png is not a label image.')
    observed = {int(value): int(count) for value, count in zip(*np.unique(labels, return_counts=True), strict=True)
                if int(value) != 0}
    declared = {int(item['object_id']): int(item['area_px']) for item in objects}
    if observed != declared:
        raise ValueError('SAM2 decoded mask areas differ from manifest objects.')
    areas = list(declared.values())
    return {'object_count': len(areas), 'mask_area_pixels': areas,
            'mask_area_distribution': {
                'minimum': min(areas) if areas else 0,
                'median': statistics.median(areas) if areas else 0,
                'maximum': max(areas) if areas else 0,
                'total': sum(areas),
            }}


def run(args, runner=subprocess.run):
    source = args.source.resolve(); media_type = validate_source(source, args.mode)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True, mode=0o700)
    upload_dir, run_dir, analysis = output / 'upload', output / 'run', output / 'analysis'
    artifact, code = upload_source(source=source, model=args.model, media_type=media_type,
                                   directory=upload_dir, idempotency_key=args.idempotency_key + '-source',
                                   runner=runner)
    if code == 75:
        return {'state': 'upload_pending', 'output_dir': str(output)}, 75
    payload = {'mode': args.mode, 'media_base64': artifact, 'media_type': media_type}
    if args.mode == 'automatic-image':
        payload['max_masks'] = args.max_masks
    else:
        payload['points'] = [{'x': args.point_x, 'y': args.point_y, 'label': 1,
                              'object_id': args.object_id}]
        if args.mode == 'prompted-video':
            payload['prompt_frame'] = args.prompt_frame
    input_path = output / 'input.json'; immutable_input(input_path, payload)
    receipt, code = invoke(model=args.model, tool=args.tool, input_path=input_path,
                           directory=run_dir, idempotency_key=args.idempotency_key,
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {**receipt, 'output_dir': str(output)}, code
    archive = native_file(run_dir / 'result.json', 'application/zip')
    required = ('manifest.json', 'overlay.mp4') if args.mode == 'prompted-video' else (
        'manifest.json', 'mask.png', 'overlay.png')
    artifacts = extract_verified_zip(archive, analysis, required=required)
    manifest = json.loads((analysis / 'manifest.json').read_text())
    identity = file_identity(source)
    if (manifest.get('schema') != 'fs2.nebius.ai/sam2-result/v1'
            or manifest.get('mode') != args.mode or manifest.get('input_sha256') != identity['sha256']
            or not isinstance(manifest.get('objects'), list)):
        raise ValueError('SAM2 manifest does not match the submitted source and mode.')
    metrics = (image_metrics(analysis / 'mask.png', manifest['objects'])
               if args.mode != 'prompted-video'
               else {'object_count': len(manifest['objects']), 'tracked_frame_count': manifest.get('frame_count')})
    operation = operation_metadata(run_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/sam2-segmentation/v1', 'state': 'succeeded',
        'model': manifest.get('model'), 'revision': manifest.get('revision'),
        'license': 'Apache-2.0', 'operation_id': operation.get('id') or receipt.get('operation_id'),
        'mode': args.mode, 'input': {'path': str(source), **identity, 'media_type': media_type},
        'parameters': {key: payload[key] for key in payload if key not in ('media_base64',)},
        'metrics': metrics, 'objects': manifest['objects'], 'timing': timing(operation),
        'artifacts': artifacts,
        'limitations': ['Masks and tracking are model predictions, not semantic labels or accuracy validation.'],
    }
    save(analysis / 'summary.json', summary)
    overlay_path = analysis / ('overlay.mp4' if args.mode == 'prompted-video' else 'overlay.png')
    mask_path = None if args.mode == 'prompted-video' else analysis / 'mask.png'
    summary_path = analysis / 'summary.json'
    return {**summary, 'source_path': str(source), 'overlay_path': str(overlay_path),
            'mask_path': None if mask_path is None else str(mask_path),
            'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(source=source, overlay=overlay_path, mask=mask_path,
                                             summary=summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=('automatic-image', 'prompted-image', 'prompted-video'))
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--max-masks', type=int, default=32)
    parser.add_argument('--point-x', type=float)
    parser.add_argument('--point-y', type=float)
    parser.add_argument('--object-id', type=int, default=1)
    parser.add_argument('--prompt-frame', type=int, default=0)
    parser.add_argument('--operation-wait-seconds', '--wait-seconds', dest='wait_seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='sam2-1-hiera-large')
    parser.add_argument('--tool', default='segment_track_media_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not 1 <= args.max_masks <= 128
            or not 0 <= args.wait_seconds <= 3600 or args.object_id < 1 or args.prompt_frame < 0
            or (args.mode != 'automatic-image' and (args.point_x is None or args.point_y is None))):
        parser.error('Invalid SAM2 key, mask count, prompt coordinates, object, frame or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained upload/run/analysis receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
