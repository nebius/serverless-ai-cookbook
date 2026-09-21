#!/usr/bin/env python3
"""Run one durable GenMol request and publish a deterministic candidate review.

The wrapper owns the single inference admission, resumes its retained receipt,
measures every returned row with RDKit, and renders presentation artifacts. It
does not repair, pad, replace, or make biological claims about molecules.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rdkit import Chem
from rdkit.Chem import Draw, Lipinski

from recording_pipeline import immutable_input, invoke, operation_metadata, timing, unwrap, workspace_urls
from scientific_receipts import load, save, staged_output


def analysis_module():
    path = Path(__file__).resolve().with_name('molecule-analysis.py')
    spec = importlib.util.spec_from_file_location('scientific_molecule_analysis', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('The installed molecule-analysis helper is unavailable.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def aromatic_heterocycle(molecule: Chem.Mol) -> bool:
    for ring in molecule.GetRingInfo().AtomRings():
        atoms = [molecule.GetAtomWithIdx(index) for index in ring]
        if atoms and all(atom.GetIsAromatic() for atom in atoms) and any(
                atom.GetAtomicNum() not in (1, 6) for atom in atoms):
            return True
    return False


def classify(report: dict) -> list[dict]:
    rows = []
    for source in report['rows']:
        row = dict(source)
        molecule = Chem.MolFromSmiles(row['canonical_smiles']) if row['valid'] else None
        hbond_donors = int(Lipinski.NumHDonors(molecule)) if molecule is not None else None
        has_ring = aromatic_heterocycle(molecule) if molecule is not None else False
        first_canonical = row['canonical_duplicate_of_row'] is None
        retained = bool(row['valid'] and first_canonical and hbond_donors >= 1 and has_ring)
        exclusions = []
        if not row['valid']:
            exclusions.append('invalid')
        elif not first_canonical:
            exclusions.append(f"canonical duplicate of row {row['canonical_duplicate_of_row']}")
        else:
            if hbond_donors < 1:
                exclusions.append('no hydrogen-bond donor')
            if not has_ring:
                exclusions.append('no aromatic heterocycle')
        row.update(hydrogen_bond_donors=hbond_donors,
                   has_aromatic_heterocycle=has_ring,
                   retained=retained,
                   retention_status='retained' if retained else '; '.join(exclusions))
        rows.append(row)
    return rows


def font(size: int, bold: bool = False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    path = Path('/usr/share/fonts/truetype/dejavu') / name
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def shortened(value: str | None, length: int = 42) -> str:
    value = value or 'invalid SMILES'
    return value if len(value) <= length else value[:length - 1] + '…'


def render_grid(rows: list[dict], counts: dict) -> Image.Image:
    columns, card_width, card_height, gap, header = 4, 340, 280, 14, 116
    row_count = max(1, math.ceil(len(rows) / columns))
    width = columns * card_width + (columns + 1) * gap
    height = header + row_count * card_height + (row_count + 1) * gap
    canvas = Image.new('RGB', (width, height), '#f3f7f3')
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 14), 'GenMol candidate review', fill='#12251b', font=font(30, True))
    facts = (f"requested {counts['requested']}  ·  returned {counts['generated']}  ·  "
             f"valid {counts['valid']}  ·  duplicates {counts['duplicates']}  ·  "
             f"retained {counts['retained']}")
    draw.text((gap, 58), facts, fill='#24523b', font=font(19, True))
    draw.text((gap, 86), 'Retained = valid + first canonical occurrence + HBD ≥ 1 + aromatic heterocycle',
              fill='#4c6256', font=font(14))
    for index, row in enumerate(rows):
        grid_row, column = divmod(index, columns)
        x = gap + column * (card_width + gap)
        y = header + gap + grid_row * (card_height + gap)
        color = '#2a8c5d' if row['retained'] else '#aab8b0'
        draw.rounded_rectangle((x, y, x + card_width, y + card_height), radius=14,
                               fill='#ffffff', outline=color, width=3)
        draw.text((x + 14, y + 10), f"Row {row['row']}", fill='#17251d', font=font(17, True))
        molecule = Chem.MolFromSmiles(row['canonical_smiles']) if row['valid'] else None
        if molecule is not None:
            depiction = Draw.MolToImage(molecule, size=(300, 165), kekulize=True)
            canvas.paste(depiction.convert('RGB'), (x + 20, y + 38))
        else:
            draw.text((x + 75, y + 112), 'Invalid molecule', fill='#8d3d3d', font=font(18, True))
        qed = row['independent_qed']
        details = (f"QED {qed:.3f}  ·  HBD {row['hydrogen_bond_donors']}  ·  "
                   f"aromatic heterocycle {'yes' if row['has_aromatic_heterocycle'] else 'no'}") \
                  if qed is not None else 'QED unavailable'
        draw.text((x + 14, y + 207), details, fill='#33473c', font=font(13))
        draw.text((x + 14, y + 229), shortened(row['canonical_smiles']), fill='#33473c', font=font(12))
        status_color = '#18784c' if row['retained'] else '#6b756f'
        draw.text((x + 14, y + 251), shortened(row['retention_status'], 48),
                  fill=status_color, font=font(12, row['retained']))
    return canvas


def publish_csv(path: Path, rows: list[dict]):
    fields = ('row', 'raw_smiles', 'valid', 'canonical_smiles', 'canonical_duplicate_of_row',
              'heavy_atoms', 'independent_qed', 'model_score', 'hydrogen_bond_donors',
              'has_aromatic_heterocycle', 'retained', 'retention_status')
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction='ignore')
    writer.writeheader(); writer.writerows(rows)
    with staged_output(path) as staged:
        staged.path.write_text(buffer.getvalue(), encoding='utf-8')
    return staged.receipt


def run(args, runner=None):
    output_dir = args.output_dir.resolve()
    run_dir, analysis_dir = output_dir / 'run', output_dir / 'analysis'
    input_path = output_dir / 'input.json'
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {'smiles': args.smiles_mask, 'num_molecules': args.num_molecules,
               'scoring': args.scoring, 'temperature': args.temperature,
               'noise': args.noise, 'unique': False}
    immutable_input(input_path, payload)
    options = dict(model=args.model, tool=args.tool, input_path=input_path,
                   directory=run_dir, idempotency_key=args.idempotency_key,
                   wait_seconds=args.wait_seconds, recover_only=args.recover_only)
    if runner is not None:
        options['runner'] = runner
    receipt, code = invoke(**options)
    if code == 75:
        return {'state': receipt.get('state', 'pending'),
                'operation_id': receipt.get('operation_id'),
                'output_dir': str(output_dir)}, 75

    result_path = run_dir / 'result.json'
    # Validate the exact envelope before the shared analyzer reads it.
    result = unwrap(load(result_path))
    if not isinstance(result.get('molecules'), list):
        raise ValueError('GenMol terminal result has no molecules list.')
    if result != load(result_path):
        save(analysis_dir / 'unwrapped-result.json', result)
        analyzed_result_path = analysis_dir / 'unwrapped-result.json'
    else:
        analyzed_result_path = result_path
    analyzer = analysis_module()
    report = analyzer.analyze_genmol_files(input_path, analyzed_result_path)
    analysis_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    analyzer.write_genmol_report(report, analysis_dir / 'metrics.json')
    rows = classify(report)
    counts = {'requested': report['requested_count'], 'generated': report['returned_count'],
              'valid': report['valid_count'],
              'duplicates': report['canonical_duplicate_valid_count'],
              'retained': sum(row['retained'] for row in rows)}
    grid_path, candidates_path = analysis_dir / 'candidate-grid.png', analysis_dir / 'candidates.csv'
    image = render_grid(rows, counts)
    with staged_output(grid_path) as staged:
        image.save(staged.path, format='PNG', optimize=True)
    grid_receipt = staged.receipt
    candidates_receipt = publish_csv(candidates_path, rows)
    operation = operation_metadata(run_dir / 'operation.json')
    unique_valid = [row for row in rows if row['valid'] and row['canonical_duplicate_of_row'] is None]
    ranked = sorted(unique_valid, key=lambda row: (-row['independent_qed'], row['row']))
    summary_path = analysis_dir / 'summary.json'
    links = workspace_urls(grid=grid_path, candidates=candidates_path,
                           metrics=analysis_dir / 'metrics.json', summary=summary_path)
    summary = {
        'schema': 'nebius-scientific-ai/genmol-candidate-review/v1',
        'state': 'succeeded', 'model': args.model,
        'operation_id': receipt.get('operation_id') or operation.get('id'),
        'timing': timing(operation), 'request': payload, 'counts': counts,
        'retention_criteria': {
            'valid_rdkit_sanitized': True, 'first_canonical_occurrence': True,
            'minimum_hydrogen_bond_donors': 1, 'aromatic_heterocycle': True,
            'qed_threshold': None,
        },
        'candidates': rows,
        'retained_candidates': [row for row in rows if row['retained']],
        'top_five_valid_unique_by_qed': [{key: row[key] for key in
            ('row', 'canonical_smiles', 'independent_qed')} for row in ranked[:5]],
        'artifacts': {'grid': grid_receipt, 'candidates_csv': candidates_receipt,
                      'metrics_path': str(analysis_dir / 'metrics.json')},
        'workspace_urls': links,
        'limitations': [
            'QED and structural filters are computed descriptors, not activity, safety, affinity, or therapeutic evidence.',
            'Invalid, duplicate, and excluded rows remain in the complete candidate table.',
            'The GenMol mask is a generation control, not a molecular-size bound.',
        ],
    }
    save(summary_path, summary)
    return {
        'state': 'succeeded', 'model': args.model, 'operation_id': summary['operation_id'],
        'timing': summary['timing'], 'counts': counts,
        'retention_criteria': summary['retention_criteria'],
        'retained_candidates': summary['retained_candidates'],
        'top_five_valid_unique_by_qed': summary['top_five_valid_unique_by_qed'],
        'grid_path': str(grid_path), 'candidates_path': str(candidates_path),
        'summary_path': str(summary_path), 'workspace_urls': links,
    }, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--num-molecules', type=int, default=16)
    parser.add_argument('--smiles-mask', default='[*{10-20}]')
    parser.add_argument('--scoring', default='QED', choices=('QED', 'LogP'))
    parser.add_argument('--temperature', type=float, default=1.0)
    parser.add_argument('--noise', type=float, default=1.0)
    parser.add_argument('--operation-wait-seconds', '--wait-seconds', dest='wait_seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='genmol')
    parser.add_argument('--tool', default='genmol_generate_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not 1 <= args.num_molecules <= 64
            or not args.smiles_mask or not 0 <= args.temperature <= 5
            or not 0 <= args.noise <= 5 or args.wait_seconds < 0):
        parser.error('Invalid GenMol key, count, mask, temperature, noise, or wait.')
    try:
        value, code = run(args)
        print(json.dumps(value, separators=(',', ':'), allow_nan=False))
        raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained run and analysis receipts; do not resubmit elsewhere.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
