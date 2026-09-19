import json
from pathlib import Path
import sys

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from scientific_preparation import export_parquet


def test_chunked_numeric_fixed_vectors_all_four_closed_exports(tmp_path):
    fields = {'state': pa.array([[float(i), float(i + 1)] for i in range(128)], type=pa.list_(pa.float32(), 2)),
              'action': pa.array([[i] * 45 for i in range(128)], type=pa.list_(pa.int32(), 45)),
              'valid': pa.array([bool(i % 2) for i in range(128)])}
    table = pa.table(fields)
    source = tmp_path / 'source.parquet'
    pq.write_table(pa.concat_tables([table.slice(0, 64), table.slice(64)]), source, row_group_size=32)
    measured = export_parquet(source, tmp_path / 'out', ['npz', 'hdf5', 'zip', 'sqlite'])
    assert measured['row_count'] == 128 and measured['scalar_values'] == 6144
    assert all(item['all_fields_exact'] and item['size_bytes'] > 0 for item in measured['exports'])
    assert '6144 total scalar values' in (tmp_path / 'out/report.md').read_text()
    assert json.loads((tmp_path / 'out/comparison.json').read_bytes()) == measured
    with np.load(tmp_path / 'out/data.npz', allow_pickle=False) as arrays:
        assert arrays['state'].dtype == np.float32 and not arrays['valid'][0]


@pytest.mark.parametrize('values,kind', [([None, 1.0], pa.float32()), ([[1], [2, 3]], pa.list_(pa.int32())), ([float('nan')], pa.float64())])
def test_unsupported_or_undefined_numeric_policy_fails_before_publication(tmp_path, values, kind):
    source = tmp_path / 'bad.parquet'
    pq.write_table(pa.table({'x': pa.array(values, type=kind)}), source)
    with pytest.raises(ValueError):
        export_parquet(source, tmp_path / 'out', ['npz', 'sqlite'])
    assert not (tmp_path / 'out/comparison.json').exists()
