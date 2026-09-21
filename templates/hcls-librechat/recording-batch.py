#!/usr/bin/env python3
"""Run deterministic, resumable multi-file campaigns for recording workflows.

The command delegates every case to an already-qualified single-case helper.
It never implements another model path. Repeating the same invocation resumes
the same child receipts and publishes one manifest, CSV, report, and gallery.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import glob
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image, ImageDraw

from scientific_receipts import save, staged_output
from recording_pipeline import workspace_urls


WORKFLOWS = {
    'cxr': {'helper': 'cxr-analysis.py', 'visual': 'source_path'},
    'proteinmpnn': {'helper': 'proteinmpnn-design.py', 'visual': 'summary_image'},
    'msa': {'helper': 'msa-search.py', 'visual': 'summary_image'},
    'sam2-image': {'helper': 'sam2-segment.py', 'visual': 'overlay_path'},
    'scvi': {'helper': 'scvi-integrate.py', 'visual': 'before_after_path'},
    'cosmos-transfer': {'helper': 'cosmos-transfer.py', 'visual': 'generated_path'},
    'speech': {'helper': 'speech-analysis.py', 'visual': 'timeline_path'},
}

METRIC_PATHS = {
    'cxr': ('assistant.answer', 'finish_reason'),
    'proteinmpnn': ('sequence_length', 'num_sequences', 'timing.elapsed_seconds'),
    'msa': ('alignment', 'timing.elapsed_seconds'),
    'sam2-image': ('metrics', 'timing.elapsed_seconds'),
    'scvi': ('input.cells', 'input.genes', 'embedding', 'runtime.timing.elapsed_seconds'),
    'cosmos-transfer': ('input.width', 'input.height', 'input.frame_count',
                        'output.width', 'output.height', 'output.frame_count',
                        'timing.elapsed_seconds'),
    'speech': ('input.audio_seconds', 'transcription.final_segment_count',
               'transcription.processing_seconds', 'diarization.processing_seconds',
               'timeline_metrics'),
}


def safe_name(value: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9_-]+', '-', value).strip('-_').lower()
    if not slug:
        raise ValueError('A case name could not be derived from the source path.')
    return slug[:48]


def parse_case(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition('=')
    if not separator or safe_name(name) != name:
        raise argparse.ArgumentTypeError('Case must be a lowercase safe-name=/absolute/file.')
    path = Path(raw_path)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError('Case source must be an absolute path.')
    return name, path


def discovered_name(path: Path) -> str:
    stem = path.name
    for suffix in ('.nii.gz', '.tar.zst'):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    else:
        stem = path.stem
    return safe_name(f'{path.parent.name}-{stem}')


def sources(args) -> list[tuple[str, Path]]:
    result = [(name, path.resolve()) for name, path in (args.case or [])]
    for pattern in args.glob or []:
        if not pattern.startswith('/workspace/'):
            raise ValueError('Discovery globs must stay below /workspace.')
        result.extend((discovered_name(path), path.resolve())
                      for path in sorted(Path(item) for item in glob.glob(pattern, recursive=True))
                      if path.is_file())
    if not result:
        raise ValueError('No source files matched the campaign.')
    seen = {}
    unique = []
    for name, path in result:
        identity = str(path)
        if identity in seen:
            continue
        candidate = name
        if any(existing == candidate for existing, _ in unique):
            candidate = safe_name(candidate[:38] + '-' + hashlib.sha256(identity.encode()).hexdigest()[:8])
        unique.append((candidate, path))
        seen[identity] = True
    return unique


def parse_terminal_json(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {'state': 'error', 'error_type': 'MissingStructuredResult',
            'details': 'The installed single-case helper returned no JSON result.'}


def child_arguments(workflow: str, args, source: Path, seed: int | None) -> list[str]:
    if workflow == 'cxr':
        return ['--source', str(source), '--max-completion-tokens', str(args.max_completion_tokens)]
    if workflow == 'proteinmpnn':
        return ['--backbone', str(source), '--num-sequences', str(args.num_sequences),
                '--seed', str(args.seed[0] if args.seed else 42),
                '--temperature', str(args.temperature)]
    if workflow == 'msa':
        return ['--query', str(source), '--max-sequences', str(args.max_sequences)]
    if workflow == 'sam2-image':
        return ['--source', str(source), '--mode', 'automatic-image',
                '--max-masks', str(args.max_masks)]
    if workflow == 'scvi':
        command = ['--source', str(source), '--batch-key', args.batch_key,
                   '--method', args.method, '--seed', str(args.seed[0] if args.seed else 42),
                   '--max-epochs', str(args.max_epochs), '--n-latent', str(args.n_latent)]
        if args.labels_key:
            command.extend(['--labels-key', args.labels_key,
                            '--unlabeled-category', args.unlabeled_category])
        return command
    if workflow == 'cosmos-transfer':
        return ['--source', str(source), '--prompt', args.prompt,
                '--negative-prompt', args.negative_prompt, '--seed', str(seed),
                '--num-steps', str(args.num_steps), '--guidance', str(args.guidance),
                '--resolution', str(args.resolution), '--control-weight', str(args.control_weight)]
    if workflow == 'speech':
        return ['--source', str(source)]
    raise ValueError(f'Unsupported workflow {workflow}.')


def campaign_cases(args) -> list[tuple[str, Path, int | None]]:
    base = sources(args)
    if args.workflow != 'cosmos-transfer':
        return [(name, path, None) for name, path in base]
    seeds = args.seed or [11]
    return [(safe_name(f'{name}-seed-{seed}'), path, seed)
            for name, path in base for seed in seeds]


def run_case(*, workflow: str, name: str, source: Path, seed: int | None,
             output_dir: Path, args, runner=subprocess.run) -> tuple[dict, int]:
    case_dir = output_dir / 'cases' / name
    key = f'{args.idempotency_key}-{name}'
    command = [
        sys.executable, str(Path(__file__).with_name(WORKFLOWS[workflow]['helper'])),
        *child_arguments(workflow, args, source, seed),
        '--output-dir', str(case_dir), '--idempotency-key', key,
        '--wait-seconds', str(args.wait_seconds),
    ]
    if args.recover_only:
        command.append('--recover-only')
    completed = runner(command, capture_output=True, text=True, check=False)
    result = parse_terminal_json(completed.stdout)
    result.update(case=name, source_file=str(source), case_output_dir=str(case_dir))
    if seed is not None:
        result['campaign_seed'] = seed
    return result, completed.returncode


def nested(value: dict, dotted: str):
    current = value
    for part in dotted.split('.'):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def scalar(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(',', ':'))
    return value


def table_rows(workflow: str, cases: list[dict]) -> tuple[list[str], list[dict]]:
    metrics = METRIC_PATHS[workflow]
    fields = ['case', 'source', 'state', 'operation_id', 'model', *metrics, 'artifacts']
    rows = []
    for case in cases:
        row = {
            'case': case['case'], 'source': case.get('source_file', ''),
            'state': case.get('state', 'unknown'), 'operation_id': case.get('operation_id', ''),
            'model': case.get('model', ''),
            'artifacts': scalar(case.get('workspace_urls', {})),
        }
        row.update({field: scalar(nested(case, field)) for field in metrics})
        rows.append(row)
    return fields, rows


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with staged_output(path) as staged, staged.path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def image_for_case(case: dict, visual_field: str, thumb_dir: Path) -> Path | None:
    value = case.get(visual_field)
    if not isinstance(value, str):
        return None
    source = Path(value)
    if not source.is_file():
        return None
    if source.suffix.lower() not in {'.mp4', '.webm', '.mov'}:
        return source
    thumb_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = thumb_dir / f"{case['case']}.png"
    completed = subprocess.run(
        ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source), '-frames:v', '1', str(target)],
        capture_output=True, check=False,
    )
    return target if completed.returncode == 0 and target.is_file() else None


def write_gallery(workflow: str, cases: list[dict], destination: Path) -> bool:
    visual = WORKFLOWS[workflow]['visual']
    images = [(case, image_for_case(case, visual, destination.parent / '.thumbnails'))
              for case in cases if case.get('state') == 'succeeded']
    images = [(case, path) for case, path in images if path is not None]
    if not images:
        return False
    tile_width, tile_height, caption_height, columns = 640, 400, 54, 2
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * tile_width, rows * tile_height), 'white')
    draw = ImageDraw.Draw(canvas)
    for index, (case, path) in enumerate(images):
        with Image.open(path) as source:
            picture = source.convert('RGB')
            picture.thumbnail((tile_width - 24, tile_height - caption_height - 18))
            left = (index % columns) * tile_width + (tile_width - picture.width) // 2
            top = (index // columns) * tile_height + caption_height
            canvas.paste(picture, (left, top))
        draw.text(((index % columns) * tile_width + 12,
                   (index // columns) * tile_height + 14),
                  f"{case['case']} · {case.get('state', 'unknown')}", fill='black')
    with staged_output(destination) as staged:
        canvas.save(staged.path, format='PNG', optimize=True)
    return True


def write_report(*, workflow: str, destination: Path, links: dict,
                 fields: list[str], rows: list[dict], cases: list[dict]) -> None:
    visible_fields = [field for field in fields if field != 'artifacts']
    summary_link = links.get('summary', 'batch.json')
    csv_link = links.get('csv', 'measurements.csv')
    lines = [f'# {workflow} recording campaign', '',
             f'- Machine-readable manifest: [JSON]({summary_link})',
             f'- Downloadable measurements: [CSV]({csv_link})']
    if links.get('gallery'):
        lines.append(f'- Visual gallery: [PNG]({links["gallery"]})')
    lines.extend(['', '| ' + ' | '.join(visible_fields) + ' |',
                  '|' + '|'.join('---' for _ in visible_fields) + '|'])
    for row in rows:
        lines.append('| ' + ' | '.join(str(row.get(field, '')).replace('|', '\\|')[:500]
                                        for field in visible_fields) + ' |')
    lines.extend(['', '## Exact retained artifacts', ''])
    for case in cases:
        links_for_case = case.get('workspace_urls') or {}
        lines.append(f"### {case['case']} — {case.get('state', 'unknown')}")
        if links_for_case:
            lines.extend(f'- {name}: [{name}]({url})' for name, url in links_for_case.items())
        else:
            lines.append('- No terminal artifact links were returned.')
        lines.append('')
    with staged_output(destination) as staged:
        staged.path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run(args, runner=subprocess.run) -> tuple[dict, int]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    expanded = campaign_cases(args)

    def execute_case(item):
        name, source, seed = item
        if not source.is_file():
            return ({'case': name, 'source_file': str(source), 'state': 'failed',
                     'error_type': 'SourceNotFound',
                     'details': 'The requested source file does not exist.'}, 1)
        return run_case(workflow=args.workflow, name=name, source=source, seed=seed,
                        output_dir=output_dir, args=args, runner=runner)

    with ThreadPoolExecutor(max_workers=min(args.max_workers, len(expanded))) as pool:
        outcomes = list(pool.map(execute_case, expanded))
    cases = [result for result, _ in outcomes]
    codes = [code for _, code in outcomes]

    fields, rows = table_rows(args.workflow, cases)
    csv_path, gallery_path = output_dir / 'measurements.csv', output_dir / 'gallery.png'
    report_path, summary_path = output_dir / 'report.md', output_dir / 'batch.json'
    write_csv(csv_path, fields, rows)
    has_gallery = write_gallery(args.workflow, cases, gallery_path)
    links = workspace_urls(summary=summary_path, csv=csv_path, report=report_path,
                           gallery=gallery_path if has_gallery else None)
    pending = sum(code == 75 for code in codes)
    failed = sum(code not in (0, 75) for code in codes)
    state = 'failed' if failed else ('pending' if pending else 'succeeded')
    summary = {
        'schema': 'nebius-scientific-ai/recording-campaign/v1',
        'state': state, 'workflow': args.workflow, 'case_count': len(cases),
        'succeeded_count': sum(code == 0 for code in codes),
        'pending_count': pending, 'failed_count': failed,
        'cases': cases, 'workspace_urls': links,
    }
    save(summary_path, summary)
    write_report(workflow=args.workflow, destination=report_path, links=links,
                 fields=fields, rows=rows, cases=cases)
    return summary, 1 if failed else (75 if pending else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workflow', required=True, choices=sorted(WORKFLOWS))
    parser.add_argument('--case', action='append', type=parse_case)
    parser.add_argument('--glob', action='append')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=600)
    parser.add_argument('--max-workers', type=int, default=1)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--seed', type=int, action='append')
    parser.add_argument('--num-sequences', type=int, default=8)
    parser.add_argument('--temperature', type=float, default=0.1)
    parser.add_argument('--max-sequences', type=int, default=500)
    parser.add_argument('--max-masks', type=int, default=32)
    parser.add_argument('--batch-key', default='batch')
    parser.add_argument('--method', choices=('scvi', 'scanvi'), default='scvi')
    parser.add_argument('--labels-key')
    parser.add_argument('--unlabeled-category', default='Unknown')
    parser.add_argument('--max-epochs', type=int, default=20)
    parser.add_argument('--n-latent', type=int, default=10)
    parser.add_argument('--max-completion-tokens', type=int, default=768)
    parser.add_argument('--prompt', default='')
    parser.add_argument('--negative-prompt', default='')
    parser.add_argument('--num-steps', type=int, default=35)
    parser.add_argument('--guidance', type=int, default=7)
    parser.add_argument('--resolution', type=int, choices=(256, 480, 512, 720), default=720)
    parser.add_argument('--control-weight', type=float, default=1.0)
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 120 or args.wait_seconds < 0
            or not 1 <= args.max_workers <= 8):
        parser.error('Use an 8–120 character key, nonnegative wait, and 1–8 workers.')
    if args.workflow == 'cosmos-transfer' and (not args.prompt or not args.seed):
        parser.error('Cosmos campaigns require a prompt and at least one seed.')
    if args.method == 'scanvi' and not args.labels_key:
        parser.error('scANVI requires --labels-key and --unlabeled-category.')
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
