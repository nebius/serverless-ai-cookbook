"""Deterministic, seekable scientific preparation; never submits inference.

Writers operate on a local directory. The study runner publishes closed files
through scientific_receipts only after independently reopening every export.
This is not a live SQLite/WAL or shared POSIX filesystem abstraction.
"""
import csv
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

from scientific_receipts import file_measurement


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def parquet_arrays(source):
    """Preserve primitive and fixed-size-list numeric columns without pandas.

    Unsupported/null/variable-length columns fail explicitly instead of silently
    dropping fields or inventing a missing-value/numeric conversion policy.
    """
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pq.read_table(source).combine_chunks()
    if len(set(table.column_names)) != len(table.column_names):
        raise ValueError('Duplicate Parquet field names cannot identify a lossless export.')
    arrays, fields = {}, []
    for field in table.schema:
        if field.name in {'file', 'allow_pickle'} or '/' in field.name or '\\' in field.name or not field.name:
            raise ValueError(f'Field name {field.name!r} requires an explicit portable rename mapping before NPZ/HDF5 export.')
        column = table[field.name]
        if column.null_count:
            raise ValueError(f'Column {field.name} contains nulls; choose an explicit missing-value policy before export.')
        scalar_type, shape = field.type, []
        while pa.types.is_fixed_size_list(scalar_type):
            shape.append(scalar_type.list_size)
            scalar_type = scalar_type.value_type
        if not (pa.types.is_integer(scalar_type) or pa.types.is_floating(scalar_type)
                or pa.types.is_boolean(scalar_type)):
            raise ValueError(f'Column {field.name} has unsupported type {field.type}; this lossless numeric exporter accepts primitives and fixed-size lists only.')
        dtype = np.dtype(scalar_type.to_pandas_dtype())
        if dtype.kind == 'u' and dtype.itemsize == 8:
            raise ValueError(f'Column {field.name} is uint64; SQLite signed integer export cannot represent its full domain.')
        values = np.asarray(column.to_pylist(), dtype=dtype)
        if values.shape != (table.num_rows, *shape):
            raise ValueError(f'Column {field.name} has inconsistent/null nested values.')
        if values.dtype.kind == 'f' and not np.isfinite(values).all():
            raise ValueError(f'Column {field.name} contains nonfinite values; an explicit preservation policy is required.')
        arrays[field.name] = values
        fields.append({'name': field.name, 'arrow_type': str(field.type), 'dtype': values.dtype.str,
                       'shape': list(values.shape), 'scalar_values': int(values.size),
                       'bytes_sha256': hashlib.sha256(values.tobytes()).hexdigest()})
    return arrays, {'row_count': table.num_rows, 'field_count': len(fields), 'fields': fields,
                    'scalar_values': sum(item['scalar_values'] for item in fields)}


def flatten(arrays):
    """Stable exported column identities; original names/shapes stay in metadata."""
    import numpy as np
    columns, rows = [], []
    flattened = []
    for name, array in arrays.items():
        values = array.reshape(array.shape[0], -1)
        for index in range(values.shape[1]):
            columns.append({'column': f'c{len(columns)}', 'field': name, 'element': index,
                            'dtype': array.dtype.str})
            flattened.append(values[:, index])
    for index in range(next(iter(arrays.values())).shape[0]):
        rows.append([value[index].item() if isinstance(value[index], np.generic) else value[index]
                     for value in flattened])
    return columns, rows


def restore_rows(rows, columns, arrays):
    import numpy as np
    output = {}
    for name, expected in arrays.items():
        indexes = [i for i, column in enumerate(columns) if column['field'] == name]
        values = []
        for row in rows:
            parsed = []
            for index in indexes:
                value = row[index]
                if expected.dtype.kind == 'b':
                    if str(value) not in {'0', '1', 'False', 'True'}:
                        raise ValueError('Boolean export must use an explicit true/false or 0/1 value.')
                    value = str(value) in {'1', 'True'}
                elif expected.dtype.kind in 'iu':
                    value = int(value)
                else:
                    value = float(value)
                parsed.append(value)
            values.append(parsed)
        output[name] = np.asarray(values, dtype=expected.dtype).reshape(expected.shape)
    return output


def verify_arrays(actual, expected):
    if actual.keys() != expected.keys():
        raise ValueError('Export field names differ from the source.')
    for name, reference in expected.items():
        observed = actual[name]
        if observed.shape != reference.shape or observed.dtype != reference.dtype or observed.tobytes() != reference.tobytes():
            raise ValueError(f'Export round-trip differs for field {name}; no verified publication.')


