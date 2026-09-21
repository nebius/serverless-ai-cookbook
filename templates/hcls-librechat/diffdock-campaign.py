#!/usr/bin/env python3
"""Run a durable DiffDock campaign from workspace receptors and SMILES.

The command owns receptor upload, one idempotent operation per receptor/ligand
pair, terminal pose validation, and presentation artifacts. Re-running the same
command resumes retained operations; it never substitutes another docking path.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import glob
import io
import json
import math
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont
from rdkit import Chem
from rdkit.Chem import Draw

from recording_pipeline import (immutable_input, invoke, operation_metadata,
                                publish_bytes, timing, unwrap, upload_source,
                                workspace_urls)
from scientific_receipts import load, save, staged_derived_view


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


def named_smiles(value: str) -> tuple[str, str]:
    name, separator, smiles = value.partition('=')
    if not separator or safe_name(name) != name or not smiles.strip():
        raise argparse.ArgumentTypeError('Use safe-name=SMILES.')
    return name, smiles.strip()


def read_smiles(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f'Ligand file does not exist: {path}')
    rows = [line.strip() for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
    if len(rows) != 1:
        raise ValueError(f'Ligand file must contain exactly one non-comment row: {path}')
    smiles = rows[0].split()[0]
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None or molecule.GetNumAtoms() == 0:
        raise ValueError(f'Ligand file contains invalid SMILES: {path}')
    return Chem.MolToSmiles(molecule, isomericSmiles=True)


def collect_ligands(args) -> list[tuple[str, str]]:
    rows = list(args.ligand or [])
    rows.extend((name, read_smiles(path.resolve())) for name, path in (args.ligand_file or []))
    for pattern in args.glob_ligands or []:
        if not pattern.startswith('/workspace/'):
            raise ValueError('Ligand globs must stay below /workspace.')
        for raw in sorted(glob.glob(pattern, recursive=True)):
            path = Path(raw)
            if path.is_file():
                rows.append((safe_name(f'{path.parent.name}-{path.stem}'), read_smiles(path.resolve())))
    if args.genmol_summary:
        value = load(args.genmol_summary.resolve())
        candidates = value.get('top_five_valid_unique_by_qed') if isinstance(value, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise ValueError('GenMol summary has no top-five valid unique QED candidates.')
        for item in candidates[:args.top_candidates]:
            if not isinstance(item, dict) or not isinstance(item.get('canonical_smiles'), str):
                raise ValueError('GenMol candidate is missing canonical_smiles.')
            rows.append((safe_name(f"genmol-row-{item.get('row')}"), item['canonical_smiles']))
    if not rows:
        raise ValueError('At least one ligand source is required.')
    result, seen_names, seen_pairs = [], set(), set()
    for name, smiles in rows:
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None or molecule.GetNumAtoms() == 0:
            raise ValueError(f'Invalid ligand SMILES for {name}.')
        canonical = Chem.MolToSmiles(molecule, isomericSmiles=True)
        pair = (name, canonical)
        if name in seen_names and pair not in seen_pairs:
            raise ValueError(f'Ligand name {name} refers to multiple molecules.')
        if pair not in seen_pairs:
            result.append(pair); seen_names.add(name); seen_pairs.add(pair)
    return result


def validate_receptor(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f'Receptor does not exist: {path}')
    data = path.read_bytes()
    if not 40 <= len(data) <= 2_000_000 or b'ATOM' not in data:
        raise ValueError(f'Receptor is not a bounded PDB with ATOM records: {path}')


def validate_result(value: dict, ligand: str, expected_poses: int) -> list[dict]:
    result = unwrap(value)
    if result.get('status') not in (None, 'success'):
        raise ValueError('DiffDock returned a non-success result.')
    if result.get('ligand') != ligand:
        raise ValueError('DiffDock returned a different ligand identity.')

    # The native DiffDock contract publishes one MolBlock per ranked pose and
    # one confidence value per position.  A few retained fixtures from the
    # pre-native gateway use the equivalent normalized ``poses`` rows, so keep
    # that representation readable without weakening either cardinality or
    # structure validation.
    positions = result.get('ligand_positions')
    confidences = result.get('position_confidence')
    if isinstance(positions, list) or isinstance(confidences, list):
        if (not isinstance(positions, list) or not isinstance(confidences, list)
                or len(positions) != expected_poses or len(confidences) != expected_poses):
            raise ValueError('DiffDock returned the wrong pose cardinality.')
        poses = [
            {'rank': index, 'confidence': confidence, 'sdf': block}
            for index, (block, confidence) in enumerate(zip(positions, confidences), 1)
        ]
    else:
        poses = result.get('poses')
    if not isinstance(poses, list) or len(poses) != expected_poses:
        raise ValueError('DiffDock returned the wrong pose cardinality.')
    checked = []
    for index, pose in enumerate(poses, 1):
        if (not isinstance(pose, dict) or pose.get('rank') != index
                or isinstance(pose.get('confidence'), bool)
                or not isinstance(pose.get('confidence'), (int, float))
                or not math.isfinite(float(pose['confidence']))
                or not isinstance(pose.get('sdf'), str)):
            raise ValueError('DiffDock returned an invalid ranked pose.')
        molecules = list(Chem.ForwardSDMolSupplier(io.BytesIO(pose['sdf'].encode()), removeHs=False))
        if len(molecules) != 1 or molecules[0] is None or molecules[0].GetNumConformers() != 1:
            raise ValueError('DiffDock pose is not one valid coordinate-bearing SDF record.')
        checked.append({'rank': index, 'confidence': float(pose['confidence']), 'sdf': pose['sdf']})
    return checked


def run_case(*, receptor_name: str, receptor_path: Path, receptor_reference: dict,
             ligand_name: str, ligand: str, args, runner=subprocess.run) -> tuple[dict, int]:
    name = safe_name(f'{receptor_name}-{ligand_name}')
    directory = args.output_dir.resolve() / 'cases' / name
    input_path = directory / 'input.json'
    payload = {'protein': receptor_reference, 'ligand': ligand, 'ligand_file_type': 'txt',
               'num_poses': args.num_poses, 'time_divisions': args.time_divisions,
               'steps': args.steps, 'random_seed': args.random_seed,
               'save_trajectory': False, 'skip_gen_conformer': False}
    immutable_input(input_path, payload)
    receipt, code = invoke(model='diffdock', tool='infer_diffdock_native', input_path=input_path,
                           directory=directory / 'run',
                           idempotency_key=f'{args.idempotency_key}-{name}',
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only,
                           runner=runner)
    base = {'case': name, 'receptor': receptor_name, 'receptor_path': str(receptor_path),
            'ligand_name': ligand_name, 'ligand': ligand,
            'operation_id': receipt.get('operation_id')}
    if code == 75:
        return {**base, 'state': receipt.get('state', 'pending')}, 75
    poses = validate_result(load(directory / 'run' / 'result.json'), ligand, args.num_poses)
    analysis = directory / 'analysis'; analysis.mkdir(parents=True, exist_ok=True, mode=0o700)
    pose_rows, links = [], {}
    for pose in poses:
        target = analysis / f"pose-rank-{pose['rank']}.sdf"
        artifact = publish_bytes(target, pose['sdf'].encode())
        link = workspace_urls(pose=target).get('pose')
        links[f"pose_rank_{pose['rank']}"] = link
        pose_rows.append({'rank': pose['rank'], 'confidence': pose['confidence'],
                          'path': str(target), 'artifact': artifact, 'workspace_url': link})
    operation = operation_metadata(directory / 'run' / 'operation.json')
    summary_path = analysis / 'summary.json'
    links['summary'] = workspace_urls(summary=summary_path).get('summary')
    summary = {**base, 'state': 'succeeded', 'model': 'diffdock',
               'timing': timing(operation), 'random_seed': args.random_seed,
               'num_poses': args.num_poses, 'poses': pose_rows, 'workspace_urls': links,
               'limitations': ['DiffDock confidence is a model score, not binding affinity or measured accuracy.',
                               'This campaign does not establish an experimental docking pose or biological effect.']}
    save(summary_path, summary)
    return summary, 0


def font(size: int, bold: bool = False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    try:
        return ImageFont.truetype(str(Path('/usr/share/fonts/truetype/dejavu') / name), size)
    except OSError:
        return ImageFont.load_default()


def write_gallery(cases: list[dict], path: Path) -> bool:
    succeeded = [case for case in cases if case.get('state') == 'succeeded']
    if not succeeded:
        return False
    width, height = 420, 285
    canvas = Image.new('RGB', (width * 3, height * math.ceil(len(succeeded) / 3)), '#f3f7f3')
    draw = ImageDraw.Draw(canvas)
    for index, case in enumerate(succeeded):
        x, y = (index % 3) * width, (index // 3) * height
        draw.rounded_rectangle((x + 8, y + 8, x + width - 8, y + height - 8), 12,
                               fill='white', outline='#70b692', width=2)
        molecule = Chem.MolFromSmiles(case['ligand'])
        picture = Draw.MolToImage(molecule, size=(360, 205)).convert('RGB')
        canvas.paste(picture, (x + 30, y + 36))
        score = max(pose['confidence'] for pose in case['poses'])
        draw.text((x + 18, y + 14), f"{case['receptor']} · {case['ligand_name']}",
                  fill='#173c2a', font=font(16, True))
        draw.text((x + 18, y + 248), f'Best DiffDock score {score:.5g}',
                  fill='#24523b', font=font(14))
    with staged_derived_view(path) as staged:
        canvas.save(staged.path, format='PNG', optimize=True)
    return True


def write_heatmap(cases: list[dict], receptors: list[str], ligands: list[str], path: Path) -> bool:
    values = {(case['receptor'], case['ligand_name']): max(p['confidence'] for p in case['poses'])
              for case in cases if case.get('state') == 'succeeded'}
    if not values:
        return False
    cell, left, top = 150, 180, 80
    image = Image.new('RGB', (left + cell * len(ligands) + 20, top + cell * len(receptors) + 20), 'white')
    draw = ImageDraw.Draw(image)
    numeric = list(values.values()); low, high = min(numeric), max(numeric)
    for column, ligand in enumerate(ligands):
        draw.text((left + column * cell + 8, 20), ligand[:18], fill='#173c2a', font=font(13, True))
    for row, receptor in enumerate(receptors):
        draw.text((12, top + row * cell + 55), receptor[:18], fill='#173c2a', font=font(14, True))
        for column, ligand in enumerate(ligands):
            box = (left + column * cell, top + row * cell,
                   left + (column + 1) * cell - 4, top + (row + 1) * cell - 4)
            value = values.get((receptor, ligand))
            if value is None:
                color, label = '#e4e8e5', 'unavailable'
            else:
                ratio = 0.5 if high == low else (value - low) / (high - low)
                color = (int(226 - 128 * ratio), int(240 - 35 * ratio), int(230 - 112 * ratio))
                label = f'{value:.5g}'
            draw.rectangle(box, fill=color, outline='#8ba497')
            draw.text((box[0] + 12, box[1] + 62), label, fill='#173c2a', font=font(14, True))
    with staged_derived_view(path) as staged:
        image.save(staged.path, format='PNG', optimize=True)
    return True


def write_csv(path: Path, cases: list[dict]) -> None:
    rows = []
    for case in cases:
        poses = case.get('poses') or [{}]
        for pose in poses:
            rows.append({'case': case['case'], 'receptor': case['receptor'],
                         'ligand_name': case['ligand_name'], 'smiles': case['ligand'],
                         'state': case.get('state'), 'operation_id': case.get('operation_id'),
                         'rank': pose.get('rank'), 'diffdock_score': pose.get('confidence'),
                         'pose_path': pose.get('path'), 'pose_url': pose.get('workspace_url')})
    with staged_derived_view(path) as staged, staged.path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def run(args, runner=subprocess.run) -> tuple[dict, int]:
    args.output_dir = args.output_dir.resolve(); args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    receptors = [(name, path.resolve()) for name, path in args.receptor]
    if len({name for name, _ in receptors}) != len(receptors):
        raise ValueError('Receptor names must be unique.')
    ligands = collect_ligands(args)
    references, upload_pending = {}, False
    for name, path in receptors:
        validate_receptor(path)
        reference, code = upload_source(source=path, model='diffdock', media_type='chemical/x-pdb',
                                        directory=args.output_dir / 'uploads' / name,
                                        idempotency_key=f'{args.idempotency_key}-receptor-{name}', runner=runner)
        if code == 75:
            upload_pending = True
        else:
            references[name] = reference
    if upload_pending:
        value = {'schema': 'nebius-scientific-ai/diffdock-campaign/v1', 'state': 'pending',
                 'details': 'At least one exact receptor upload is still pending; resume this command.',
                 'output_dir': str(args.output_dir)}
        save(args.output_dir / 'batch.json', value)
        return value, 75

    pairs = [(rn, rp, references[rn], ln, smiles) for rn, rp in receptors for ln, smiles in ligands]
    def execute(pair):
        try:
            return run_case(receptor_name=pair[0], receptor_path=pair[1], receptor_reference=pair[2],
                            ligand_name=pair[3], ligand=pair[4], args=args, runner=runner)
        except Exception as error:
            return ({'case': safe_name(f'{pair[0]}-{pair[3]}'), 'receptor': pair[0],
                     'receptor_path': str(pair[1]), 'ligand_name': pair[3], 'ligand': pair[4],
                     'state': 'failed', 'error_type': type(error).__name__,
                     'details': str(error)[:500]}, 1)
    with ThreadPoolExecutor(max_workers=min(args.max_workers, len(pairs))) as pool:
        outcomes = list(pool.map(execute, pairs))
    cases, codes = [item[0] for item in outcomes], [item[1] for item in outcomes]
    csv_path, gallery_path = args.output_dir / 'measurements.csv', args.output_dir / 'gallery.png'
    heatmap_path, report_path, summary_path = (args.output_dir / 'score-heatmap.png',
                                               args.output_dir / 'report.md', args.output_dir / 'batch.json')
    write_csv(csv_path, cases)
    has_gallery = write_gallery(cases, gallery_path)
    has_heatmap = write_heatmap(cases, [name for name, _ in receptors], [name for name, _ in ligands], heatmap_path)
    links = workspace_urls(summary=summary_path, csv=csv_path, report=report_path,
                           gallery=gallery_path if has_gallery else None,
                           heatmap=heatmap_path if has_heatmap else None)
    pending, failed = sum(code == 75 for code in codes), sum(code not in (0, 75) for code in codes)
    state = 'failed' if failed else ('pending' if pending else 'succeeded')
    summary = {'schema': 'nebius-scientific-ai/diffdock-campaign/v1', 'state': state,
               'receptor_count': len(receptors), 'ligand_count': len(ligands), 'run_count': len(cases),
               'succeeded_count': sum(code == 0 for code in codes), 'pending_count': pending,
               'failed_count': failed, 'cases': cases, 'workspace_urls': links,
               'score_semantics': 'DiffDock model confidence; not binding affinity or measured pose accuracy.'}
    lines = ['# DiffDock recording campaign', '',
             f"Runs: {len(cases)}; succeeded: {summary['succeeded_count']}; pending: {pending}; failed: {failed}.",
             '', f"- [Manifest]({links.get('summary', 'batch.json')})",
             f"- [Measurements CSV]({links.get('csv', 'measurements.csv')})"]
    if links.get('gallery'):
        lines.append(f"- [Pose gallery]({links['gallery']})")
    if links.get('heatmap'):
        lines.append(f"- [Target-by-candidate score heatmap]({links['heatmap']})")
    lines += ['', '| Receptor | Ligand | State | Operation | Best DiffDock score |',
              '|---|---|---|---|---:|']
    for case in cases:
        score = max((p['confidence'] for p in case.get('poses', [])), default='unavailable')
        lines.append(f"| {case['receptor']} | {case['ligand_name']} | {case['state']} | "
                     f"{case.get('operation_id') or 'unavailable'} | {score} |")
    lines += ['', 'Scores are model confidence values, not binding affinity, experimental accuracy, or efficacy.']
    with staged_derived_view(report_path) as staged:
        staged.path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    save(summary_path, summary)
    return summary, 1 if failed else (75 if pending else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receptor', action='append', type=named_file, required=True)
    parser.add_argument('--ligand', action='append', type=named_smiles)
    parser.add_argument('--ligand-file', action='append', type=named_file)
    parser.add_argument('--glob-ligands', action='append')
    parser.add_argument('--genmol-summary', type=Path)
    parser.add_argument('--top-candidates', type=int, default=5)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--num-poses', type=int, default=1)
    parser.add_argument('--time-divisions', type=int, default=20)
    parser.add_argument('--steps', type=int, default=18)
    parser.add_argument('--random-seed', type=int, default=1)
    parser.add_argument('--operation-wait-seconds', '--wait-seconds', dest='wait_seconds', type=int, default=600)
    parser.add_argument('--max-workers', type=int, default=3)
    parser.add_argument('--recover-only', action='store_true')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 120 or not 1 <= args.num_poses <= 4
            or not 3 <= args.time_divisions <= 20 or not 1 <= args.steps <= args.time_divisions
            or not 1 <= args.random_seed < 2**31 or not 1 <= args.top_candidates <= 5
            or not 0 <= args.wait_seconds <= 3600 or not 1 <= args.max_workers <= 8):
        parser.error('Invalid campaign key, pose/sampling settings, candidate count, wait or workers.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'), allow_nan=False)); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained campaign inputs and receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
