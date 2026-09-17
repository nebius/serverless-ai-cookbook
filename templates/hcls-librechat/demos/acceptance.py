"""Exercise real demo APIs on an isolated candidate; never print credentials."""
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx


def candidate_credentials(name):
    data = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
    return dict(value.split('=', 1) for value in data['Config']['Env'])


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--url', default='http://127.0.0.1:13117')
    cli.add_argument('--container', default='scientific-demos-candidate-20260917')
    cli.add_argument('--audio', action='store_true')
    cli.add_argument('--browser-state', type=Path)
    cli.add_argument('--evidence', type=Path, help='Save test receipts and generated files; use only public/synthetic fixtures.')
    args = cli.parse_args()
    values = candidate_credentials(args.container)
    with httpx.Client(base_url=args.url, timeout=90) as client:
        response = client.post('/api/auth/login', json={'email': values['SEED_DEFAULT_USER_EMAIL'],
                                                       'password': values['SEED_DEFAULT_USER_PASSWORD']})
        response.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + response.json()['token']
        if args.browser_state:
            args.browser_state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            state = {'cookies': [{'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain,
                                   'path': cookie.path, 'httpOnly': 'HttpOnly' in cookie._rest,
                                   'secure': cookie.secure, 'sameSite': 'Lax', 'expires': cookie.expires or -1}
                                  for cookie in client.cookies.jar], 'origins': []}
            args.browser_state.write_text(json.dumps(state))
            args.browser_state.chmod(0o600)
            print('Protected browser session state saved', flush=True)
        response = client.put('/api/scientific-demos/settings', json={'api_key': values['SCIENTIFIC_MODELS_API_KEY']})
        response.raise_for_status()
        print('Per-user demo key: saved; provider credentials remain server-side', flush=True)
        response = client.get('/api/scientific-demos/workshop/catalog')
        response.raise_for_status()
        catalog = response.json()
        print(json.dumps({'judge': catalog['catalog']['judge_model'], 'clinicians': [m['id'] for m in catalog['catalog']['data'] if m['clinician_eligible']], 'limits': catalog['limits']}), flush=True)
        cases = [('transcript', 'de', Path(__file__).parent / 'fixture.txt')]
        if args.audio:
            assets = Path('/home/tux/demo-assets/medical-speech-en-de-20260916/ready')
            cases += [('audio', 'de', assets / 'de/hhu-herzrasen.wav'),
                      ('audio', 'en', assets / 'en/day1_consultation01_conversation.wav')]

        def one(case):
            kind, language, source = case
            raw = source.read_bytes()
            idem = 'librechat-acceptance-v1-' + hashlib.sha256(raw + language.encode()).hexdigest()[:24]
            start = time.monotonic()
            response = client.post('/api/scientific-demos/clinical', data={'kind': kind, 'language': language, 'idempotency_key': idem},
                                   files={'file': (source.name, raw)})
            response.raise_for_status()
            job = response.json()
            reused = job['status'] == 'completed'
            while job['status'] in {'prepared', 'running', 'queued'} and time.monotonic() - start < 1200:
                time.sleep(3)
                response = client.get('/api/scientific-demos/clinical/' + job['id'])
                response.raise_for_status()
                job = response.json()
            workflow_seconds = None
            if job.get('finished_at'):
                workflow_seconds = (datetime.fromisoformat(job['finished_at'].replace('Z', '+00:00')) -
                                    datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))).total_seconds()
            row = {'case': source.name, 'language': language, 'job': job['id'], 'status': job['status'],
                   'request_wall_seconds': round(time.monotonic() - start, 2), 'reused_completed_job': reused,
                   'original_workflow_seconds_including_queue': workflow_seconds,
                   'files': job['files'], 'clinical_validation': False}
            if job['status'] != 'completed':
                print(json.dumps(row), flush=True)
                raise RuntimeError('Workflow did not complete; inspect its saved evidence.')
            for filename in ['transcript.txt', 'report.md', 'review.md', 'follow-up.md', 'document.json', 'run.json']:
                response = client.get(f"/api/scientific-demos/clinical/{job['id']}/files/{filename}")
                response.raise_for_status()
                assert response.content
                if filename == 'document.json':
                    document = response.json()
                    row.update(facts=len(document['facts']), withheld=len(document['rejected']))
                if args.evidence:
                    folder = args.evidence / source.stem
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / filename).write_bytes(response.content)
            replay = client.post('/api/scientific-demos/clinical', data={'kind': kind, 'language': language, 'idempotency_key': idem}, files={'file': (source.name, raw)})
            replay.raise_for_status()
            assert replay.json()['id'] == job['id']
            assert job['status'] == 'completed', row
            row['same_request_reused'] = True
            print(json.dumps(row), flush=True)
            return row

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(one, cases))
        print(json.dumps({'completed': len(results), 'clinical_validation': False}), flush=True)
        if args.evidence:
            (args.evidence / 'summary.json').write_text(json.dumps({'candidate': args.container,
                'base_url': args.url, 'results': results, 'clinical_validation': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
