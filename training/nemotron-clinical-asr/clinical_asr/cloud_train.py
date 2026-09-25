"""Train a fresh candidate on a pinned, already-aligned data bundle.

The shared archive is staged once per job, not re-aligned or republished. Source
manifests and every WAV checksum are verified before training. Outputs are
manifest-last and never overwrite an earlier run. No resumed-training claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import math
import re
import subprocess
import sys
import tarfile
import time

from .cloud import safe_key, upload_outputs
from .common import read_jsonl, sha256_file, write_json


def extract_verified_archive(archive, target, expected):
    """No links, special files, traversal, duplicates or undeclared members."""
    seen = set()
    target = Path(target)
    with tarfile.open(archive, 'r|*') as stream:
        for member in stream:
            key = safe_key(member.name)
            if not member.isfile() or key not in expected or key in seen or '\\' in key:
                raise ValueError('archive_member_not_declared_regular_unique')
            obj = expected[key]
            if member.size != obj['bytes']:
                raise ValueError('archive_member_size_mismatch')
            destination = target / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with stream.extractfile(member) as source, destination.open('xb') as output:
                for chunk in iter(lambda: source.read(8 * 1024 * 1024), b''):
                    h.update(chunk)
                    output.write(chunk)
            if h.hexdigest() != obj['sha256']:
                raise ValueError('archive_member_sha256_mismatch')
            seen.add(key)
    if seen != set(expected):
        raise ValueError('archive_missing_declared_members')
    return len(seen)


def main():
    from .cloud_evaluate import add_cohort_arguments, pinned_cohorts, stage_cohorts, evaluate_cohorts
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--bundle-key', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--arm', choices=['clinical-only', 'mixed'], required=True)
    parser.add_argument('--max-steps', type=int, default=500)
    parser.add_argument('--val-every', type=int, default=100)
    parser.add_argument('--batch-duration', type=float, default=120)
    parser.add_argument('--accumulate-grad-batches', type=int, default=1)
    parser.add_argument('--learning-rate', type=float, default=1e-4)
    parser.add_argument('--seed', type=int, default=20260926)
    parser.add_argument('--checkpoint-every', type=int, default=200)
    parser.add_argument('--require-replay-by-step', type=int, default=50)
    parser.add_argument('--upload-workers', type=int, default=8)
    add_cohort_arguments(parser)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,100}', args.run_id):
        raise ValueError('invalid_run_id')
    if not re.fullmatch(r'[0-9a-f]{64}', args.bundle_sha256):
        raise ValueError('immutable_bundle_sha256_required')
    if min(args.max_steps, args.val_every, args.batch_duration, args.accumulate_grad_batches, args.require_replay_by_step) <= 0:
        raise ValueError('positive_training_parameters_required')
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0 or not math.isfinite(args.batch_duration):
        raise ValueError('finite_positive_learning_parameters_required')
    if not 0 <= args.seed < 2**32 or not 1 <= args.upload_workers <= 16 or args.checkpoint_every < 0:
        raise ValueError('invalid_seed_workers_or_checkpoint_interval')
    specs = pinned_cohorts(args.evaluation_manifest_key, args.evaluation_manifest_sha256)
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.config import Config
    client = boto3.client('s3', endpoint_url=os.environ['AWS_ENDPOINT_URL'],
                          region_name=os.getenv('AWS_DEFAULT_REGION', 'eu-north1'),
                          config=Config(signature_version='s3v4', retries={'max_attempts': 8},
                                        s3={'addressing_style': 'path'}))
    prefix = 'runs/' + args.run_id
    if client.list_objects_v2(Bucket=args.bucket, Prefix=prefix + '/', MaxKeys=1).get('Contents'):
        raise ValueError('new_run_id_required_no_remote_overwrite')
    output = Path('/output') / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    source_root = Path('/data/clinical-speech')
    bundle_root = source_root / 'round2-bundle'
    bundle_root.mkdir(parents=True, exist_ok=False)
    os.environ['CHECKPOINT_BUCKET'] = args.bucket
    os.environ['CHECKPOINT_PREFIX'] = prefix + '/resume'
    status = {'run_id': args.run_id, 'status': 'running', 'started_at_unix': time.time(),
              'parameters': vars(args), 'clinical_validation': 'NOT_PERFORMED'}
    write_json(output / 'run-status.json', status)

    def download(key, checksum, destination, expected_bytes=None):
        if not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise ValueError('source_sha_required')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError('staging_path_exists')
        client.download_file(args.bucket, safe_key(key), str(destination))
        if sha256_file(destination) != checksum or (expected_bytes is not None and destination.stat().st_size != expected_bytes):
            raise ValueError('downloaded_source_sha_or_size_mismatch')
        return destination

    def command(name, arguments):
        print(json.dumps({'stage': name, 'state': 'starting', 'run_id': args.run_id}), flush=True)
        with (output / (name + '.log')).open('x') as log:
            process = subprocess.Popen([sys.executable, '-m', 'clinical_asr', *arguments],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line.rstrip(), flush=True)
            if process.wait() != 0:
                raise RuntimeError('stage_failed:' + name)

    stage = 'stage_bundle'
    failure = None
    try:
        print(json.dumps({'stage': stage, 'state': 'starting'}), flush=True)
        from .environment import collect
        write_json(output / 'environment.json', collect())
        bundle_path = download(args.bundle_key, args.bundle_sha256, output / 'bundle.json')
        bundle = json.loads(bundle_path.read_text())
        if bundle['schema'] != 'clinical-speech/prealigned-training-bundle/v1' or bundle['seed'] != args.seed:
            raise ValueError('bundle_schema_or_seed_mismatch')
        paths, all_rows = {}, {}
        for label, obj in bundle['manifests'].items():
            paths[label] = download(obj['key'], obj['sha256'], output / 'inputs' / (label + '.jsonl'), obj['bytes'])
            all_rows[label] = read_jsonl(paths[label])
            if len(all_rows[label]) != obj['rows']:
                raise ValueError('manifest_count_mismatch')
        expected = {}
        # Bundle includes the common clinical/dev/replay sources for both arms;
        # only the chosen arm manifest is passed to the actual trainer.
        for row in all_rows['mixed'] + all_rows['dev']:
            member = safe_key(str(Path(row['audio_filepath']).relative_to(bundle_root)))
            if member in expected:
                raise ValueError('duplicate_audio_in_training_bundle')
            expected[member] = {'sha256': row['audio_sha256'], 'bytes': row['audio_bytes']}
        archive_obj = bundle['archive']
        archive = download(archive_obj['key'], archive_obj['sha256'], bundle_root / 'download.tar', archive_obj['bytes'])
        count = extract_verified_archive(archive, bundle_root, expected)
        if count != archive_obj['members']:
            raise ValueError('archive_count_mismatch')
        # Only this task-local downloaded archive is removed after exact WAV
        # verification; immutable S3/source data and all extracted WAVs remain.
        archive.unlink()
        write_json(output / 'input-verification.json', {'bundle_key': args.bundle_key,
                   'bundle_sha256': args.bundle_sha256, 'waveforms_verified': count,
                   'selected_arm': args.arm, 'train_manifest_sha256': sha256_file(paths[args.arm]),
                   'dev_manifest_sha256': sha256_file(paths['dev']),
                   'source_data_mutated': False, 'archive_sha256': archive_obj['sha256']})
        print(json.dumps({'stage': stage, 'state': 'completed', 'waveforms_verified': count}), flush=True)
        stage = 'train'
        command(stage, ['train', '--train-manifest', str(paths[args.arm]), '--dev-manifest', str(paths['dev']),
                        '--output', str(output / 'training'), '--max-steps', str(args.max_steps),
                        '--val-every', str(args.val_every), '--batch-duration', str(args.batch_duration),
                        '--accumulate-grad-batches', str(args.accumulate_grad_batches),
                        '--learning-rate', str(args.learning_rate), '--seed', str(args.seed),
                        '--checkpoint-every', str(args.checkpoint_every), '--expected-data-mix', args.arm,
                        '--require-replay-by-step', str(args.require_replay_by_step)])
        if specs:
            stage = 'stage_known_evaluation'
            cohorts = stage_cohorts(client, args.bucket, source_root, output, specs)
            provenance = json.loads((output / 'training/training-provenance.json').read_text())
            stage = 'evaluate_known_cohorts'
            evaluate_cohorts(cohorts, output / 'training/nemotron-clinical-en.nemo', provenance['checkpoint_sha256'], command)
        status.update(status='completed', finished_at_unix=time.time())
    except BaseException as exc:
        failure = exc
        status.update(status='failed', failed_stage=stage, error_type=type(exc).__name__, finished_at_unix=time.time())
    finally:
        write_json(output / 'run-status.json', status)
        started = time.monotonic()
        objects = upload_outputs(client, args.bucket, prefix, output, include_checkpoints=False,
                                 workers=args.upload_workers, transfer_config=TransferConfig(use_threads=False))
        publication = {'schema': 'clinical-speech/prealigned-training-publication/v1',
                       'run_id': args.run_id, 'status': status['status'], 'objects': objects,
                       'bundle_sha256': args.bundle_sha256, 'arm': args.arm,
                       'cohorts': specs, 'clinical_validation': 'NOT_PERFORMED',
                       'checksums': 'local_SHA256_and_full_S3_GET_readback',
                       'output_upload_seconds': time.monotonic() - started,
                       'output_upload_workers': args.upload_workers}
        filename = 'completed.json' if status['status'] == 'completed' else 'failed.json'
        write_json(output / filename, publication)
        client.upload_file(str(output / filename), args.bucket, prefix + '/' + filename)
        print(json.dumps({'run_id': args.run_id, 'publication': prefix + '/' + filename, 'status': status['status']}), flush=True)
    if failure:
        raise failure
