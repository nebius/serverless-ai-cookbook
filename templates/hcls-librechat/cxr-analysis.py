#!/usr/bin/env python3
"""Run one durable NV-Reason-CXR image workflow without image bytes in chat."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from scientific_receipts import load, save


ARTIFACT_FIELDS = ('artifact_id', 'sha256', 'size_bytes', 'media_type', 'compression')
DEFAULT_QUESTION = (
    'Describe the visible chest-radiograph findings in a concise, structured, research-only summary. '
    'Separate observations, uncertainty, and limitations. Do not diagnose, prescribe, or invent localization.'
)


def file_identity(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


def detected_media_type(path):
    header = path.read_bytes()[:16]
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'image/webp'
    raise ValueError('Source is not a signature-verified PNG, JPEG or WebP image.')


def verified_artifact_reference(path, source, media_type):
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict) or any(field not in value for field in ARTIFACT_FIELDS):
        raise ValueError('Finalized artifact file is missing required fields.')
    reference = {field: value[field] for field in ARTIFACT_FIELDS}
    identity = file_identity(source)
    if reference['sha256'] != identity['sha256'] or reference['size_bytes'] != identity['size_bytes']:
        raise ValueError('Finalized artifact identity differs from the source image.')
    if reference['media_type'] != media_type or reference['compression'] != 'none':
        raise ValueError('Finalized artifact media type or compression differs from the source contract.')
    return reference


def execute(command, runner=subprocess.run):
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 75):
        raise RuntimeError(f'Pipeline stage failed with exit code {completed.returncode}; inspect its saved receipt.')
    return completed


def assistant_content(result):
    choices = result.get('choices') if isinstance(result, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError('Completed CXR result has no OpenAI-compatible choice.')
    message = choices[0].get('message')
    if not isinstance(message, dict):
        raise ValueError('Completed CXR result has no assistant message.')
    for field in ('content', 'reasoning_content', 'reasoning'):
        value = message.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip(), field
    raise ValueError('Completed CXR assistant message is empty.')


def visible_answer(content):
    """Return the model's answer channel without publishing hidden reasoning."""
    match = re.search(r'<answer>\s*(.*?)\s*</answer>', content, flags=re.IGNORECASE | re.DOTALL)
    if match:
        answer = match.group(1)
    else:
        answer = re.sub(r'<think>.*?</think>', '', content, flags=re.IGNORECASE | re.DOTALL)
    answer = ' '.join(answer.split())
    if not answer:
        raise ValueError('Completed CXR response has no visible answer content.')
    return answer


def run(args, runner=subprocess.run):
    source = args.source.resolve()
    if not source.is_file():
        raise ValueError('Source chest radiograph does not exist.')
    media_type = detected_media_type(source)
    output_dir = args.output_dir.resolve()
    upload_dir = output_dir / 'upload'
    run_dir = output_dir / 'run'
    input_path = output_dir / 'input.json'
    summary_path = output_dir / 'summary.json'
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    python = Path(sys.executable)
    helper_dir = Path(__file__).resolve().parent

    upload = execute([
        str(python), str(helper_dir / 'upload-artifact.py'), '--model', args.model,
        '--file', str(source), '--media-type', media_type, '--output-dir', str(upload_dir),
        '--idempotency-key', args.idempotency_key + '-source',
    ], runner)
    if upload.returncode == 75:
        return {'state': 'upload_pending', 'output_dir': str(output_dir)}, 75
    artifact = verified_artifact_reference(upload_dir / 'artifact.json', source, media_type)
    payload = {
        'messages': [
            {'role': 'system', 'content': 'Research image review only; never present output as diagnosis or treatment advice.'},
            {'role': 'user', 'content': [
                {'type': 'text', 'text': args.question},
                {'type': 'image_url', 'image_url': {'url': artifact, 'detail': args.detail}},
            ]},
        ],
        'max_completion_tokens': args.max_completion_tokens,
        'temperature': 0,
    }
    existing = load(input_path)
    if existing is not None and existing != payload:
        raise ValueError('Saved CXR input belongs to different image bytes or settings; use a new output directory.')
    save(input_path, payload)

    command = [
        str(python), str(helper_dir / 'invoke-native.py'), '--protocol', 'openai-chat',
        '--model', args.model, '--tool', args.tool, '--input', str(input_path),
        '--output-dir', str(run_dir), '--idempotency-key', args.idempotency_key,
        '--wait-seconds', str(args.wait_seconds),
    ]
    if args.recover_only:
        command.append('--recover-only')
    native = execute(command, runner)
    receipt = load(run_dir / 'receipt.json') or {}
    operation_id = receipt.get('operation_id')
    if native.returncode == 75:
        return {'state': receipt.get('state', 'pending'), 'operation_id': operation_id,
                'output_dir': str(output_dir)}, 75

    result = load(run_dir / 'result.json')
    content, content_field = assistant_content(result)
    answer = visible_answer(content)
    summary = {
        'schema': 'nebius-scientific-ai/cxr-analysis/v1',
        'state': 'succeeded', 'operation_id': operation_id,
        'model': result.get('model', args.model), 'source': {**file_identity(source),
            'path': str(source), 'media_type': media_type},
        'assistant': {'answer': answer, 'source_field': content_field,
                      'raw_content_sha256': hashlib.sha256(content.encode()).hexdigest(),
                      'raw_content_chars': len(content)},
        'usage': result.get('usage'), 'finish_reason': result.get('choices', [{}])[0].get('finish_reason'),
        'limitations': ['Research use only; not a diagnosis or radiology report.',
                        'No localization is claimed unless explicitly returned by the model.'],
    }
    save(summary_path, summary)
    return {**summary, 'result_path': str(run_dir / 'result.json'),
            'summary_path': str(summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--question', default=DEFAULT_QUESTION)
    parser.add_argument('--detail', choices=('auto', 'low', 'high'), default='high')
    parser.add_argument('--max-completion-tokens', type=int, default=768)
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='nv-reason-cxr-3b')
    parser.add_argument('--tool', default='analyze_image_openai_chat')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or args.wait_seconds < 0
            or not 1 <= args.max_completion_tokens <= 4096):
        parser.error('Use an 8–193 character key, nonnegative wait, and 1–4096 completion tokens.')
    try:
        value, exit_code = run(args)
        print(json.dumps(value, separators=(',', ':')))
        raise SystemExit(exit_code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect upload and run receipts; do not resubmit elsewhere.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
