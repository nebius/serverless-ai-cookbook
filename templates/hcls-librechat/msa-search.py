#!/usr/bin/env python3
"""Run and materialize one PDB70 MSA search without ad-hoc chat scripts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

from scientific_receipts import load, save, staged_output
from recording_pipeline import workspace_urls


AA = 'ACDEFGHIKLMNPQRSTVWY-'
AA_INDEX = {letter: index for index, letter in enumerate(AA)}
AA_COLORS = ['#8dd3c7', '#ffffb3', '#bebada', '#fb8072', '#80b1d3', '#fdb462', '#b3de69',
             '#fccde5', '#d9d9d9', '#bc80bd', '#ccebc5', '#ffed6f', '#66c2a5', '#fc8d62',
             '#8da0cb', '#e78ac3', '#a6d854', '#ffd92f', '#e5c494', '#b3b3b3', '#ffffff']
SEQUENCE_RE = re.compile(r'^[ACDEFGHIKLMNPQRSTVWY]+$')


def read_single_fasta(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise ValueError('MSA query FASTA does not exist.')
    records, header, sequence = [], None, []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('>'):
            if header is not None:
                records.append((header, ''.join(sequence)))
            header, sequence = line[1:] or 'query', []
        elif header is None:
            raise ValueError('FASTA sequence appears before its header.')
        else:
            sequence.append(''.join(line.split()).upper())
    if header is not None:
        records.append((header, ''.join(sequence)))
    if len(records) != 1 or not 6 <= len(records[0][1]) <= 4096 or not SEQUENCE_RE.fullmatch(records[0][1]):
        raise ValueError('MSA input must contain exactly one 6–4096 residue canonical protein record.')
    return records[0]


def execute(command, runner=subprocess.run):
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 75):
        raise RuntimeError(f'Pipeline stage failed with exit code {completed.returncode}; inspect its receipt.')
    return completed


def unwrap(value):
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
        raise ValueError('MSA result must be an object.')
    return value


def parse_a3m(text: str) -> list[dict]:
    records, header, sequence = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('>'):
            if header is not None:
                records.append({'header': header, 'raw_sequence': ''.join(sequence)})
            header, sequence = line[1:] or 'unnamed', []
        elif header is None:
            raise ValueError('A3M sequence appears before its header.')
        else:
            sequence.append(line)
    if header is not None:
        records.append({'header': header, 'raw_sequence': ''.join(sequence)})
    if not records:
        raise ValueError('Returned A3M is empty.')
    for record in records:
        aligned = ''.join(character for character in record['raw_sequence'] if not character.islower()).upper()
        if not aligned or any(character not in AA_INDEX for character in aligned):
            raise ValueError('Returned A3M contains an invalid aligned residue.')
        record['aligned_sequence'] = aligned
    length = len(records[0]['aligned_sequence'])
    if any(len(record['aligned_sequence']) != length for record in records):
        raise ValueError('Returned A3M sequences do not share one aligned query grid.')
    return records


def extract_alignment(value: dict) -> tuple[str, str, dict]:
    result = unwrap(value)
    alignments = result.get('alignments')
    if not isinstance(alignments, dict) or len(alignments) != 1:
        raise ValueError('MSA result must contain exactly one declared database.')
    database, formats = next(iter(alignments.items()))
    if not isinstance(formats, dict) or not isinstance(formats.get('a3m'), dict):
        raise ValueError('MSA result has no A3M object.')
    a3m = formats['a3m']
    if a3m.get('format') != 'a3m' or not isinstance(a3m.get('alignment'), str):
        raise ValueError('MSA result does not advertise a valid A3M alignment.')
    return database, a3m['alignment'], result.get('metrics') if isinstance(result.get('metrics'), dict) else {}


def alignment_metrics(records: list[dict]) -> dict:
    matrix = np.array([list(record['aligned_sequence']) for record in records])
    coverage = np.mean(matrix != '-', axis=1)
    conservation = []
    entropy = []
    for column in matrix.T:
        residues = [item for item in column if item != '-']
        if not residues:
            conservation.append(0.0); entropy.append(0.0); continue
        counts = Counter(residues)
        frequencies = np.array(list(counts.values()), dtype=float) / len(residues)
        conservation.append(float(max(frequencies)))
        entropy.append(float(-np.sum(frequencies * np.log2(frequencies))))
    return {'matrix': matrix, 'coverage': coverage,
            'conservation': np.asarray(conservation), 'entropy': np.asarray(entropy)}


def render_summary(records: list[dict], database: str) -> bytes:
    values = alignment_metrics(records)
    matrix, coverage, conservation = values['matrix'], values['coverage'], values['conservation']
    display = matrix[:min(50, len(matrix))]
    encoded = np.vectorize(AA_INDEX.__getitem__)(display)
    figure = plt.figure(figsize=(15, 9), facecolor='#f4f7f3')
    grid = figure.add_gridspec(3, 1, height_ratios=[2.2, 0.8, 0.9], hspace=0.42)
    alignment_axis = figure.add_subplot(grid[0])
    alignment_axis.imshow(encoded, aspect='auto', interpolation='nearest',
                          cmap=ListedColormap(AA_COLORS), vmin=0, vmax=len(AA) - 1)
    alignment_axis.set_title(f'Colored A3M alignment · first {len(display)} of {len(records)} sequences')
    alignment_axis.set_ylabel('sequence'); alignment_axis.set_xlabel('query position')
    conservation_axis = figure.add_subplot(grid[1])
    conservation_axis.fill_between(np.arange(1, len(conservation) + 1), conservation,
                                   color='#35c98b', alpha=0.85)
    conservation_axis.set_ylim(0, 1.02); conservation_axis.set_ylabel('top residue frequency')
    conservation_axis.set_xlabel('query position'); conservation_axis.set_title('Per-column conservation')
    coverage_axis = figure.add_subplot(grid[2])
    coverage_axis.hist(coverage, bins=np.linspace(0, 1, 21), color='#4d79c7', edgecolor='white')
    coverage_axis.set_xlabel('aligned non-gap coverage'); coverage_axis.set_ylabel('sequences')
    coverage_axis.set_title('Sequence coverage distribution')
    figure.suptitle(f'MSA Search · {database}', fontsize=18, color='#19241d')
    buffer = io.BytesIO()
    figure.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                   metadata={'Software': 'Nebius Scientific AI'})
    plt.close(figure)
    return buffer.getvalue()


def publish_bytes(path: Path, data: bytes):
    with staged_output(path) as staged:
        staged.path.write_bytes(data)
    return staged.receipt


def operation_metadata(path: Path) -> dict:
    value = load(path) or {}
    if isinstance(value, dict) and isinstance(value.get('structuredContent'), dict):
        value = value['structuredContent']
    return value if isinstance(value, dict) else {}


def elapsed_seconds(operation: dict):
    start, end = operation.get('accepted_at'), operation.get('completed_at')
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    return (datetime.fromisoformat(end.replace('Z', '+00:00'))
            - datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds()


def materialize(result_path: Path, operation_path: Path, query_path: Path,
                output_dir: Path, model: str) -> dict:
    raw = result_path.read_bytes(); database, a3m, runtime_metrics = extract_alignment(json.loads(raw))
    records = parse_a3m(a3m); values = alignment_metrics(records)
    query_header, query_sequence = read_single_fasta(query_path)
    if records[0]['aligned_sequence'].replace('-', '') != query_sequence:
        raise ValueError('Returned A3M query differs from the submitted FASTA sequence.')
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    alignment_receipt = publish_bytes(output_dir / 'alignment.a3m', a3m.encode())
    image_receipt = publish_bytes(output_dir / 'msa-summary.png', render_summary(records, database))
    operation = operation_metadata(operation_path)
    summary = {
        'schema': 'nebius-scientific-ai/msa-search/v1', 'state': 'succeeded',
        'model': model, 'operation_id': operation.get('id'), 'database': database,
        'format': 'a3m', 'query': {'header': query_header, 'length': len(query_sequence),
                                   'path': str(query_path),
                                   'sha256': hashlib.sha256(query_path.read_bytes()).hexdigest()},
        'alignment': {'sequence_count': len(records), 'aligned_columns': len(records[0]['aligned_sequence']),
                      'mean_coverage': float(np.mean(values['coverage'])),
                      'median_coverage': float(np.median(values['coverage'])),
                      'mean_top_residue_frequency': float(np.mean(values['conservation']))},
        'timing': {'accepted_at': operation.get('accepted_at'), 'completed_at': operation.get('completed_at'),
                   'elapsed_seconds': elapsed_seconds(operation),
                   'analysis_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')},
        'runtime_metrics': runtime_metrics,
        'artifacts': {'alignment': alignment_receipt, 'summary_image': image_receipt},
        'provenance': {'result_path': str(result_path), 'result_sha256': hashlib.sha256(raw).hexdigest()},
        'limitations': ['PDB70 homology search is not functional or evolutionary validation.',
                        'Conservation and coverage are descriptive values from the returned alignment.'],
    }
    save(output_dir / 'summary.json', summary)
    return summary


def run(args, runner=subprocess.run):
    _, sequence = read_single_fasta(args.query.resolve())
    output_dir = args.output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir, analysis_dir, input_path = output_dir / 'run', output_dir / 'analysis', output_dir / 'input.json'
    payload = {'sequence': sequence, 'databases': [args.database],
               'max_msa_sequences': args.max_sequences, 'output_alignment_formats': ['a3m']}
    existing = load(input_path)
    if existing is not None and existing != payload:
        raise ValueError('Saved MSA input differs; use a new output directory.')
    save(input_path, payload)
    python, helper_dir = Path(sys.executable), Path(__file__).resolve().parent
    command = [str(python), str(helper_dir / 'invoke-native.py'), '--model', args.model,
               '--tool', args.tool, '--input', str(input_path), '--output-dir', str(run_dir),
               '--idempotency-key', args.idempotency_key, '--wait-seconds', str(args.wait_seconds)]
    if args.recover_only:
        command.append('--recover-only')
    native = execute(command, runner)
    receipt = load(run_dir / 'receipt.json') or {}; operation_id = receipt.get('operation_id')
    if native.returncode == 75:
        return {'state': receipt.get('state', 'pending'), 'operation_id': operation_id,
                'output_dir': str(output_dir)}, 75
    summary = materialize(run_dir / 'result.json', run_dir / 'operation.json', args.query.resolve(),
                          analysis_dir, args.model)
    summary_image = analysis_dir / 'msa-summary.png'
    alignment_path = analysis_dir / 'alignment.a3m'
    summary_path = analysis_dir / 'summary.json'
    return {'state': 'succeeded', 'operation_id': operation_id, 'model': args.model,
            'database': summary['database'], 'query': summary['query'],
            'alignment': summary['alignment'], 'timing': summary['timing'],
            'coverage_definition': 'fraction of aligned non-gap query-grid columns per returned sequence',
            'summary_image': str(summary_image),
            'alignment_path': str(alignment_path),
            'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(
                query=args.query.resolve(), summary_image=summary_image,
                alignment=alignment_path, summary=summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--max-sequences', type=int, default=500)
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--database', default='pdb70_220313', choices=('pdb70_220313',))
    parser.add_argument('--model', default='msa-search-pdb70')
    parser.add_argument('--tool', default='msa_search_native')
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 193 or not 1 <= args.max_sequences <= 5000 or args.wait_seconds < 0:
        parser.error('Invalid MSA idempotency key, maximum sequence count or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect saved run/analysis receipts; do not resubmit elsewhere.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
