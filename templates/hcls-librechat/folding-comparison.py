#!/usr/bin/env python3
"""Run a receipt-safe OpenFold2/OpenFold3/Boltz2 comparison campaign.

Every model receives the same canonical sequence through its exact hosted
contract. References are explicit or selected by an exact sequence match. The
reported RMSD/TM-score is deterministic post-processing, not model confidence.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import glob
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont

from recording_pipeline import (immutable_input, invoke, operation_metadata,
                                publish_bytes, timing, unwrap, workspace_urls)
from scientific_receipts import load, save, staged_derived_view


MODELS = {
    'openfold2': ('infer_openfold2_native', 'pdb'),
    'openfold3': ('infer_openfold3_native', 'cif'),
    'boltz2': ('boltz2_predict_native', 'cif'),
}
AMINO_ACIDS = frozenset('ACDEFGHIKLMNPQRSTVWY')


def structure_analysis():
    path = Path(__file__).resolve().with_name('structure-analysis.py')
    spec = importlib.util.spec_from_file_location('recording_structure_analysis', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('The installed structure analysis helper is unavailable.')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def safe_name(value: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_-]+', '-', value).strip('-_').lower()
    if not value:
        raise ValueError('A nonempty safe name is required.')
    return value[:48]


def named_file(value: str) -> tuple[str, Path]:
    name, separator, raw = value.partition('=')
    if not separator or safe_name(name) != name or not Path(raw).is_absolute():
        raise argparse.ArgumentTypeError('Use safe-name=/absolute/file.')
    return name, Path(raw)


def read_fasta(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise ValueError(f'FASTA does not exist: {path}')
    records, header, chunks = [], None, []
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('>'):
            if header is not None:
                records.append((header, ''.join(chunks)))
            header, chunks = line[1:] or 'protein', []
        elif header is None:
            raise ValueError('FASTA sequence appears before its header.')
        else:
            chunks.append(''.join(line.split()).upper())
    if header is not None:
        records.append((header, ''.join(chunks)))
    if len(records) != 1 or not 6 <= len(records[0][1]) <= 1024 \
            or any(letter not in AMINO_ACIDS for letter in records[0][1]):
        raise ValueError('Each comparison FASTA must contain one 6–1024 residue canonical protein.')
    return records[0]


def collect_fastas(args) -> list[tuple[str, Path]]:
    values = [(name, path.resolve()) for name, path in (args.fasta or [])]
    for pattern in args.glob_fasta or []:
        if not pattern.startswith('/workspace/'):
            raise ValueError('FASTA globs must stay below /workspace.')
        values.extend((safe_name(Path(raw).stem), Path(raw).resolve())
                      for raw in sorted(glob.glob(pattern, recursive=True)) if Path(raw).is_file())
    if not values:
        raise ValueError('No FASTA inputs were selected.')
    result, names, paths = [], set(), set()
    for name, path in values:
        if name in names and str(path) not in paths:
            raise ValueError(f'FASTA name {name} refers to multiple files.')
        if str(path) not in paths:
            result.append((name, path)); names.add(name); paths.add(str(path))
    return result


def exact_reference(sequence: str, candidates: list[Path], analysis) -> tuple[Path, str]:
    matches = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            chains = analysis.load_structure(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        for chain, residues in chains.items():
            if analysis.sequence(residues) == sequence:
                matches.append((path.resolve(), chain))
    if len(matches) != 1:
        raise ValueError(f'Expected one exact-sequence reference chain, found {len(matches)}.')
    return matches[0]


def references(args, fastas: list[tuple[str, Path]], analysis) -> tuple[dict[str, tuple[Path, str]], dict[str, str]]:
    explicit = {name: path.resolve() for name, path in (args.reference or [])}
    if len(explicit) != len(args.reference or []):
        raise ValueError('Reference names must be unique.')
    pool = sorted(args.reference_dir.resolve().glob('*.pdb')) if args.reference_dir else []
    result, failures = {}, {}
    for name, fasta in fastas:
        try:
            _, sequence = read_fasta(fasta)
            selected = [explicit[name]] if name in explicit else pool
            if not selected:
                raise ValueError(f'No explicit reference or reference directory is available for {name}.')
            result[name] = exact_reference(sequence, selected, analysis)
        except Exception as error:
            failures[name] = f'{type(error).__name__}: {error}'
    return result, failures


def payload(model: str, name: str, sequence: str) -> dict:
    if model == 'openfold2':
        return {'input_id': name, 'sequence': sequence,
                'selected_models': [1], 'relax_prediction': False}
    if model == 'openfold3':
        return {'request_id': name, 'inputs': [{'input_id': name, 'output_format': 'cif',
                'molecules': [{'type': 'protein', 'id': 'A', 'sequence': sequence}]}]}
    if model == 'boltz2':
        return {'polymers': [{'id': 'A', 'molecule_type': 'protein', 'sequence': sequence,
                'msa': {'msa_search': {'a3m': {'alignment': f'>query\n{sequence}\n',
                                                'format': 'a3m', 'rank': 0}}}}],
                'recycling_steps': 3, 'sampling_steps': 200, 'diffusion_samples': 1,
                'output_format': 'mmcif'}
    raise ValueError(f'Unsupported comparison model {model}.')


def parse_prediction(model: str, value: dict, name: str) -> tuple[str, dict, dict]:
    result = unwrap(value)
    if model == 'openfold2':
        if result.get('input_id') != name:
            raise ValueError('OpenFold2 returned a different input identity.')
        rows = result.get('structures_in_ranked_order')
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError('OpenFold2 returned the wrong structure cardinality.')
        row = rows[0]; structure = row.get('structure')
        confidence = {'mean_plddt': row.get('confidence'), 'ptm_score': row.get('ptm_score')}
        runtime = {'inference_seconds': row.get('inference_seconds')}
    elif model == 'openfold3':
        outputs = result.get('outputs')
        if not isinstance(outputs, list) or len(outputs) != 1 or outputs[0].get('input_id') != name:
            raise ValueError('OpenFold3 returned the wrong output identity or cardinality.')
        rows = outputs[0].get('structures_with_scores')
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError('OpenFold3 returned the wrong structure cardinality.')
        row = rows[0]; structure = row.get('structure')
        confidence = {key: row.get(key) for key in
                      ('confidence_score', 'complex_plddt_score', 'complex_pde_score', 'ptm_score', 'iptm_score')}
        runtime = outputs[0].get('runtime_metrics') or {}
    else:
        rows = result.get('structures')
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError('Boltz2 returned the wrong structure cardinality.')
        row = rows[0]; structure = row.get('structure')
        scores, ptm = result.get('confidence_scores'), result.get('ptm_scores')
        if not isinstance(scores, list) or len(scores) != 1 or not isinstance(ptm, list) or len(ptm) != 1:
            raise ValueError('Boltz2 returned the wrong confidence cardinality.')
        confidence = {'confidence_score': scores[0], 'ptm_score': ptm[0]}; runtime = {}
    if not isinstance(structure, str) or len(structure) < 80 \
            or ('ATOM ' not in structure and '_atom_site.' not in structure):
        raise ValueError(f'{model} returned no valid coordinate structure.')
    for key, score in confidence.items():
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))
                                  or not math.isfinite(float(score))):
            raise ValueError(f'{model} returned invalid {key}.')
    return structure, confidence, runtime


def matching_prediction_chain(sequence: str, structure: str, analysis) -> str:
    matches = [name for name, residues in analysis.load_structure(structure).items()
               if analysis.sequence(residues) == sequence]
    if len(matches) != 1:
        raise ValueError(f'Expected one exact-sequence prediction chain, found {len(matches)}.')
    return matches[0]


def run_case(*, name: str, fasta: Path, reference: Path, reference_chain: str,
             model: str, args, analysis, runner=subprocess.run) -> tuple[dict, int]:
    header, sequence = read_fasta(fasta)
    directory = args.output_dir.resolve() / 'cases' / name / model
    input_path = directory / 'input.json'; request = payload(model, name, sequence)
    immutable_input(input_path, request)
    receipt, code = invoke(model=model, tool=MODELS[model][0], input_path=input_path,
                           directory=directory / 'run',
                           idempotency_key=f'{args.idempotency_key}-{name}-{model}',
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only,
                           runner=runner)
    base = {'case': name, 'model': model, 'fasta': str(fasta), 'reference': str(reference),
            'reference_chain': reference_chain, 'operation_id': receipt.get('operation_id')}
    if code == 75:
        return {**base, 'state': receipt.get('state', 'pending')}, 75
    structure, confidence, runtime = parse_prediction(model, load(directory / 'run' / 'result.json'), name)
    prediction_chain = matching_prediction_chain(sequence, structure, analysis)
    metrics, _ = analysis.compare(reference.read_text(encoding='utf-8'), structure,
                                  [(reference_chain, prediction_chain)])
    analysis_dir = directory / 'analysis'; analysis_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    suffix = MODELS[model][1]; structure_path = analysis_dir / f'prediction.{suffix}'
    structure_receipt = publish_bytes(structure_path, structure.encode())
    operation = operation_metadata(directory / 'run' / 'operation.json')
    summary_path = analysis_dir / 'summary.json'
    links = workspace_urls(structure=structure_path, summary=summary_path)
    summary = {**base, 'state': 'succeeded', 'header': header, 'sequence_length': len(sequence),
               'prediction_chain': prediction_chain, 'confidence': confidence,
               'reported_runtime': runtime, 'operation_timing': timing(operation),
               'comparison': {'global_ca_rmsd_angstrom': metrics['global_ca_rmsd_angstrom'],
                              'tm_score_reference_normalized_ca': metrics['tm_score_reference_normalized_ca'],
                              'mapped_residues': metrics['mapped_residues'],
                              'reference_coverage': metrics['chains'][0]['reference_coverage']},
               'structure_artifact': structure_receipt, 'structure_path': str(structure_path),
               'summary_path': str(summary_path), 'workspace_urls': links,
               'limitations': ['Model confidence is reported separately from reference agreement.',
                               'The compared hosted contracts use different inputs and inference methods; this is not a controlled benchmark.',
                               'RMSD and helper TM-score describe fitted agreement with this supplied reference.']}
    save(summary_path, summary)
    return summary, 0


def font(size: int, bold: bool = False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    try:
        return ImageFont.truetype(str(Path('/usr/share/fonts/truetype/dejavu') / name), size)
    except OSError:
        return ImageFont.load_default()


def write_gallery(cases: list[dict], proteins: list[str], path: Path) -> bool:
    values = {(case['case'], case['model']): case['comparison']['tm_score_reference_normalized_ca']
              for case in cases if case.get('state') == 'succeeded'}
    if not values:
        return False
    models = list(MODELS); cell, left, top = 210, 240, 82
    image = Image.new('RGB', (left + cell * len(models) + 20, top + cell * len(proteins) + 20), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((12, 14), 'Reference-normalized fitted C-alpha TM-score', fill='#173c2a', font=font(20, True))
    for column, model in enumerate(models):
        draw.text((left + column * cell + 35, 50), model, fill='#173c2a', font=font(15, True))
    for row, protein in enumerate(proteins):
        draw.text((14, top + row * cell + 82), protein[:25], fill='#173c2a', font=font(15, True))
        for column, model in enumerate(models):
            box = (left + column * cell, top + row * cell,
                   left + (column + 1) * cell - 6, top + (row + 1) * cell - 6)
            value = values.get((protein, model))
            color = '#e4e8e5' if value is None else (int(232 - 130 * value), int(242 - 42 * value), int(233 - 115 * value))
            draw.rectangle(box, fill=color, outline='#8ba497')
            label = 'unavailable' if value is None else f'{value:.4f}'
            draw.text((box[0] + 52, box[1] + 82), label, fill='#173c2a', font=font(18, True))
    with staged_derived_view(path) as staged:
        image.save(staged.path, format='PNG', optimize=True)
    return True


def write_csv(path: Path, cases: list[dict]) -> None:
    fields = ['case', 'model', 'state', 'operation_id', 'sequence_length',
              'operation_elapsed_seconds', 'reported_runtime', 'reported_confidence',
              'fitted_ca_rmsd_angstrom', 'reference_normalized_ca_tm_score',
              'mapped_residues', 'reference_coverage', 'structure_url', 'summary_url']
    rows = []
    for case in cases:
        comparison, links = case.get('comparison') or {}, case.get('workspace_urls') or {}
        rows.append({'case': case['case'], 'model': case['model'], 'state': case.get('state'),
                     'operation_id': case.get('operation_id'), 'sequence_length': case.get('sequence_length'),
                     'operation_elapsed_seconds': (case.get('operation_timing') or {}).get('elapsed_seconds'),
                     'reported_runtime': json.dumps(case.get('reported_runtime') or {}, sort_keys=True),
                     'reported_confidence': json.dumps(case.get('confidence') or {}, sort_keys=True),
                     'fitted_ca_rmsd_angstrom': comparison.get('global_ca_rmsd_angstrom'),
                     'reference_normalized_ca_tm_score': comparison.get('tm_score_reference_normalized_ca'),
                     'mapped_residues': comparison.get('mapped_residues'),
                     'reference_coverage': comparison.get('reference_coverage'),
                     'structure_url': links.get('structure'), 'summary_url': links.get('summary')})
    with staged_derived_view(path) as staged, staged.path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def run(args, runner=subprocess.run) -> tuple[dict, int]:
    args.output_dir = args.output_dir.resolve(); args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    analysis = structure_analysis(); fastas = collect_fastas(args); refs, reference_failures = references(args, fastas, analysis)
    jobs = [(name, fasta, refs[name][0], refs[name][1], model)
            for name, fasta in fastas if name in refs for model in MODELS]
    def execute(job):
        try:
            return run_case(name=job[0], fasta=job[1], reference=job[2], reference_chain=job[3],
                            model=job[4], args=args, analysis=analysis, runner=runner)
        except Exception as error:
            return ({'case': job[0], 'model': job[4], 'fasta': str(job[1]),
                     'reference': str(job[2]), 'reference_chain': job[3], 'state': 'failed',
                     'error_type': type(error).__name__, 'details': str(error)[:500]}, 1)
    if jobs:
        with ThreadPoolExecutor(max_workers=min(args.max_workers, len(jobs))) as pool:
            outcomes = list(pool.map(execute, jobs))
    else:
        outcomes = []
    for name, fasta in fastas:
        if name not in reference_failures:
            continue
        for model in MODELS:
            outcomes.append(({'case': name, 'model': model, 'fasta': str(fasta),
                              'state': 'failed', 'error_type': 'ReferenceResolutionError',
                              'details': reference_failures[name]}, 1))
    cases, codes = [item[0] for item in outcomes], [item[1] for item in outcomes]
    csv_path, gallery_path = args.output_dir / 'measurements.csv', args.output_dir / 'gallery.png'
    report_path, summary_path = args.output_dir / 'report.md', args.output_dir / 'batch.json'
    write_csv(csv_path, cases); has_gallery = write_gallery(cases, [name for name, _ in fastas], gallery_path)
    links = workspace_urls(summary=summary_path, csv=csv_path, report=report_path,
                           gallery=gallery_path if has_gallery else None)
    pending, failed = sum(code == 75 for code in codes), sum(code not in (0, 75) for code in codes)
    state = 'failed' if failed else ('pending' if pending else 'succeeded')
    summary = {'schema': 'nebius-scientific-ai/folding-comparison/v1', 'state': state,
               'protein_count': len(fastas), 'run_count': len(cases),
               'succeeded_count': sum(code == 0 for code in codes), 'pending_count': pending,
               'failed_count': failed, 'cases': cases, 'workspace_urls': links,
               'benchmark_status': 'not-a-controlled-benchmark-different-hosted-contracts'}
    lines = ['# Three-model structure comparison', '',
             'This is not a controlled benchmark: the hosted contracts use different model inputs and methods.', '',
             f"- [Manifest]({links.get('summary', 'batch.json')})",
             f"- [Measurements CSV]({links.get('csv', 'measurements.csv')})"]
    if links.get('gallery'):
        lines.append(f"- [Ranked TM-score gallery]({links['gallery']})")
    lines += ['', '| Protein | Model | State | Operation | Runtime (s) | Confidence | RMSD (Å) | Helper TM-score |',
              '|---|---|---|---|---:|---|---:|---:|']
    for case in cases:
        comparison = case.get('comparison') or {}
        elapsed = (case.get('operation_timing') or {}).get('elapsed_seconds', 'unavailable')
        confidence = json.dumps(case.get('confidence') or {}, sort_keys=True).replace('|', '\\|')
        lines.append(f"| {case['case']} | {case['model']} | {case['state']} | {case.get('operation_id') or 'unavailable'} | "
                     f"{elapsed} | {confidence} | {comparison.get('global_ca_rmsd_angstrom', 'unavailable')} | "
                     f"{comparison.get('tm_score_reference_normalized_ca', 'unavailable')} |")
    with staged_derived_view(report_path) as staged:
        staged.path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    save(summary_path, summary)
    return summary, 1 if failed else (75 if pending else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fasta', action='append', type=named_file)
    parser.add_argument('--glob-fasta', action='append')
    parser.add_argument('--reference', action='append', type=named_file)
    parser.add_argument('--reference-dir', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=600)
    parser.add_argument('--max-workers', type=int, default=3)
    parser.add_argument('--recover-only', action='store_true')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 120 or not 0 <= args.wait_seconds <= 3600
            or not 1 <= args.max_workers <= 8):
        parser.error('Use an 8–120 character key, a 0–3600 second wait, and 1–8 workers.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'), allow_nan=False)); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained campaign inputs and receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
