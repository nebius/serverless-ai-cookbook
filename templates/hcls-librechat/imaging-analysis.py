#!/usr/bin/env python3
"""Materialize and visualize a completed NV-Segment-CT result deterministically."""

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import nibabel as nib
from nibabel.processing import resample_from_to
import numpy as np
from PIL import Image
from skimage.measure import marching_cubes

from scientific_receipts import save_analysis, staged_output


def unwrap(value):
    """Accept the saved native value or its retained MCP/result envelopes."""
    for _ in range(4):
        if not isinstance(value, dict):
            break
        if isinstance(value.get('structuredContent'), dict):
            value = value['structuredContent']
        elif isinstance(value.get('result'), dict) and set(value) <= {'operation', 'result'}:
            value = value['result']
        else:
            break
    if not isinstance(value, dict):
        raise ValueError('Completed CT result must be a JSON object.')
    return value


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def decode_prediction(result):
    encoded = result.get('output_nifti_base64')
    if not isinstance(encoded, str) or not encoded:
        raise ValueError('Completed CT result has no output_nifti_base64 string.')
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('output_nifti_base64 is not strict base64.') from error
    if result.get('output_bytes') is not None and int(result['output_bytes']) != len(compressed):
        raise ValueError('Decoded CT output length differs from output_bytes.')
    if result.get('mime_type') not in (None, 'application/gzip') or not compressed.startswith(b'\x1f\x8b'):
        raise ValueError('CT output is not the advertised gzip NIfTI.')
    try:
        uncompressed = gzip.decompress(compressed)
        image = nib.Nifti1Image.from_bytes(uncompressed)
    except Exception as error:
        raise ValueError('CT output cannot be decoded as a gzip NIfTI.') from error
    return compressed, image


def label_counts(segmentation):
    labels, counts = np.unique(segmentation, return_counts=True)
    return {str(int(label)): int(count) for label, count in zip(labels, counts, strict=True)}


def source_on_prediction_grid(source_image, predicted_image):
    """Return source intensities on the prediction's physical grid.

    NV-Segment-CT may normalize its output grid independently from the input
    voxel matrix. Resampling via both NIfTI affines is safe; resizing arrays by
    shape alone is not. A resampled coverage mask also proves that the two
    physical grids overlap before an overlay is published.
    """
    for name, image in (('source', source_image), ('prediction', predicted_image)):
        if image.ndim != 3:
            raise ValueError(f'{name.capitalize()} CT image must be 3D, got {image.shape}.')
        if not np.isfinite(image.affine).all() or not np.isfinite(np.linalg.det(image.affine[:3, :3])):
            raise ValueError(f'{name.capitalize()} CT affine is invalid.')
        if abs(float(np.linalg.det(image.affine[:3, :3]))) < 1e-12:
            raise ValueError(f'{name.capitalize()} CT affine is singular.')

    target = (predicted_image.shape, predicted_image.affine)
    same_grid = source_image.shape == predicted_image.shape and np.allclose(
        source_image.affine, predicted_image.affine, rtol=1e-6, atol=1e-6)
    if same_grid:
        source = np.asarray(source_image.dataobj, dtype=np.float32)
        coverage = np.ones(predicted_image.shape, dtype=bool)
    else:
        source = np.asarray(
            resample_from_to(source_image, target, order=1, mode='constant', cval=np.nan).dataobj,
            dtype=np.float32,
        )
        source_grid = nib.Nifti1Image(np.ones(source_image.shape, dtype=np.uint8), source_image.affine)
        coverage = np.asarray(
            resample_from_to(source_grid, target, order=0, mode='constant', cval=0).dataobj,
            dtype=np.uint8,
        ).astype(bool)
    coverage_fraction = float(np.count_nonzero(coverage) / coverage.size)
    if coverage_fraction <= 0:
        raise ValueError('Source and prediction NIfTI grids do not overlap in physical space.')
    source[~coverage] = np.nan
    return source, {'resampled': not same_grid, 'coverage_fraction': coverage_fraction}


def publish_bytes(path, data):
    with staged_output(path) as staged:
        staged.path.write_bytes(data)
    return staged.receipt


