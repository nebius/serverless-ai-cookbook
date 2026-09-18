"""Bounded provider contract probe; not a scientist workflow or model score."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True)
    path = '/home/tux/.codex/skills/nebius-token-factory/scripts/nebius_token_factory.py'
    spec = importlib.util.spec_from_file_location('token_factory', path)
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    options = argparse.Namespace(base_url=None, include_latency=True)
    catalog = api.request_json('GET', '/models', args=options)['response']
    model = 'zai-org/GLM-5.3'
    if model not in {item['id'] for item in catalog['data']}:
        raise RuntimeError('Configured probe model is absent from the live catalog')
    base = {'model': model, 'max_tokens': 8192,
            'messages': [{'role': 'user', 'content': 'A previously authorized protein design operation is still running. Write a brief status update explaining that the job is not finished, that its existing operation ID can be used to resume, and that no new inference was submitted. Do not call tools or invent timing.'}]}

    def run(variant):
        payload = {**base, **({'reasoning_effort': 'low'} if variant == 'low' else {})}
        (args.output / f'{variant}-request.json').write_text(json.dumps(payload, indent=2) + '\n')
        try:
            result = api.request_json('POST', '/chat/completions', args=options, payload=payload)
            (args.output / f'{variant}-response.json').write_text(json.dumps(result, indent=2) + '\n')
            choice = result['response']['choices'][0]
            message = choice['message']
            return {'variant': variant, 'latency_ms': result['latency_ms'],
                    'finish_reason': choice.get('finish_reason'),
                    'content_chars': len(message.get('content') or ''),
                    'reasoning_chars': len(message.get('reasoning') or message.get('reasoning_content') or ''),
                    'usage': result['response'].get('usage')}
        except SystemExit as error:
            return {'variant': variant, 'error': str(error)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        summary = list(pool.map(run, ['default', 'low']))
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
