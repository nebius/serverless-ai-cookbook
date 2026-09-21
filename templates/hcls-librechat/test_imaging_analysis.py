import base64
import gzip
import importlib.util
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('imaging_analysis', Path(__file__).with_name('imaging-analysis.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def fixture(tmp_path):
    source_data = np.zeros((12, 14, 16), dtype=np.float32)
    source_data[3:9, 4:11, 5:13] = 100
    segmentation = np.zeros_like(source_data, dtype=np.uint8)
    segmentation[5:8, 6:10, 7:12] = 1
    affine = np.diag([1.5, 1.2, 2.0, 1.0])
    source = tmp_path / 'source.nii.gz'
    nib.save(nib.Nifti1Image(source_data, affine), source)
    raw = nib.Nifti1Image(segmentation, affine).to_bytes()
    compressed = gzip.compress(raw, mtime=0)
    result = tmp_path / 'result.json'
    result.write_text(json.dumps({
        'model': 'nv-segment-ct', 'revision': 'fixture-revision', 'request_id': 'fixture-operation',
        'mime_type': 'application/gzip', 'output_bytes': len(compressed),
        'output_nifti_base64': base64.b64encode(compressed).decode(),
        'shape': list(segmentation.shape), 'labels': {'0': int((segmentation == 0).sum()), '1': int(segmentation.sum())},
        'model_seconds': 0.25,
    }))
    return source, result, compressed


def test_completed_result_materializes_verified_mask_overlay_and_rotation(tmp_path):
    source, result, compressed = fixture(tmp_path)
    output = tmp_path / 'analysis'
    metrics = analysis.analyze(result, source, output)
    assert (output / 'segmentation.nii.gz').read_bytes() == compressed
    assert (output / 'orthogonal-overlay.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert (output / 'surface-rotation.gif').read_bytes().startswith(b'GIF89a')
    assert metrics['prediction']['label_voxel_counts'] == {'0': 2628, '1': 60}
    assert metrics['visualization']['surface_supported'] is True
    assert json.loads((output / 'metrics.json').read_text())['provenance']['decoded_counts_match_result'] is True


def test_affine_aware_resampling_aligns_different_source_and_prediction_grids(tmp_path):
    source, result, _ = fixture(tmp_path)
    source_image = nib.load(source)
    source_data = np.asarray(source_image.dataobj)
    coarse_source = tmp_path / 'coarse-source.nii.gz'
    nib.save(nib.Nifti1Image(source_data[::2, ::2, ::2], source_image.affine @ np.diag([2, 2, 2, 1])), coarse_source)
    output = tmp_path / 'analysis-resampled'
    metrics = analysis.analyze(result, coarse_source, output)
    assert metrics['source']['shape'] == [6, 7, 8]
    assert metrics['source']['render_grid']['shape'] == [12, 14, 16]
    assert metrics['source']['render_grid']['resampled'] is True
    assert metrics['source']['render_grid']['coverage_fraction'] > 0.75
    assert (output / 'orthogonal-overlay.png').exists()


def test_non_overlapping_physical_grids_fail_before_publishing(tmp_path):
    source, result, _ = fixture(tmp_path)
    source_image = nib.load(source)
    moved_source = tmp_path / 'moved-source.nii.gz'
    moved_affine = source_image.affine.copy()
    moved_affine[:3, 3] = 10000
    nib.save(nib.Nifti1Image(np.asarray(source_image.dataobj), moved_affine), moved_source)
    output = tmp_path / 'analysis-no-overlap'
    with pytest.raises(ValueError, match='do not overlap'):
        analysis.analyze(result, moved_source, output)
    assert not output.exists()


@pytest.mark.parametrize('mutation,match', [
    (lambda value: value.update(output_bytes=1), 'length'),
    (lambda value: value.update(output_nifti_base64='not base64'), 'strict base64'),
    (lambda value: value.update(labels={'0': 1}), 'label counts'),
    (lambda value: value.update(shape=[1, 2, 3]), 'shape'),
])
def test_corrupt_or_mismatched_result_fails_before_publishing(tmp_path, mutation, match):
    source, result, _ = fixture(tmp_path)
    value = json.loads(result.read_text())
    mutation(value)
    result.write_text(json.dumps(value))
    output = tmp_path / 'analysis'
    with pytest.raises(ValueError, match=match):
        analysis.analyze(result, source, output)
    assert not (output / 'metrics.json').exists()


def test_empty_mask_still_has_overlay_but_no_invented_surface(tmp_path):
    source, result, _ = fixture(tmp_path)
    source_image = nib.load(source)
    empty = np.zeros(source_image.shape, dtype=np.uint8)
    compressed = gzip.compress(nib.Nifti1Image(empty, source_image.affine).to_bytes(), mtime=0)
    value = json.loads(result.read_text())
    value.update(output_bytes=len(compressed), output_nifti_base64=base64.b64encode(compressed).decode(),
                 labels={'0': int(empty.size)})
    result.write_text(json.dumps(value))
    output = tmp_path / 'analysis'
    metrics = analysis.analyze(result, source, output)
    assert metrics['visualization']['surface_supported'] is False
    assert not (output / 'surface-rotation.gif').exists()