def slice_positions(mask):
    foreground = np.argwhere(mask)
    if len(foreground):
        return tuple(int(value) for value in np.median(foreground, axis=0))
    return tuple(length // 2 for length in mask.shape)


def render_slices(source, segmentation, labels):
    finite = source[np.isfinite(source)]
    if not finite.size:
        raise ValueError('Source CT has no finite intensities.')
    low, high = np.percentile(finite, (1, 99))
    if not high > low:
        low, high = float(finite.min()), float(finite.max() + 1)
    center = slice_positions(segmentation != 0)
    planes = (
        ('Sagittal', 0, center[0]),
        ('Coronal', 1, center[1]),
        ('Axial', 2, center[2]),
    )
    figure, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), facecolor='#f4f7f3')
    colors = plt.get_cmap('turbo', max(2, len(labels)))
    for axis, (title, dimension, index) in zip(axes, planes, strict=True):
        image = np.rot90(np.take(source, index, axis=dimension))
        mask = np.rot90(np.take(segmentation, index, axis=dimension))
        axis.imshow(image, cmap='gray', vmin=low, vmax=high, interpolation='nearest')
        axis.imshow(np.ma.masked_where(mask == 0, mask), cmap=colors, alpha=0.58,
                    interpolation='nearest', vmin=0, vmax=max(labels or [1]))
        axis.set_title(f'{title} · index {index}', color='#19241d')
        axis.axis('off')
    figure.suptitle('NV-Segment-CT · source with returned mask overlay', color='#19241d')
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format='png', dpi=150, bbox_inches='tight', metadata={'Software': 'Nebius Scientific AI'})
    plt.close(figure)
    return buffer.getvalue(), {'sagittal': center[0], 'coronal': center[1], 'axial': center[2]}


def render_surface(segmentation):
    mask = segmentation != 0
    if not mask.any() or mask.all() or min(mask.shape) < 2:
        return None
    padded = np.pad(mask.astype(np.uint8), 1)
    vertices, faces, _, _ = marching_cubes(padded, level=0.5)
    vertices -= 1
    if len(vertices) > 250_000 or len(faces) > 500_000:
        return None
    frames = []
    for azimuth in range(0, 360, 20):
        figure = plt.figure(figsize=(4.8, 4.4), facecolor='#f4f7f3')
        axis = figure.add_subplot(111, projection='3d')
        surface = Poly3DCollection(vertices[faces], alpha=0.72, linewidths=0.04)
        surface.set_facecolor('#35c98b')
        surface.set_edgecolor('#126b4a')
        axis.add_collection3d(surface)
        axis.set_xlim(0, mask.shape[0]); axis.set_ylim(0, mask.shape[1]); axis.set_zlim(0, mask.shape[2])
        axis.set_box_aspect(mask.shape)
        axis.view_init(elev=22, azim=azimuth)
        axis.set_title('Returned segmentation surface', color='#19241d')
        axis.set_axis_off()
        figure.tight_layout()
        figure.canvas.draw()
        frame = Image.fromarray(np.asarray(figure.canvas.buffer_rgba())[:, :, :3].copy())
        frames.append(frame)
        plt.close(figure)
    output = io.BytesIO()
    frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:], duration=90, loop=0,
                   optimize=False, disposal=2)
    return output.getvalue()


