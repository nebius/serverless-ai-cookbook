#!/usr/bin/env python3
"""Run one OpenFold3 Preview2 fold and materialize its verified CIF and scores."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess

from recording_pipeline import (immutable_input, invoke, operation_metadata, publish_bytes, timing,
                                unwrap, workspace_urls)
from scientific_receipts import load, save


SEQUENCE_RE = re.compile(r'^[ACDEFGHIKLMNPQRSTVWY]+$')
SCORE_FIELDS = ('confidence_score', 'complex_plddt_score', 'complex_pde_score', 'ptm_score', 'iptm_score')


def read_fasta(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise ValueError('OpenFold3 FASTA does not exist.')
    records, header, chunks = [], None, []
    for raw in path.read_text().splitlines():
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
    if len(records) != 1 or not 1 <= len(records[0][1]) <= 4096 or not SEQUENCE_RE.fullmatch(records[0][1]):
        raise ValueError('OpenFold3 input must contain exactly one canonical protein record.')
    return records[0]


def validate_result(value: dict, request_id: str, input_id: str) -> dict:
    result = unwrap(value)
    if result.get('request_id') != request_id:
        raise ValueError('OpenFold3 result request_id differs from the submitted request.')
    outputs = result.get('outputs')
    if not isinstance(outputs, list) or len(outputs) != 1 or outputs[0].get('input_id') != input_id:
        raise ValueError('OpenFold3 result has the wrong output identity or cardinality.')
    structures = outputs[0].get('structures_with_scores')
    if not isinstance(structures, list) or len(structures) != 1:
        raise ValueError('OpenFold3 result must contain exactly one structure sample.')
    structure = structures[0]
    if structure.get('format') != 'cif' or not isinstance(structure.get('structure'), str):
        raise ValueError('OpenFold3 result has no mmCIF structure.')
    if len(structure['structure']) < 80 or ('_atom_site.' not in structure['structure']
                                            and 'ATOM ' not in structure['structure']):
        raise ValueError('OpenFold3 returned text does not look like mmCIF.')
    scores = {}
    for field in SCORE_FIELDS:
        value = structure.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f'OpenFold3 result is missing finite {field}.')
        scores[field] = float(value)
    metrics = outputs[0].get('runtime_metrics')
    if not isinstance(metrics, dict):
        raise ValueError('OpenFold3 result has no runtime metrics.')
    return {'structure': structure, 'scores': scores, 'runtime_metrics': metrics}


def run(args, runner=subprocess.run):
    header, sequence = read_fasta(args.fasta.resolve())
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir, analysis = output / 'run', output / 'analysis'
    input_path = output / 'input.json'
    payload = {'request_id': args.request_id, 'inputs': [{
        'input_id': args.input_id, 'output_format': 'cif',
        'molecules': [{'type': 'protein', 'id': args.chain_id, 'sequence': sequence}],
    }]}
    immutable_input(input_path, payload)
    receipt, code = invoke(model=args.model, tool=args.tool, input_path=input_path,
                           directory=run_dir, idempotency_key=args.idempotency_key,
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {**receipt, 'output_dir': str(output)}, code
    parsed = validate_result(load(run_dir / 'result.json'), args.request_id, args.input_id)
    analysis.mkdir(parents=True, exist_ok=True, mode=0o700)
    structure = parsed['structure']
    cif_receipt = publish_bytes(analysis / 'structure.cif', structure['structure'].encode())
    operation = operation_metadata(run_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/openfold3-fold/v1', 'state': 'succeeded',
        'model': args.model, 'model_name': structure.get('source'),
        'operation_id': operation.get('id') or receipt.get('operation_id'),
        'input': {'path': str(args.fasta.resolve()), 'header': header,
                  'sequence_length': len(sequence), 'chain_id': args.chain_id},
        'scores': parsed['scores'], 'runtime_metrics': parsed['runtime_metrics'],
        'timing': timing(operation), 'structure': cif_receipt,
        'limitations': ['Scores are model predictions, not experimental structure validation.',
                        'This Preview2 App uses a fixed seed and one diffusion sample without templates or online MSA search.'],
    }
    save(analysis / 'summary.json', summary)
    structure_path, summary_path = analysis / 'structure.cif', analysis / 'summary.json'
    return {**summary, 'structure_path': str(structure_path), 'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(structure=structure_path, summary=summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fasta', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--request-id', default='recording-openfold3')
    parser.add_argument('--input-id', default='protein')
    parser.add_argument('--chain-id', default='A')
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='openfold3')
    parser.add_argument('--tool', default='infer_openfold3_native')
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 193 or not 0 <= args.wait_seconds <= 3600:
        parser.error('Invalid OpenFold3 idempotency key or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained input/run/analysis receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
