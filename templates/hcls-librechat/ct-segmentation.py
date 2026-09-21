#!/usr/bin/env python3
"""Run one durable NV-Segment-CT file workflow without exposing bytes to chat.

The wrapper composes the existing verified upload, native invocation and imaging
analysis clients. Repeating the same command resumes their saved receipts; it
never implements a second inference path.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from scientific_receipts import load, save
from recording_pipeline import workspace_urls


ARTIFACT_FIELDS = ('artifact_id', 'sha256', 'size_bytes', 'media_type', 'compression')


def file_identity(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


def verified_artifact_reference(path, source):
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict) or any(field not in value for field in ARTIFACT_FIELDS):
        raise ValueError('Finalized artifact file is missing required fields.')
    reference = {field: value[field] for field in ARTIFACT_FIELDS}
    identity = file_identity(source)
    if reference['sha256'] != identity['sha256'] or reference['size_bytes'] != identity['size_bytes']:
        raise ValueError('Finalized artifact identity differs from the source NIfTI.')
    if reference['media_type'] not in ('application/gzip', 'application/x-nifti', 'application/octet-stream'):
        raise ValueError('Finalized artifact has an unsupported NIfTI media type.')
    if reference['compression'] != 'none':
        raise ValueError('Finalized artifact transport compression must be none.')
    return reference


def execute(command, runner=subprocess.run):
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 75):
        raise RuntimeError(f'Pipeline stage failed with exit code {completed.returncode}; inspect its saved receipt.')
    return completed


def run(args, runner=subprocess.run):
    source = args.source.resolve()
    if not source.is_file():
        raise ValueError('Source NIfTI does not exist.')
    output_dir = args.output_dir.resolve()
    upload_dir = output_dir / 'upload'
    run_dir = output_dir / 'run'
    analysis_dir = output_dir / 'analysis'
    input_path = output_dir / 'input.json'
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    python = Path(sys.executable)
    helper_dir = Path(__file__).resolve().parent
    upload = execute([
        str(python), str(helper_dir / 'upload-artifact.py'),
        '--model', args.model,
        '--file', str(source),
        '--media-type', args.media_type,
        '--output-dir', str(upload_dir),
        '--idempotency-key', args.idempotency_key + '-source',
    ], runner)
    if upload.returncode == 75:
        return {'state': 'upload_pending', 'output_dir': str(output_dir)}, 75

    artifact = verified_artifact_reference(upload_dir / 'artifact.json', source)
    payload = {'input_nifti_base64': artifact, 'label_prompt': args.label_prompt}
    existing = load(input_path)
    if existing is not None and existing != payload:
        raise ValueError('Saved CT input belongs to different source bytes or labels; use a new output directory.')
    save(input_path, payload)

    native_command = [
        str(python), str(helper_dir / 'invoke-native.py'),
        '--model', args.model,
        '--tool', args.tool,
        '--input', str(input_path),
        '--output-dir', str(run_dir),
        '--idempotency-key', args.idempotency_key,
        '--wait-seconds', str(args.wait_seconds),
    ]
    if args.recover_only:
        native_command.append('--recover-only')
    native = execute(native_command, runner)
    receipt = load(run_dir / 'receipt.json') or {}
    operation_id = receipt.get('operation_id')
    if native.returncode == 75:
        return {'state': receipt.get('state', 'pending'), 'operation_id': operation_id,
                'output_dir': str(output_dir)}, 75

    analysis = execute([
        str(python), str(helper_dir / 'imaging-analysis.py'),
        '--result', str(run_dir / 'result.json'),
        '--source', str(source),
        '--output-dir', str(analysis_dir),
    ], runner)
    if analysis.returncode:
        raise RuntimeError('CT analysis did not reach terminal success.')
    metrics = load(analysis_dir / 'metrics.json')
    overlay_path = analysis_dir / 'orthogonal-overlay.png'
    rotation_path = analysis_dir / 'surface-rotation.gif'
    segmentation_path = analysis_dir / 'segmentation.nii.gz'
    metrics_path = analysis_dir / 'metrics.json'
    report_path = analysis_dir / 'report.md'
    return {
        'state': 'succeeded',
        'operation_id': operation_id,
        'model': metrics.get('model') if isinstance(metrics, dict) else args.model,
        'input_grid': metrics.get('source', {}).get('shape') if isinstance(metrics, dict) else None,
        'prediction_grid': metrics.get('prediction', {}).get('shape') if isinstance(metrics, dict) else None,
        'label_voxel_counts': metrics.get('prediction', {}).get('label_voxel_counts') if isinstance(metrics, dict) else None,
        'model_seconds': metrics.get('prediction', {}).get('model_seconds') if isinstance(metrics, dict) else None,
        'analysis_dir': str(analysis_dir),
        'media': [str(overlay_path)] + ([str(rotation_path)] if rotation_path.is_file() else []),
        'workspace_urls': workspace_urls(
            overlay=overlay_path,
            rotation=rotation_path if rotation_path.is_file() else None,
            segmentation=segmentation_path,
            metrics=metrics_path,
            report=report_path,
        ),
    }, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--label-prompt', required=True, type=int, action='append')
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--model', default='nv-segment-ct')
    parser.add_argument('--tool', default='segment_ct_native')
    parser.add_argument('--media-type', default='application/gzip',
                        choices=('application/gzip', 'application/x-nifti', 'application/octet-stream'))
    parser.add_argument('--operation-wait-seconds', '--wait-seconds', dest='wait_seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 193 or args.wait_seconds < 0:
        parser.error('Use an 8–193 character idempotency key and a nonnegative wait.')
    try:
        value, exit_code = run(args)
        print(json.dumps(value, separators=(',', ':')))
        raise SystemExit(exit_code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect the upload, run and analysis receipts; do not resubmit elsewhere.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
