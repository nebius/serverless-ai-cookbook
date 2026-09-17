"""Replay public teaching transcripts through the current report helper.

Uses an existing candidate's credentials without printing them. Does not repeat
ASR, overwrite previous evidence or claim clinical validation.
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path

from acceptance import candidate_credentials


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--container', required=True)
    cli.add_argument('--source-evidence', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    values = candidate_credentials(args.container)
    helper = Path(__file__).parent.parent / 'skills/clinical-documentation/scripts/clinical_report.py'
    env = {**os.environ, 'FS2_API_KEY': values['SCIENTIFIC_MODELS_API_KEY'],
           'CLINICAL_REPORT_API_KEY': values['NEBIUS_API_KEY']}

    def one(case):
        name, language = case
        output = args.output / name
        command = [sys.executable, str(helper), '--transcript', str(args.source_evidence / name / 'transcript.txt'),
                   '--language', language, '--report-provider', 'https://api.tokenfactory.nebius.com/v1',
                   '--report-model', 'Qwen/Qwen3-235B-A22B-Instruct-2507', '--output', str(output)]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=1200)
        if result.returncode:
            raise RuntimeError(f'{name}: report helper failed; inspect saved receipts')
        document = json.loads((output / 'document.json').read_text())
        statements = [fact['statement'] for fact in document['facts']]
        if language == 'de':
            assert any('appetit' in text.lower() or 'hunger' in text.lower() for text in statements), 'Explicit appetite history was lost'
        else:
            assert not any('dioralyte' in text.lower() for text in statements), 'Unclear medication was silently normalized'
        receipt = {'case': name, 'status': 'completed', 'facts': len(statements),
                   'withheld': len(document['rejected']), 'asr_repeated': False, 'clinical_validation': False}
        print(json.dumps(receipt), flush=True)
        return receipt

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one, [('hhu-herzrasen', 'de'), ('day1_consultation01_conversation', 'en')]))
    (args.output / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
