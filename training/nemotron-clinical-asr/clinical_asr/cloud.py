"""Stage immutable source data to local disk and publish outputs without FUSE.

Only boto3's environment credential chain is used. No credentials in argv/logs.
Publication is manifest-last; an absent completed.json means not promotable.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

from .common import read_jsonl, sha256_file, write_json


def safe_key(key):
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or not key:
        raise ValueError("unsafe_object_key")
    return str(path)


def upload_outputs(client, bucket, prefix, output, *, include_checkpoints=False, workers=8, transfer_config=None):
    """Bounded publication, verified per object; never publishes a success marker.

    S3 clients are thread-safe. transfer_config disables nested transfer threads
    so the configured worker count also bounds concurrent upload/readback I/O.
    """
    if not 1 <= workers <= 16:
        raise ValueError("upload_workers_must_be_1_to_16")
    paths = [path for path in sorted(output.rglob("*")) if path.is_file()
             and path.name not in {"completed.json", "failed.json"}
             and (include_checkpoints or path.suffix != ".ckpt")]

    def upload(path):
        checksum = sha256_file(path)
        size = path.stat().st_size
        key = prefix + "/" + str(path.relative_to(output))
        client.upload_file(str(path), bucket, key, Config=transfer_config,
                           ExtraArgs={"Metadata": {"sha256": checksum}})
        remote = client.get_object(Bucket=bucket, Key=key)
        remote_hash = hashlib.sha256()
        try:
            for chunk in remote["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
                remote_hash.update(chunk)
        finally:
            remote["Body"].close()
        if remote["ContentLength"] != size or remote_hash.hexdigest() != checksum:
            raise RuntimeError("output_upload_verification_failed")
        return {"key": key, "sha256": checksum, "bytes": size}

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = []
    try:
        futures = [pool.submit(upload, path) for path in paths]
        results = [future.result() for future in as_completed(futures)]
    except BaseException:
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return sorted(results, key=lambda item: item["key"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=os.getenv("DATA_BUCKET"), required=not bool(os.getenv("DATA_BUCKET")))
    parser.add_argument("--manifest-key", default="manifests/pilot-alignment.jsonl")
    parser.add_argument("--replay-manifest-key", help="Optional already-segmented, disjoint general-English training replay")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--val-every", type=int, default=5)
    parser.add_argument("--batch-duration", type=float, default=30.0)
    parser.add_argument("--accumulate-grad-batches", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--mode", choices=["align", "align-train", "align-train-evaluate"], default="align-train-evaluate")
    parser.add_argument("--upload-lightning-checkpoints", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=0)
    parser.add_argument("--resume-pointer")
    parser.add_argument("--upload-workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.upload_workers <= 16:
        raise ValueError("upload_workers_must_be_1_to_16")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,100}", args.run_id):
        raise ValueError("invalid_run_id")
    import boto3
    from botocore.config import Config
    client = boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"],
                          region_name=os.getenv("AWS_DEFAULT_REGION", "eu-north1"),
                          config=Config(signature_version="s3v4", retries={"max_attempts": 8},
                                        s3={"addressing_style": "path"}))
    source_root = Path("/data/clinical-speech")
    output = Path("/output") / args.run_id
    output.mkdir(parents=True, exist_ok=True)
    prefix = "runs/" + args.run_id
    if args.checkpoint_every or args.resume_pointer:
        os.environ["CHECKPOINT_BUCKET"] = args.bucket
        os.environ["CHECKPOINT_PREFIX"] = prefix + "/resume"
    # Refuse to overwrite an already published successful experiment.
    from botocore.exceptions import ClientError
    try:
        client.head_object(Bucket=args.bucket, Key=prefix + "/completed.json")
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in {"404", "NoSuchKey", "NotFound"}:
            raise
    else:
        raise ValueError("run_id_already_completed")
    stage = "stage_data"
    status = {"run_id": args.run_id, "status": "running", "started_at_unix": time.time(), "parameters": vars(args)}
    write_json(output / "run-status.json", status)
    uploaded = []

    def download(key):
        key = safe_key(key)
        target = source_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".download")
        client.download_file(args.bucket, key, str(temp))
        temp.replace(target)
        return target

    def command(name, arguments):
        print(json.dumps({"stage": name, "state": "starting", "run_id": args.run_id}), flush=True)
        with (output / (name + ".log")).open("w") as log:
            process = subprocess.Popen([sys.executable, "-m", "clinical_asr", *arguments],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                log.write(line)
                log.flush()
                # Forward framework progress, never credential values.
                print(line.rstrip(), flush=True)
            if process.wait() != 0:
                raise RuntimeError("stage_failed:" + name)

    failure = None
    try:
        # Record the ACTUAL job environment, not the developer laptop. The
        # collector only reads allowlisted environment values and GPU metadata.
        from .environment import collect
        write_json(output / "environment.json", collect())
        manifest = download(args.manifest_key)
        rows = read_jsonl(manifest)
        staged = []
        for row in rows:
            audio_path = Path(row["audio_filepath"])
            key = str(audio_path.relative_to(source_root))
            target = download(key)
            staged.append({"key": key, "sha256": sha256_file(target), "bytes": target.stat().st_size})
        replay = []
        if args.replay_manifest_key:
            replay_manifest = download(args.replay_manifest_key)
            replay = read_jsonl(replay_manifest)
            for row in replay:
                if row.get("split") != "train" or not str(row.get("conversation_id", "")).startswith("librispeech-train-clean100:"):
                    raise ValueError("replay_requires_explicit_librispeech_train_only_provenance")
                if not 0.5 <= row["duration"] <= 30.0:
                    raise ValueError("replay_duration_out_of_range")
                target = download(str(Path(row["audio_filepath"]).relative_to(source_root)))
                staged.append({"key": str(target.relative_to(source_root)), "sha256": sha256_file(target), "bytes": target.stat().st_size})
        write_json(output / "input-inventory.json", {"manifest_key": args.manifest_key,
                   "manifest_sha256": sha256_file(manifest), "objects": staged})
        stage = "align"
        command(stage, ["align", "--manifest", str(manifest), "--output", str(output / "alignment")])
        stage = "segment"
        command(stage, ["segment", "--source-manifest", str(manifest), "--alignment-dir", str(output / "alignment"),
                        "--output", str(output / "segments")])
        if replay:
            with (output / "segments/train.jsonl").open("a") as train_manifest:
                for row in replay:
                    train_manifest.write(json.dumps(row, ensure_ascii=False) + "\n")
            write_json(output / "replay-provenance.json", {"manifest_key": args.replay_manifest_key,
                       "manifest_sha256": sha256_file(replay_manifest), "utterances": len(replay),
                       "hours": sum(row["duration"] for row in replay) / 3600})
        if args.mode != "align":
            stage = "train"
            command(stage, ["train", "--train-manifest", str(output / "segments/train.jsonl"),
                            "--dev-manifest", str(output / "segments/dev.jsonl"), "--output", str(output / "training"),
                            "--max-steps", str(args.max_steps), "--val-every", str(args.val_every),
                            "--batch-duration", str(args.batch_duration), "--accumulate-grad-batches", str(args.accumulate_grad_batches),
                            "--learning-rate", str(args.learning_rate), "--checkpoint-every", str(args.checkpoint_every),
                            *(["--resume-pointer", args.resume_pointer] if args.resume_pointer else [])])
        if args.mode == "align-train-evaluate":
            stage = "evaluate-base"
            command(stage, ["evaluate", "--manifest", str(output / "segments/dev.jsonl"),
                            "--output", str(output / "evaluation/base-predictions.jsonl"), "--limit", "12"])
            provenance = json.loads((output / "training/training-provenance.json").read_text())
            stage = "evaluate-tuned"
            command(stage, ["evaluate", "--manifest", str(output / "segments/dev.jsonl"),
                            "--output", str(output / "evaluation/tuned-predictions.jsonl"), "--limit", "12",
                            "--model-id", "nemotron-clinical-en", "--checkpoint", str(output / "training/nemotron-clinical-en.nemo"),
                            "--checkpoint-sha", provenance["checkpoint_sha256"]])
        status.update(status="completed", finished_at_unix=time.time())
    except BaseException as exc:
        failure = exc
        status.update(status="failed", failed_stage=stage, error_type=type(exc).__name__, finished_at_unix=time.time())
    finally:
        write_json(output / "run-status.json", status)
        from boto3.s3.transfer import TransferConfig
        started = time.monotonic()
        uploaded = upload_outputs(client, args.bucket, prefix, output,
                                  include_checkpoints=args.upload_lightning_checkpoints,
                                  workers=args.upload_workers, transfer_config=TransferConfig(use_threads=False))
        publication = {"run_id": args.run_id, "status": status["status"], "objects": uploaded,
                       "clinical_validation": "NOT_PERFORMED", "checksums": "local_SHA256_and_full_S3_GET_readback",
                       "output_upload_workers": args.upload_workers,
                       "output_upload_seconds": time.monotonic() - started,
                       "lightning_resume_checkpoints_uploaded": args.upload_lightning_checkpoints}
        final_name = "completed.json" if status["status"] == "completed" else "failed.json"
        write_json(output / final_name, publication)
        client.upload_file(str(output / final_name), args.bucket, prefix + "/" + final_name)
        print(json.dumps({"run_id": args.run_id, "publication": prefix + "/" + final_name, "status": status["status"]}), flush=True)
    if failure:
        raise failure
