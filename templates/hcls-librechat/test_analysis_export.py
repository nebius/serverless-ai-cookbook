"""Scientific measurements export completely or leave prior evidence intact."""
import json

import numpy as np
import pytest

from scientific_receipts import save_analysis


def test_numpy_measurements_and_arrays_are_complete(tmp_path):
    target = tmp_path / 'measurements.json'
    save_analysis(target, {'mean': np.float32(1.25), 'count': np.int64(128),
                          'exact': np.bool_(True), 'rgb': np.asarray([1, 2, 3]),
                          'nested': [{'ratio': np.float64(0.5)}]})
    assert json.loads(target.read_text()) == {
        'mean': 1.25, 'count': 128, 'exact': True, 'rgb': [1, 2, 3],
        'nested': [{'ratio': 0.5}]}


@pytest.mark.parametrize('value', [np.float32('nan'), float('inf'), np.asarray([1, float('-inf')]), object()])
def test_serialization_failure_preserves_existing_file(tmp_path, value):
    target = tmp_path / 'measurements.json'
    original = b'{"retained": true}\n'
    target.write_bytes(original)
    with pytest.raises((TypeError, ValueError)):
        save_analysis(target, {'early_valid_value': 42, 'invalid': value})
    assert target.read_bytes() == original


def test_no_partial_file_created_for_invalid_measurement(tmp_path):
    target = tmp_path / 'measurements.json'
    with pytest.raises(ValueError):
        save_analysis(target, {'mean': np.float32('nan')})
    assert not target.exists()


def test_no_rounding_or_integer_string_substitution(tmp_path):
    target = tmp_path / 'measurements.json'
    value = np.float32(15.787162)
    save_analysis(target, {'actual': value, 'count': np.uint64(2**63 + 1)})
    actual = json.loads(target.read_text())
    assert actual['actual'] == float(value)
    assert actual['count'] == 2**63 + 1
