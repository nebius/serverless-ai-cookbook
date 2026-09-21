#!/usr/bin/env python3
"""Run and materialize one ProteinMPNN design without ad-hoc chat scripts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
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
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D
import numpy as np

from scientific_receipts import load, save, staged_output


ARTIFACT_FIELDS = ('artifact_id', 'sha256', 'size_bytes', 'media_type', 'compression')
AMINO_ACIDS = 'ACDEFGHIKLMNPQRSTVWY'
SEQUENCE_RE = re.compile(r'^[ACDEFGHIKLMNPQRSTVWYX]+$')
HEADER_VALUE_RE = re.compile(r'([A-Za-z_]+)=([^ ]+)')
COLORS = {
    **{letter: '#2f9e6f' for letter in 'AILMFWVY'},
    **{letter: '#3478c6' for letter in 'KRH'},
    **{letter: '#d44a55' for letter in 'DE'},
    **{letter: '#b47b22' for letter in 'STNQ'},
    **{letter: '#7b61a8' for letter in 'CGP'},
    'X': '#7c8580',
}


def file_identity(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


def verified_pdb(path: Path) -> None:
    if not path.is_file():
        raise ValueError('ProteinMPNN backbone does not exist.')
    raw = path.read_bytes()
    if not 40 <= len(raw) <= 2_000_000 or b'ATOM' not in raw:
        raise ValueError('ProteinMPNN backbone must be a 40–2,000,000 byte PDB with ATOM records.')
    raw.decode('utf-8')


def verified_artifact_reference(path: Path, source: Path) -> dict:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict) or any(field not in value for field in ARTIFACT_FIELDS):
        raise ValueError('Finalized ProteinMPNN artifact is missing required fields.')
    reference = {field: value[field] for field in ARTIFACT_FIELDS}
    identity = file_identity(source)
    if reference['sha256'] != identity['sha256'] or reference['size_bytes'] != identity['size_bytes']:
        raise ValueError('Finalized ProteinMPNN artifact differs from the backbone bytes.')
    if reference['media_type'] not in ('chemical/x-pdb', 'text/plain') or reference['compression'] != 'none':
        raise ValueError('Finalized ProteinMPNN artifact has the wrong media contract.')
    return reference


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
        raise ValueError('ProteinMPNN result must be an object.')
    return value


def parse_fasta(text: str) -> list[dict]:
    records = []
    header = None
    sequence = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('>'):
            if header is not None:
                records.append({'header': header, 'sequence': ''.join(sequence)})
            header, sequence = line[1:], []
        elif header is None:
            raise ValueError('ProteinMPNN mfasta has sequence data before a header.')
        else:
            sequence.append(line.upper())
    if header is not None:
        records.append({'header': header, 'sequence': ''.join(sequence)})
    if len(records) < 2:
        raise ValueError('ProteinMPNN mfasta must contain the input and at least one design.')
    length = len(records[0]['sequence'])
    for record in records:
        if len(record['sequence']) != length or not SEQUENCE_RE.fullmatch(record['sequence']):
            raise ValueError('ProteinMPNN mfasta contains invalid or unequal-length sequences.')
        record['metadata'] = dict(HEADER_VALUE_RE.findall(record['header']))
    return records


def validate_result(value: dict) -> dict:
    result = unwrap(value)
    if not isinstance(result.get('mfasta'), str):
        raise ValueError('ProteinMPNN result has no mfasta string.')
    records = parse_fasta(result['mfasta'])
    designs = records[1:]
    scores = result.get('scores')
    probabilities = result.get('probs')
    if not isinstance(scores, list) or len(scores) != len(designs):
        raise ValueError('ProteinMPNN scores do not match the returned designs.')
    if not isinstance(probabilities, list) or len(probabilities) != len(designs):
        raise ValueError('ProteinMPNN probability matrices do not match the returned designs.')
    for index, (design, score, matrix) in enumerate(zip(designs, scores, probabilities, strict=True), 1):
        if not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise ValueError('ProteinMPNN returned a non-finite score.')
        if not isinstance(matrix, list) or len(matrix) != len(design['sequence']):
            raise ValueError('ProteinMPNN probability matrix length differs from a design.')
        for row in matrix:
            if (not isinstance(row, list) or len(row) != 21
                    or any(not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in row)):
                raise ValueError('ProteinMPNN probability matrix is not finite [L,21] data.')
        header_score = design['metadata'].get('score')
        if header_score is not None and not math.isclose(float(header_score), float(score), rel_tol=1e-5, abs_tol=1e-6):
            raise ValueError(f'ProteinMPNN mfasta score differs from scores[{index - 1}].')
        design['sample'] = int(design['metadata'].get('sample', index))
        design['score'] = float(score)
        design['global_score'] = float(design['metadata'].get('global_score', score))
        design['sequence_recovery'] = float(design['metadata']['seq_recovery']) if 'seq_recovery' in design['metadata'] else None
    return {'input': records[0], 'designs': designs,
            'probability_shape': [len(probabilities), len(designs[0]['sequence']), 21]}


def publish_bytes(path: Path, data: bytes):
    with staged_output(path) as staged:
        staged.path.write_bytes(data)
    return staged.receipt


def draw_logo(axis, sequences: list[str]):
    length = len(sequences[0])
    font = FontProperties(family='DejaVu Sans', weight='bold')
    for position in range(length):
        counts = {letter: sum(sequence[position] == letter for sequence in sequences) for letter in AMINO_ACIDS}
        frequencies = {letter: count / len(sequences) for letter, count in counts.items() if count}
        entropy = -sum(value * math.log2(value) for value in frequencies.values())
        information = max(0.0, math.log2(len(AMINO_ACIDS)) - entropy)
        bottom = 0.0
        for letter, frequency in sorted(frequencies.items(), key=lambda item: item[1]):
            height = frequency * information
            if height <= 0:
                continue
            glyph = TextPath((0, 0), letter, size=1, prop=font)
            bounds = glyph.get_extents()
            sx, sy = 0.82 / bounds.width, height / bounds.height
            transform = Affine2D().scale(sx, sy).translate(
                position + 0.09 - bounds.xmin * sx, bottom - bounds.ymin * sy)
            axis.add_patch(PathPatch(glyph, transform=transform + axis.transData,
                                     color=COLORS.get(letter, '#40534a'), lw=0))
            bottom += height
    axis.set_xlim(0, length)
    axis.set_ylim(0, math.log2(len(AMINO_ACIDS)) + 0.15)
    axis.set_ylabel('bits')
    axis.set_xlabel('backbone position')
    axis.set_title('Observed sequence logo across returned designs')
    ticks = np.arange(0, length, 5)
    axis.set_xticks(ticks + 0.5, [str(item + 1) for item in ticks])
    axis.spines[['top', 'right']].set_visible(False)


def render_summary(designs: list[dict]) -> bytes:
    ranked = sorted(designs, key=lambda row: (row['score'], row['sample']))
    figure = plt.figure(figsize=(16, 9), facecolor='#f4f7f3')
    grid = figure.add_gridspec(2, 1, height_ratios=[1.35, 1], hspace=0.32)
    logo_axis = figure.add_subplot(grid[0])
    draw_logo(logo_axis, [row['sequence'] for row in designs])
    table_axis = figure.add_subplot(grid[1]); table_axis.axis('off')
    table_rows = [[rank, row['sample'], f"{row['score']:.6f}",
                   '' if row['sequence_recovery'] is None else f"{row['sequence_recovery']:.3f}",
                   row['sequence']]
                  for rank, row in enumerate(ranked, 1)]
    table = table_axis.table(cellText=table_rows,
                             colLabels=['rank*', 'sample', 'model score', 'sequence recovery', 'sequence'],
                             colWidths=[0.06, 0.07, 0.11, 0.13, 0.63], loc='center', cellLoc='left')
    table.auto_set_font_size(False); table.set_fontsize(9); table.scale(1, 1.45)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor('#c8d2cc')
        cell.set_facecolor('#dcebe3' if row == 0 else '#ffffff')
    table_axis.set_title('*Ranked by ascending returned model score; not experimental performance', pad=12)
    figure.suptitle('ProteinMPNN · deterministic design summary', fontsize=18, color='#19241d')
    buffer = io.BytesIO()
    figure.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                   metadata={'Software': 'Nebius Scientific AI'})
    plt.close(figure)
    return buffer.getvalue()


def operation_metadata(path: Path) -> dict:
    value = load(path) or {}
    if isinstance(value, dict) and isinstance(value.get('structuredContent'), dict):
        value = value['structuredContent']
    return value if isinstance(value, dict) else {}


def elapsed_seconds(operation: dict):
    start = operation.get('accepted_at')
    end = operation.get('completed_at')
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    return (datetime.fromisoformat(end.replace('Z', '+00:00'))
            - datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds()


def materialize(result_path: Path, operation_path: Path, backbone: Path, output_dir: Path, model: str) -> dict:
    raw = result_path.read_bytes()
    parsed = validate_result(json.loads(raw))
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    designs = parsed['designs']
    ranked = sorted(designs, key=lambda row: (row['score'], row['sample']))
    csv_buffer = io.StringIO(newline='')
    writer = csv.DictWriter(csv_buffer, fieldnames=('rank', 'sample', 'score', 'global_score', 'sequence_recovery', 'sequence'))
    writer.writeheader()
    for rank, row in enumerate(ranked, 1):
        writer.writerow({'rank': rank, **{key: row[key] for key in writer.fieldnames if key != 'rank'}})
    table_receipt = publish_bytes(output_dir / 'designs.csv', csv_buffer.getvalue().encode())
    image_receipt = publish_bytes(output_dir / 'proteinmpnn-summary.png', render_summary(designs))
    operation = operation_metadata(operation_path)
    summary = {
        'schema': 'nebius-scientific-ai/proteinmpnn-design/v1',
        'state': 'succeeded', 'model': model, 'operation_id': operation.get('id'),
        'source': {'path': str(backbone), **file_identity(backbone)},
        'parameters': {'random_seed': None, 'num_sequences': len(designs)},
        'input_sequence': parsed['input']['sequence'], 'sequence_length': len(parsed['input']['sequence']),
        'designs': [{key: row[key] for key in ('sample', 'score', 'global_score', 'sequence_recovery', 'sequence')}
                    for row in ranked],
        'probability_shape': parsed['probability_shape'],
        'timing': {'accepted_at': operation.get('accepted_at'), 'completed_at': operation.get('completed_at'),
                   'elapsed_seconds': elapsed_seconds(operation)},
        'artifacts': {'summary_image': image_receipt, 'designs_csv': table_receipt},
        'provenance': {'result_path': str(result_path), 'result_sha256': hashlib.sha256(raw).hexdigest()},
        'limitations': ['Model scores are model outputs, not experimental binding, folding or function.',
                        'Ascending score rank is presentation order and not biological validation.'],
    }
    save(output_dir / 'summary.json', summary)
    return summary


def run(args, runner=subprocess.run):
    backbone = args.backbone.resolve(); verified_pdb(backbone)
    output_dir = args.output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    upload_dir, run_dir, analysis_dir = output_dir / 'upload', output_dir / 'run', output_dir / 'analysis'
    input_path = output_dir / 'input.json'
    python, helper_dir = Path(sys.executable), Path(__file__).resolve().parent
    upload = execute([str(python), str(helper_dir / 'upload-artifact.py'), '--model', args.model,
                      '--file', str(backbone), '--media-type', 'chemical/x-pdb',
                      '--output-dir', str(upload_dir), '--idempotency-key', args.idempotency_key + '-source'], runner)
    if upload.returncode == 75:
        return {'state': 'upload_pending', 'output_dir': str(output_dir)}, 75
    artifact = verified_artifact_reference(upload_dir / 'artifact.json', backbone)
    payload = {'input_pdb': artifact, 'random_seed': args.seed,
               'num_seq_per_target': args.num_sequences, 'sampling_temp': args.temperature,
               'omit_AAs': ['X']}
    if args.chain:
        payload['input_pdb_chains'] = args.chain
    existing = load(input_path)
    if existing is not None and existing != payload:
        raise ValueError('Saved ProteinMPNN input differs; use a new output directory.')
    save(input_path, payload)
    command = [str(python), str(helper_dir / 'invoke-native.py'), '--model', args.model, '--tool', args.tool,
               '--input', str(input_path), '--output-dir', str(run_dir),
               '--idempotency-key', args.idempotency_key, '--wait-seconds', str(args.wait_seconds)]
    if args.recover_only:
        command.append('--recover-only')
    native = execute(command, runner)
    receipt = load(run_dir / 'receipt.json') or {}; operation_id = receipt.get('operation_id')
    if native.returncode == 75:
        return {'state': receipt.get('state', 'pending'), 'operation_id': operation_id,
                'output_dir': str(output_dir)}, 75
    summary = materialize(run_dir / 'result.json', run_dir / 'operation.json', backbone, analysis_dir, args.model)
    summary['parameters'].update({'random_seed': args.seed, 'sampling_temperature': args.temperature,
                                  'designed_chains': args.chain or None})
    save(analysis_dir / 'summary.json', summary)
    ranked_designs = [
        {
            'rank': rank,
            'sample': row['sample'],
            'model_score': row['score'],
            'global_model_score': row['global_score'],
            'sequence_recovery': row['sequence_recovery'],
            'sequence': row['sequence'],
        }
        for rank, row in enumerate(summary['designs'], 1)
    ]
    return {'state': 'succeeded', 'operation_id': operation_id, 'model': args.model,
            'parameters': summary['parameters'], 'sequence_length': summary['sequence_length'],
            'num_sequences': len(summary['designs']), 'ranked_designs': ranked_designs,
            'probability_shape': summary['probability_shape'], 'timing': summary['timing'],
            'allowed_result_fields': ['model_score', 'global_model_score', 'sequence_recovery'],
            'absent_result_fields': ['pLDDT', 'pTM', 'PAE', 'binding', 'folding', 'function'],
            'summary_image': str(analysis_dir / 'proteinmpnn-summary.png'),
            'designs_csv': str(analysis_dir / 'designs.csv'),
            'summary_path': str(analysis_dir / 'summary.json')}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backbone', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--num-sequences', type=int, default=8)
    parser.add_argument('--temperature', type=float, default=0.1)
    parser.add_argument('--chain', action='append')
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='proteinmpnn')
    parser.add_argument('--tool', default='infer_proteinmpnn_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not 1 <= args.seed <= 2_147_483_647
            or not 1 <= args.num_sequences <= 8 or not 0.01 <= args.temperature <= 1
            or args.wait_seconds < 0):
        parser.error('Invalid ProteinMPNN key, seed, sequence count, temperature or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect saved upload/run/analysis receipts; do not resubmit elsewhere.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