def export_parquet(source, output, formats):
    import h5py
    import numpy as np

    source, output = Path(source), Path(output)
    allowed = {'npz', 'hdf5', 'zip', 'sqlite'}
    if not formats or len(formats) != len(set(formats)) or set(formats) - allowed:
        raise ValueError('formats must be a nonempty unique selection of npz, hdf5, zip, sqlite.')
    before = file_measurement(source)
    arrays, metadata = parquet_arrays(source)
    if not arrays or not metadata['row_count']:
        raise ValueError('Export requires at least one numeric field and one row.')
    columns, rows = flatten(arrays)
    metadata.update(schema='scientific-recorded-export/v1', source_size_bytes=before[0],
                    source_sha256=before[1], flat_columns=columns,
                    limitations=['Preserves numeric data and row order; does not establish scientific or physical validity.',
                                 'Standalone closed SQLite export only; no live database/WAL support.'])
    output.mkdir(parents=True, exist_ok=True)
    exports = []
    for kind in formats:
        path = output / ('data.' + {'hdf5': 'h5'}.get(kind, kind))
        if kind == 'npz':
            np.savez_compressed(path, **arrays)
            with np.load(path, allow_pickle=False) as saved:
                verify_arrays({name: saved[name] for name in saved.files}, arrays)
        elif kind == 'hdf5':
            with h5py.File(path, 'w') as saved:
                for name, values in arrays.items():
                    saved.create_dataset(name, data=values, track_times=False)
            with h5py.File(path, 'r') as saved:
                verify_arrays({name: saved[name][:] for name in arrays}, arrays)
        elif kind == 'zip':
            text = io.StringIO(newline='')
            writer = csv.writer(text, lineterminator='\n')
            writer.writerow([column['column'] for column in columns])
            writer.writerows(rows)
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as saved:
                for name, data in [('rows.csv', text.getvalue().encode()), ('metadata.json', canonical(metadata))]:
                    member = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                    member.compress_type = zipfile.ZIP_DEFLATED
                    saved.writestr(member, data)
            with zipfile.ZipFile(path) as saved:
                recovered = list(csv.reader(io.StringIO(saved.read('rows.csv').decode())))
                if recovered[0] != [column['column'] for column in columns]:
                    raise ValueError('CSV columns changed during export.')
                verify_arrays(restore_rows(recovered[1:], columns, arrays), arrays)
        else:
            types = ['REAL' if np.dtype(column['dtype']).kind == 'f' else 'INTEGER' for column in columns]
            with closing(sqlite3.connect(path)) as database:
                definition = ', '.join(f'"{column["column"]}" {kind}' for column, kind in zip(columns, types, strict=True))
                database.execute(f'CREATE TABLE recorded ({definition})')
                database.executemany('INSERT INTO recorded VALUES (' + ','.join('?' for _ in columns) + ')', rows)
                database.execute('CREATE TABLE metadata (document TEXT NOT NULL)')
                database.execute('INSERT INTO metadata VALUES (?)', (canonical(metadata).decode(),))
                database.commit()
            with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as database:
                if database.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite integrity check failed.')
                verify_arrays(restore_rows(database.execute('SELECT * FROM recorded ORDER BY rowid').fetchall(), columns, arrays), arrays)
        size, checksum = file_measurement(path)
        exports.append({'file': path.name, 'size_bytes': size, 'sha256': checksum, 'all_fields_exact': True})
    if file_measurement(source) != before:
        raise ValueError('Source changed during export; no verified publication.')
    metadata['exports'] = exports
    (output / 'comparison.json').write_bytes(canonical(metadata) + b'\n')
    (output / 'report.md').write_text(
        '# Recorded-data export\n\n'
        f'{metadata["row_count"]} rows; {metadata["field_count"]} fields; {metadata["scalar_values"]} total scalar values. '
        'Every selected format was reopened and verified against the source field names, shapes, dtypes and values.\n\n'
        '| File | Bytes | SHA256 |\n|---|---:|---|\n' + ''.join(
            f'| {item["file"]} | {item["size_bytes"]} | `{item["sha256"]}` |\n' for item in exports)
        + '\n' + '\n'.join('- ' + item for item in metadata['limitations']) + '\n')
    return metadata