def analyze(result_path, source_path, output_dir):
    result_bytes = result_path.read_bytes()
    result = unwrap(json.loads(result_bytes))
    compressed, predicted_image = decode_prediction(result)
    source_image = nib.load(source_path)
    predicted = np.asarray(predicted_image.dataobj)
    source, grid_alignment = source_on_prediction_grid(source_image, predicted_image)
    if predicted.ndim != 3:
        raise ValueError(f'Prediction CT image must be 3D, got {predicted.shape}.')
    if not np.isfinite(predicted).all() or not np.allclose(predicted, np.rint(predicted)):
        raise ValueError('Returned segmentation contains non-finite or non-integral labels.')
    segmentation = np.rint(predicted).astype(np.int32)
    counts = label_counts(segmentation)
    advertised_shape = result.get('shape')
    if advertised_shape is not None and list(predicted.shape) != advertised_shape:
        raise ValueError('Decoded CT output shape differs from the result metadata.')
    advertised_counts = result.get('labels')
    if advertised_counts is not None and {str(k): int(v) for k, v in advertised_counts.items()} != counts:
        raise ValueError('Decoded CT label counts differ from the result metadata.')

    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    mask_receipt = publish_bytes(output_dir / 'segmentation.nii.gz', compressed)
    overlay, positions = render_slices(source, segmentation, [int(key) for key in counts if key != '0'])
    overlay_receipt = publish_bytes(output_dir / 'orthogonal-overlay.png', overlay)
    surface = render_surface(segmentation)
    surface_receipt = publish_bytes(output_dir / 'surface-rotation.gif', surface) if surface is not None else None
    metrics = {
        'schema': 'nebius-scientific-ai/ct-segmentation-analysis/v1',
        'model': result.get('model'),
        'revision': result.get('revision'),
        'request_id': result.get('request_id'),
        'source': {'path': str(source_path), 'sha256': sha256(source_path.read_bytes()),
                   'shape': list(source_image.shape), 'affine': source_image.affine.tolist(),
                   'render_grid': {'shape': list(predicted_image.shape),
                                   'affine': predicted_image.affine.tolist(), **grid_alignment}},
        'prediction': {'path': str(output_dir / 'segmentation.nii.gz'), 'sha256': sha256(compressed),
                       'compressed_size_bytes': len(compressed), 'shape': list(segmentation.shape),
                       'affine': predicted_image.affine.tolist(), 'label_voxel_counts': counts,
                       'foreground_voxels': int(np.count_nonzero(segmentation)),
                       'model_seconds': result.get('model_seconds')},
        'visualization': {'slice_indices': positions, 'overlay': overlay_receipt,
                          'surface_rotation': surface_receipt,
                          'surface_supported': surface_receipt is not None},
        'provenance': {'result_path': str(result_path), 'result_sha256': sha256(result_bytes),
                       'decoded_counts_match_result': True, 'decoded_shape_matches_result': True},
        'limitations': ['Research use only; not diagnosis or clinical validation.',
                        'Voxel counts and visual overlays do not establish segmentation accuracy.'],
    }
    save_analysis(output_dir / 'metrics.json', metrics)
    report = [
        '# NV-Segment-CT analysis', '',
        f"- Gateway request: `{metrics['request_id'] or 'unavailable'}`",
        f"- Source grid: `{list(source_image.shape)}`",
        f"- Prediction grid: `{list(segmentation.shape)}`",
        f"- Source resampled to prediction grid with NIfTI affines: `{grid_alignment['resampled']}`",
        f"- Prediction-grid source coverage: `{grid_alignment['coverage_fraction']:.6f}`",
        f"- Label voxel counts: `{counts}`",
        f"- Foreground voxels: `{metrics['prediction']['foreground_voxels']}`",
        f"- Model execution time: `{result.get('model_seconds')}` seconds",
        f"- Orthogonal overlay: `{output_dir / 'orthogonal-overlay.png'}`",
        f"- Rotating surface: `{output_dir / 'surface-rotation.gif'}`" if surface_receipt else '- Rotating surface: unavailable for this returned mask',
        '', 'Research use only. This is neither a diagnosis nor clinical validation.',
    ]
    publish_bytes(output_dir / 'report.md', ('\n'.join(report) + '\n').encode())
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    metrics = analyze(args.result, args.source, args.output_dir)
    print(json.dumps({'status': 'succeeded', 'request_id': metrics['request_id'],
                      'label_voxel_counts': metrics['prediction']['label_voxel_counts'],
                      'output_dir': str(args.output_dir),
                      'media': [str(args.output_dir / 'orthogonal-overlay.png')]
                               + ([str(args.output_dir / 'surface-rotation.gif')]
                                  if metrics['visualization']['surface_supported'] else [])}))


if __name__ == '__main__':
    main()
