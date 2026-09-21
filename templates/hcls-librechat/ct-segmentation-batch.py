#!/usr/bin/env python3
"""Run a deterministic, resumable NV-Segment-CT campaign.

Each case is delegated to the receipt-safe single-volume pipeline.  A repeated
command resumes the same uploads and model operations, records every terminal
case, and publishes one machine-readable summary, report, and heatmap.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from scientific_receipts import load, save, staged_output
from recording_pipeline import workspace_urls


def parse_case(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition('=')
    if not separator or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}', name):
        raise argparse.ArgumentTypeError('Case must be NAME=/absolute/source.nii.gz.')
    path = Path(raw_path)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError('Case source must be an absolute path.')
    return name, path


def parse_terminal_json(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {'state': 'error', 'details': 'The case command returned no structured result.'}


def run_case(*, name: str, source: Path, output_dir: Path, labels: list[int],
             idempotency_key: str, wait_seconds: int, recover_only: bool,
             runner=subprocess.run) -> tuple[dict, int]:
    case_dir = output_dir / 'cases' / name
    command = [
        sys.executable, str(Path(__file__).with_name('ct-segmentation.py')),
        '--source', str(source), '--output-dir', str(case_dir),
        '--idempotency-key', f'{idempotency_key}-{name}',
        '--wait-seconds', str(wait_seconds),
    ]
    for label in labels:
        command.extend(['--label-prompt', str(label)])
    if recover_only:
        command.append('--recover-only')
    completed = runner(command, capture_output=True, text=True, check=False)
    result = parse_terminal_json(completed.stdout)
    result['case'] = name
    result['source'] = str(source)
    result['case_output_dir'] = str(case_dir)
    return result, completed.returncode


def write_heatmap(cases: list[dict], destination: Path) -> None:
    labels = sorted({str(label) for case in cases
                     for label in (case.get('label_voxel_counts') or {})})
    if not labels:
        raise ValueError('No succeeded case contains label voxel counts.')
    matrix = np.asarray([
        [int((case.get('label_voxel_counts') or {}).get(label, 0)) for label in labels]
        for case in cases
    ], dtype=np.int64)
    figure, axis = plt.subplots(figsize=(max(6, len(labels) * 1.2), max(3.5, len(cases) * 0.8)))
    image = axis.imshow(matrix, cmap='viridis', aspect='auto')
    axis.set_xticks(range(len(labels)), [f'Label {label}' for label in labels])
    axis.set_yticks(range(len(cases)), [case['case'] for case in cases])
    axis.set_xlabel('Predicted label')
    axis.set_ylabel('Case')
    axis.set_title('NV-Segment-CT case-by-label voxel counts')
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(column, row, f'{matrix[row, column]:,}', ha='center', va='center',
                      color='white' if matrix[row, column] > matrix.max() * 0.45 else 'black')
    figure.colorbar(image, ax=axis, label='Voxel count')
    figure.tight_layout()
    with staged_output(destination) as staged:
        figure.savefig(staged.path, dpi=160, format='png')
    plt.close(figure)


def write_report(*, cases: list[dict], destination: Path, heatmap_url: str,
                 summary_url: str) -> None:
    lines = [
        '# NV-Segment-CT batch report', '',
        'Research use only. These segmentation outputs are not diagnoses.', '',
        f'- Batch summary: [JSON]({summary_url})',
    ]
    if heatmap_url:
        lines.append(f'- Case-by-label heatmap: [PNG]({heatmap_url})')
    lines.extend([
        '', '| Case | State | Operation | Model seconds | Mask | Preview |',
        '|---|---|---|---:|---|---|',
    ])
    for case in cases:
        urls = case.get('workspace_urls') or {}
        mask = f"[NIfTI]({urls['segmentation']})" if urls.get('segmentation') else '—'
        preview_url = urls.get('overlay') or urls.get('rotation')
        preview = f'[view]({preview_url})' if preview_url else '—'
        seconds = case.get('model_seconds')
        seconds_text = f'{seconds:.3f}' if isinstance(seconds, (int, float)) else '—'
        lines.append(
            f"| {case['case']} | {case.get('state', 'unknown')} | "
            f"{case.get('operation_id') or '—'} | {seconds_text} | {mask} | {preview} |"
        )
    with staged_output(destination) as staged:
        staged.path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run(args, runner=subprocess.run) -> tuple[dict, int]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    names = [name for name, _ in args.case]
    if len(names) != len(set(names)):
        raise ValueError('Case names must be unique.')

    cases = []
    return_codes = []
    for name, source in args.case:
        resolved = source.resolve()
        if not resolved.is_file():
            cases.append({'case': name, 'source': str(resolved), 'state': 'failed',
                          'error_type': 'SourceNotFound',
                          'details': 'The requested source file does not exist.'})
            return_codes.append(1)
            continue
        result, return_code = run_case(
            name=name, source=resolved, output_dir=output_dir, labels=args.label_prompt,
            idempotency_key=args.idempotency_key, wait_seconds=args.wait_seconds,
            recover_only=args.recover_only, runner=runner,
        )
        cases.append(result)
        return_codes.append(return_code)

    succeeded = [case for case in cases if case.get('state') == 'succeeded']
    heatmap_path = output_dir / 'case-label-voxel-heatmap.png'
    summary_path = output_dir / 'batch.json'
    report_path = output_dir / 'report.md'
    if succeeded:
        write_heatmap(succeeded, heatmap_path)

    links = workspace_urls(
        summary=summary_path,
        report=report_path,
        heatmap=heatmap_path if heatmap_path.is_file() else None,
    )
    pending = any(code == 75 for code in return_codes)
    failed = any(code not in (0, 75) for code in return_codes)
    state = 'failed' if failed else ('pending' if pending else 'succeeded')
    summary = {
        'state': state,
        'model': 'nv-segment-ct',
        'labels': args.label_prompt,
        'case_count': len(cases),
        'succeeded_count': len(succeeded),
        'pending_count': sum(code == 75 for code in return_codes),
        'failed_count': sum(code not in (0, 75) for code in return_codes),
        'cases': cases,
        'workspace_urls': links,
        'research_use_only': True,
    }
    save(summary_path, summary)
    write_report(cases=cases, destination=report_path,
                 heatmap_url=links.get('heatmap', ''), summary_url=links.get('summary', ''))
    return summary, 1 if failed else (75 if pending else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', type=parse_case, required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--label-prompt', required=True, type=int, action='append')
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 120 or args.wait_seconds < 0:
        parser.error('Use an 8–120 character idempotency key and a nonnegative wait.')
    try:
        value, exit_code = run(args)
        print(json.dumps(value, separators=(',', ':')))
        raise SystemExit(exit_code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': str(error), 'output_dir': str(args.output_dir)},
                         separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
