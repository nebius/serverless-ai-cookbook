#!/usr/bin/env python3
"""Offline, payload-free comparison of retained scientific startup attempts.

Requested snapshot policy is not a restored-process observation. Lifecycle
estimates are never added as though they were disjoint GPU utilization spans.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
from itertools import combinations
import json
from pathlib import Path
import re
from statistics import median, pstdev

import numpy as np
from Bio.PDB import MMCIFParser, PDBParser

LABEL = 'fs2.nebius.ai/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Evidence timestamps must include a timezone.')
    return parsed


def seconds(start, end):
    if start is None or end is None:
        return None
    value = (stamp(end) - stamp(start)).total_seconds()
    if value < 0:
        raise ValueError('Negative duration; evidence is inconsistent.')
    return value


def distribution(values):
    if any(isinstance(value, bool) for value in values):
        raise ValueError('Boolean is not a measured duration.')
    known = [float(value) for value in values if value is not None]
    if any(not np.isfinite(value) or value < 0 for value in known):
        raise ValueError('Invalid duration in retained evidence.')
    return {'n': len(known), 'missing': len(values) - len(known),
            'min': min(known) if known else None, 'median': median(known) if known else None,
            'max': max(known) if known else None, 'population_stddev': pstdev(known) if known else None,
            'unit': 'seconds', 'qualification': 'exploratory, not a percentile SLO'}


def json_log_records(text):
    """Parse timestamped single/multiline JSON without returning free-form logs."""
    cleaned = '\n'.join(re.sub(r'^\d{4}-\d\d-\d\dT\S+\s', '', line) for line in text.splitlines())
    decoder, offset = json.JSONDecoder(), 0
    while offset < len(cleaned):
        position = cleaned.find('{', offset)
        if position < 0:
            return
        try:
            value, size = decoder.raw_decode(cleaned[position:])
        except ValueError:
            offset = position + 1
            continue
        offset = position + size
        if isinstance(value, dict):
            yield value


def mechanism(requested, pod_ids, observations, *, expected_attempt_ids=None):
    if expected_attempt_ids is not None and set(expected_attempt_ids) != {
            pod['attempt_id'] for pod in pod_ids.values()}:
        return 'unknown-or-incomplete-worker-mechanism'
    by_pod = {uid: set() for uid in pod_ids}
    for row in observations:
        if row['pod_uid'] in by_pod:
            by_pod[row['pod_uid']].add(row['mechanism'])
    if requested == 'normal-load' and all(not events for events in by_pod.values()):
        return 'normal-load-requested; no restore observed'
    if by_pod and all(events == {'cuda-criu-restored'} for events in by_pod.values()):
        return 'all-observed-workers-restored'
    events = set().union(*by_pod.values()) if by_pod else set()
    if 'normal-load-fallback' in events and 'cuda-criu-restored' in events:
        return 'mixed-restore-and-normal-fallback'
    if 'normal-load-fallback' in events:
        return 'normal-load-fallback'
    return 'unknown-or-incomplete-worker-mechanism'


def structure_data(text):
    first = next((line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')), '')
    parser = MMCIFParser(QUIET=True) if first.startswith('data_') else PDBParser(QUIET=True)
    models = list(parser.get_structure('retained', io.StringIO(text)).get_models())
    if len(models) != 1:
        raise ValueError('Expected exactly one coordinate model per artifact.')
    positions, identifiers, distances = [], [], []
    atom_count = 0
    for chain in models[0]:
        previous = None
        for residue in chain:
            atoms = list(residue.get_atoms())
            atom_count += len(atoms)
            if any(not np.isfinite(atom.coord).all() for atom in atoms):
                raise ValueError('Nonfinite atom coordinates.')
            if 'CA' not in residue or residue.id[0] != ' ':
                continue
            xyz = np.asarray(residue['CA'].coord, dtype=float)
            identifier = [chain.id, *residue.id, residue.resname]
            if previous is not None and residue.id[1] == previous[0] + 1:
                distances.append(float(np.linalg.norm(xyz - previous[1])))
            previous = (residue.id[1], xyz)
            identifiers.append(identifier)
            positions.append(xyz)
    if len(positions) < 3:
        raise ValueError('Fewer than three protein C-alpha coordinates.')
    return np.asarray(positions), identifiers, {
        'protein_ca_count': len(positions), 'atom_count': atom_count,
        'chain_count': len({value[0] for value in identifiers}),
        'residue_identity_sha256': sha(json.dumps(identifiers).encode()),
        'finite_coordinates': True, 'consecutive_ca_pairs': len(distances),
        'ca_distance_min_angstrom': min(distances) if distances else None,
        'ca_distance_max_angstrom': max(distances) if distances else None,
        'ca_distances_outside_2_5_to_4_5_angstrom': sum(not 2.5 <= d <= 4.5 for d in distances),
        'scope': 'Parsing, finite coordinates and descriptive backbone geometry; not experimental accuracy or biological efficacy.'}


def structure_comparison(left, right):
    a, ids_a, _ = structure_data(left)
    b, ids_b, _ = structure_data(right)
    if ids_a != ids_b:
        return {'comparable': False, 'reason': 'Residue/chain/name order differs; no guessed correspondence.'}
    centered_a, centered_b = a - a.mean(axis=0), b - b.mean(axis=0)
    u, _, vt = np.linalg.svd(centered_b.T @ centered_a)
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    fitted = centered_b @ (u @ vt)
    return {'comparable': True, 'ca_count': len(a), 'identical_coordinate_bytes': left == right,
            'raw_ca_rmsd_angstrom': float(np.sqrt(np.mean(np.sum((a - b) ** 2, axis=1)))),
            'jointly_fitted_ca_rmsd_angstrom': float(np.sqrt(np.mean(np.sum((centered_a - fitted) ** 2, axis=1)))),
            'max_fitted_ca_displacement_angstrom': float(np.max(np.linalg.norm(centered_a - fitted, axis=1))),
            'equivalence_verdict': 'descriptive_only; no undeclared numerical tolerance or experimental-reference claim'}


def analyze(root):
    root = Path(root)
    sources = {}
    def read(path):
        data = path.read_bytes()
        sources[str(path.relative_to(root))] = sha(data)
        return json.loads(data)
    comparison = read(root / 'comparison.json')
    stage = comparison['identity']['stage']
    samples, coordinates = [], {}
    # Include partially observed runs even before comparison.json appends them.
    declared = {sample['run_id']: sample for sample in comparison['samples']}
    for path in root.glob('*/receipt.json'):
        run_id = path.parent.name
        declared.setdefault(run_id, {'run_id': run_id, 'requested_backend':
            'cuda-criu' if run_id.endswith('-cuda-criu') else 'normal-load'})
    for run_id, declared_sample in sorted(declared.items()):
        folder = root / run_id
        receipt = read(folder / 'receipt.json')
        state_path = folder / 'status.json'
        status = read(state_path) if state_path.exists() else {}
        operation = status.get('operation', {})
        pods, logs, log_seen = {}, [], set()
        for path in sorted((folder / 'observations').glob('*-pods.json')):
            for pod in read(path).get('items', []):
                meta, spec, body = pod['metadata'], pod['spec'], pod.get('status', {})
                if meta.get('labels', {}).get(LABEL + 'stage-id') != stage:
                    continue
                uid = meta['uid']
                entry = pods.setdefault(uid, {'uid': uid, 'node': spec.get('nodeName'),
                    'attempt_id': meta['labels'].get(LABEL + 'attempt-id'),
                    'shard_id': meta['labels'].get(LABEL + 'shard-id'),
                    'created_at': meta.get('creationTimestamp'), 'model_containers': {},
                    'companion_images': set(), 'snapshot_manifest_sha256': meta.get('annotations', {}).get(LABEL + 'snapshot-manifest-sha256')})
                if spec.get('nodeName'):
                    entry['node'] = spec['nodeName']
                statuses = {c['name']: c for c in body.get('containerStatuses', [])}
                for container in spec.get('initContainers', []) + spec.get('containers', []):
                    if not int(container.get('resources', {}).get('requests', {}).get('nvidia.com/gpu', 0)):
                        entry['companion_images'].add(container['image'])
                        continue
                    observed = statuses.get(container['name'], {})
                    runtime = entry['model_containers'].setdefault(container['name'], {'requested_images': set(), 'observed_image_ids': set(), 'restart_count_max': 0})
                    runtime['requested_images'].add(container['image'])
                    if observed.get('imageID'):
                        runtime['observed_image_ids'].add(observed['imageID'])
                    runtime['restart_count_max'] = max(runtime['restart_count_max'], observed.get('restartCount', 0))
                    for key in ('running', 'terminated'):
                        times = observed.get('state', {}).get(key, {})
                        if times.get('startedAt'):
                            runtime['started_at'] = times['startedAt']
                        if times.get('finishedAt'):
                            runtime['finished_at'] = times['finishedAt']
        for path in sorted((folder / 'worker-logs').glob('*.json')):
            document = read(path)
            uid = document['pod_uid']
            for container in document.get('containers', {}).values():
                for record in json_log_records(container.get('text', '')):
                    identity = (uid, sha(json.dumps(record, sort_keys=True).encode()))
                    if identity in log_seen:
                        continue
                    log_seen.add(identity)
                    if record.get('event') == 'scientific_snapshot_request':
                        logs.append({'pod_uid': uid, 'mechanism': record.get('mechanism')})
                    if record.get('action') == 'restore' and isinstance(record.get('runtime_identity'), dict):
                        target = pods.get(uid)
                        if target is not None:
                            target['restore_identity'] = {key: record['runtime_identity'].get(key) for key in (
                                'runtime_image', 'runtime_id', 'model_revision', 'kernel_release',
                                'gpu_uuid', 'gpu_name', 'driver_version', 'compute_capability')}
                            target['restore_action_status'] = record.get('status')
                            target['restore_subprocesses'] = [
                                {'executable': Path(row.get('command', ['unknown'])[0]).name,
                                 'phase': 'criu-process-restore' if any(Path(arg).name == 'criu' for arg in row.get('command', [])) else
                                    'cuda-' + (row['command'][row['command'].index('--action') + 1] if '--action' in row.get('command', []) else 'unknown'),
                                 'seconds': row.get('seconds'), 'returncode': row.get('returncode')}
                                for row in record.get('records', [])]
        for pod in pods.values():
            pod['companion_images'] = sorted(pod['companion_images'])
            pod.setdefault('restore_identity', None)
            node_path = folder / 'worker-nodes' / (pod['uid'] + '.json')
            pod['node_label_evidence'] = None
            if node_path.exists():
                capture = read(node_path)
                if capture.get('available'):
                    meta = capture['node']['metadata']
                    if capture['pod_uid'] != pod['uid'] or meta['name'] != pod['node']:
                        raise ValueError('Captured node identity does not match worker.')
                    pod['node_label_evidence'] = {'node_uid': meta['uid'],
                        'observed_at': capture['observed_at'], 'source': capture['driver_evidence'],
                        'labels': {key: value for key, value in meta.get('labels', {}).items()
                            if any(part in key for part in ('driver', 'kernel', 'cuda', 'gpu.product'))}}
            for container in pod['model_containers'].values():
                container['requested_images'] = sorted(container['requested_images'])
                container['observed_image_ids'] = sorted(container['observed_image_ids'])
        accounting_path = folder / 'operator-accounting.json'
        accounting = read(accounting_path).get('data', {}) if accounting_path.exists() else {}
        independent, structures = [], {}
        runtime_reports = []
        artifact_path = folder / 'verified-artifacts.json'
        if artifact_path.exists():
            for output in read(artifact_path).get('outputs', []):
                producer_times = {key: output[key] for key in ('model_ready_seconds', 'phases_seconds', 'total_seconds') if key in output}
                if producer_times:
                    runtime_reports.append({'artifact_name': output['artifact_name'], 'producer_reported_times': producer_times,
                        'scope': 'Producer-defined timings; not assumed independent or pure GPU compute.'})
                if not isinstance(output.get('structure'), str):
                    continue
                name, text = output['artifact_name'], output['structure']
                if name in structures:
                    raise ValueError('Duplicate named structure artifact.')
                structures[name] = text
                measured = {'artifact_name': name, 'text_sha256': sha(text.encode()),
                            'verified_artifact_sha256': output.get('verified_sha256')}
                try:
                    if measured['text_sha256'] != measured['verified_artifact_sha256']:
                        raise ValueError('Materialized structure hash differs from verified artifact hash.')
                    _, _, geometry = structure_data(text)
                    measured.update(parsed=True, **geometry)
                except (ValueError, KeyError, StopIteration) as error:
                    measured.update(parsed=False, error=str(error))
                independent.append(measured)
        coordinates[run_id] = structures
        selected_stage = next((item for item in status.get('batch', {}).get('stages', []) if item['stage_id'] == stage), None)
        expected_attempt_ids = [item['attempt_id'] for item in selected_stage['attempts']] if selected_stage else None
        sample = {'run_id': run_id, 'requested_backend': declared_sample['requested_backend'],
            'state': receipt['state'], 'operation_id': receipt.get('operation_id'),
            'request_sha256': receipt['identity']['request_sha256'],
            'same_identity_replay_verified': receipt.get('same_identity_replay_verified', False),
            'semantic_validation': receipt.get('semantic_validation'),
            'observed_mechanism': mechanism(declared_sample['requested_backend'], pods, logs,
                expected_attempt_ids=expected_attempt_ids),
            'mechanism_witnesses': logs, 'gpu_workers': list(pods.values()),
            'client_wall_seconds': seconds(receipt.get('started_at'), receipt.get('finished_at')),
            'accepted_to_completed_seconds': seconds(operation.get('accepted_at'), operation.get('completed_at')),
            'service_started_to_completed_seconds': seconds(operation.get('started_at'), operation.get('completed_at')),
            'lifecycle_phase_estimates': accounting.get('lifecycle_phases', []),
            'producer_runtime_reports': runtime_reports,
            'independent_structure_checks': independent}
        samples.append(sample)
    pairs = []
    for normal in samples:
        if normal['requested_backend'] != 'normal-load':
            continue
        restore_id = normal['run_id'].removesuffix('-normal-load') + '-cuda-criu'
        restored = next((sample for sample in samples if sample['run_id'] == restore_id), None)
        if restored is None:
            continue
        left, right = coordinates[normal['run_id']], coordinates[restore_id]
        def images(sample):
            return sorted({image for pod in sample['gpu_workers'] for c in pod['model_containers'].values() for image in c['observed_image_ids']})
        pairs.append({'normal_run_id': normal['run_id'], 'requested_restore_run_id': restore_id,
            'same_request_identity': normal['request_sha256'] == restored['request_sha256'],
            'same_observed_model_images': bool(images(normal)) and images(normal) == images(restored),
            'restore_mechanism': restored['observed_mechanism'],
            'same_named_structure_set': bool(left) and left.keys() == right.keys(),
            'structures': {name: structure_comparison(left[name], right[name]) for name in sorted(left.keys() & right.keys())},
            'environment_equivalence': 'not established by equal image alone; normal-load driver may be unavailable'})
    within_mechanism = []
    for left_sample, right_sample in combinations(samples, 2):
        if (left_sample['requested_backend'], left_sample['observed_mechanism']) != (right_sample['requested_backend'], right_sample['observed_mechanism']):
            continue
        left, right = coordinates[left_sample['run_id']], coordinates[right_sample['run_id']]
        within_mechanism.append({'left_run_id': left_sample['run_id'], 'right_run_id': right_sample['run_id'],
            'mechanism': left_sample['observed_mechanism'],
            'same_request_identity': left_sample['request_sha256'] == right_sample['request_sha256'],
            'structures': {name: structure_comparison(left[name], right[name]) for name in sorted(left.keys() & right.keys())}})
    groups = []
    for requested, observed in sorted({(sample['requested_backend'], sample['observed_mechanism']) for sample in samples}):
        selected = [sample for sample in samples if (sample['requested_backend'], sample['observed_mechanism']) == (requested, observed)]
        groups.append({'requested_backend': requested, 'observed_mechanism': observed,
            'states': dict(Counter(sample['state'] for sample in selected)),
            'client_wall': distribution([sample['client_wall_seconds'] for sample in selected]),
            'accepted_to_completed': distribution([sample['accepted_to_completed_seconds'] for sample in selected]),
            'lifecycle_phases': {phase: distribution([next((row['duration']['value'] for row in sample['lifecycle_phase_estimates'] if row['phase'] == phase), None) for sample in selected])
                for phase in sorted({row['phase'] for sample in selected for row in sample['lifecycle_phase_estimates']})}})
    return {'schema': 'scientific-startup-exploratory-summary/v1', 'as_of': datetime.now(timezone.utc).isoformat(),
        'identity': comparison['identity'], 'scope': comparison['measurement_scope'],
        'policy_restored': comparison.get('policy_active') is False, 'policy_restored_at': comparison.get('restored_at'),
        'samples': samples, 'matched_repetition_pairs': pairs, 'within_mechanism_repeats': within_mechanism,
        'descriptive_groups': groups, 'analysis_source_sha256': sha(Path(__file__).read_bytes()),
        'evidence_sources_sha256': sources,
        'limits': ['Three repetitions are exploratory, not twenty-sample Fast Start qualification or a percentile SLO.',
                   'Fresh Pods on prepared/warm capacity do not establish cold-node or cold-registry-cache performance.',
                   'Fallback and mixed-shard attempts remain separate from actual restore; failures/partial attempts are retained.',
                   'Lifecycle duration values retain their source estimated/unavailable labels; overlapping phases are not summed into GPU time.',
                   'Model images, companion images and per-restore driver identity are retained per attempt; no unchanged-release claim is inferred.',
                   'Structure agreement is descriptive; no scientific equivalence tolerance, experimental accuracy or biological function is inferred.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = analyze(args.comparison)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'samples': len(value['samples']),
                      'policy_restored': value['policy_restored'], 'scope': 'exploratory'}))


if __name__ == '__main__':
    main()
