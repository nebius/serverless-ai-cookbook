"""Evaluate frozen cohorts separately from the training job's time allowance."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .cloud import safe_key, upload_outputs
from .common import read_jsonl, sha256_file, write_json


def add_cohort_arguments(parser, *, required=False):
    parser.add_argument("--evaluation-manifest-key", action="append", default=[], required=required,
                        help="Repeat once per frozen cohort; every row is evaluated")
    parser.add_argument("--evaluation-manifest-sha256", action="append", default=[], required=required,
                        help="Repeat SHA256 values in the same order as manifest keys")


def pinned_cohorts(keys, hashes):
    if len(keys) != len(hashes):
        raise ValueError("one_frozen_sha256_required_per_evaluation_manifest")
    result = []
    for key, checksum in zip(keys, hashes):
        key = safe_key(key)
        name = Path(key).stem
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", name):
            raise ValueError("invalid_cohort_name")
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("invalid_manifest_sha256")
        if any(item["name"] == name for item in result):
            raise ValueError("duplicate_cohort_output_name")
        result.append({"name": name, "key": key, "sha256": checksum})
    return result


def download(client, bucket, key, root, *, checksum=None):
    key = safe_key(key)
    target = root / key
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("download_path_outside_source_root")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".download")
    client.download_file(bucket, key, str(temp))
    actual = sha256_file(temp)
    if checksum and actual != checksum:
        raise ValueError("download_sha256_mismatch:" + key)
    temp.replace(target)
    return target, actual


def stage_cohorts(client, bucket, root, output, specs):
    """Pin membership before inference; never derive a cohort from predictions."""
    cohorts = []
    staged_audio = {}
    for cohort_index, spec in enumerate(specs, start=1):
        print(json.dumps({"stage": "stage_evaluation_cohort", "state": "starting",
                          "cohort_index": cohort_index, "cohorts_total": len(specs)}), flush=True)
        manifest, _ = download(client, bucket, spec["key"], root, checksum=spec["sha256"])
        rows = read_jsonl(manifest)
        ids = [row.get("id") for row in rows]
        if not rows or any(not isinstance(identity, str) or not identity for identity in ids) or len(set(ids)) != len(ids):
            raise ValueError("evaluation_requires_nonempty_unique_string_ids")
        directory = output / "evaluation" / spec["name"]
        directory.mkdir(parents=True, exist_ok=True)
        references = directory / "references.jsonl"
        shutil.copyfile(manifest, references)
        inventory = []
        for index, row in enumerate(rows, start=1):
            path = Path(row["audio_filepath"])
            key = safe_key(str(path.relative_to(root)))
            if path.suffix.lower() != ".wav" or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("evaluation_audio_must_be_wav_under_source_root")
            if not 0 < float(row["duration"]) <= 1800:
                raise ValueError("evaluation_audio_duration_out_of_range")
            if key not in staged_audio:
                local, actual = download(client, bucket, key, root)
                staged_audio[key] = {"key": key, "sha256": actual, "bytes": local.stat().st_size}
            item = staged_audio[key]
            if row.get("audio_sha256") and row["audio_sha256"] != item["sha256"]:
                raise ValueError("evaluation_audio_sha256_mismatch:" + row["id"])
            inventory.append({"id": row["id"], **item})
            if index == 1 or index % 25 == 0 or index == len(rows):
                print(json.dumps({"stage": "stage_evaluation_cohort", "state": "progress",
                                  "cohort_index": cohort_index, "objects_staged": index,
                                  "objects_total": len(rows)}), flush=True)
        provenance = {**spec, "rows": len(rows), "audio_seconds": sum(float(row["duration"]) for row in rows),
                      "split_labels": sorted({str(row.get("split", "UNSPECIFIED")) for row in rows}),
                      "example_exposure_labels": sorted({str(row.get("example_exposure", "UNSPECIFIED")) for row in rows}),
                      "membership": "all_rows_of_explicit_sha256_pinned_manifest", "audio": inventory}
        write_json(directory / "cohort-provenance.json", provenance)
        cohorts.append({**provenance, "manifest": references, "directory": directory})
    return cohorts


def evaluate_cohorts(cohorts, checkpoint, checkpoint_sha, command):
    for cohort in cohorts:
        for label in ("base", "tuned"):
            arguments = ["evaluate", "--manifest", str(cohort["manifest"]),
                         "--output", str(cohort["directory"] / (label + "-predictions.jsonl"))]
            if label == "tuned":
                arguments += ["--model-id", "nemotron-clinical-en", "--checkpoint", str(checkpoint),
                              "--checkpoint-sha", checkpoint_sha]
            # Deliberately no --limit: missing predictions must fail paired scoring.
            command("evaluate-" + cohort["name"] + "-" + label, arguments)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=os.getenv("DATA_BUCKET"), required=not bool(os.getenv("DATA_BUCKET")))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--checkpoint-key", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--upload-workers", type=int, default=8)
    add_cohort_arguments(parser, required=True)
    args = parser.parse_args()
    specs = pinned_cohorts(args.evaluation_manifest_key, args.evaluation_manifest_sha256)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,100}", args.run_id):
        raise ValueError("invalid_run_id")
    if not re.fullmatch(r"[0-9a-f]{64}", args.checkpoint_sha256) or not args.checkpoint_key.endswith(".nemo"):
        raise ValueError("exact_nemo_checkpoint_and_sha256_required")
    if not 1 <= args.upload_workers <= 16:
        raise ValueError("upload_workers_must_be_1_to_16")
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.config import Config
    from botocore.exceptions import ClientError
    client = boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"],
                          region_name=os.getenv("AWS_DEFAULT_REGION", "eu-north1"),
                          config=Config(signature_version="s3v4", retries={"max_attempts": 8},
                                        s3={"addressing_style": "path"}))
    prefix = "runs/" + args.run_id
    try:
        client.head_object(Bucket=args.bucket, Key=prefix + "/completed.json")
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in {"404", "NoSuchKey", "NotFound"}:
            raise
    else:
        raise ValueError("run_id_already_completed")
    output = Path("/output") / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    source_root = Path("/data/clinical-speech")
    status = {"run_id": args.run_id, "status": "running", "started_at_unix": time.time(), "parameters": vars(args),
              "purpose": "paired_evaluation_only_no_training", "latency_claim": "not_a_repeated_latency_benchmark"}
    failure = None
    stage = "stage_inputs"

    def command(name, arguments):
        nonlocal stage
        stage = name
        print(json.dumps({"stage": name, "state": "starting", "run_id": args.run_id}), flush=True)
        with (output / (name + ".log")).open("w") as log:
            process = subprocess.Popen([sys.executable, "-m", "clinical_asr", *arguments],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line.rstrip(), flush=True)
            if process.wait() != 0:
                raise RuntimeError("stage_failed:" + name)

    try:
        print(json.dumps({"stage": stage, "state": "starting", "run_id": args.run_id}), flush=True)
        from .environment import collect
        write_json(output / "environment.json", collect())
        print(json.dumps({"stage": "stage_checkpoint", "state": "starting"}), flush=True)
        checkpoint, _ = download(client, args.bucket, args.checkpoint_key, source_root, checksum=args.checkpoint_sha256)
        print(json.dumps({"stage": "stage_checkpoint", "state": "verified"}), flush=True)
        cohorts = stage_cohorts(client, args.bucket, source_root, output, specs)
        evaluate_cohorts(cohorts, checkpoint, args.checkpoint_sha256, command)
        status.update(status="completed", finished_at_unix=time.time())
    except BaseException as exc:
        failure = exc
        status.update(status="failed", failed_stage=stage, error_type=type(exc).__name__, finished_at_unix=time.time())
    finally:
        write_json(output / "run-status.json", status)
        started = time.monotonic()
        uploaded = upload_outputs(client, args.bucket, prefix, output, workers=args.upload_workers,
                                  transfer_config=TransferConfig(use_threads=False))
        publication = {"run_id": args.run_id, "status": status["status"], "objects": uploaded,
                       "checkpoint_key": args.checkpoint_key, "checkpoint_sha256": args.checkpoint_sha256,
                       "cohorts": specs, "clinical_validation": "NOT_PERFORMED",
                       "checksums": "local_SHA256_and_full_S3_GET_readback", "output_upload_workers": args.upload_workers,
                       "output_upload_seconds": time.monotonic() - started}
        final_name = "completed.json" if status["status"] == "completed" else "failed.json"
        write_json(output / final_name, publication)
        client.upload_file(str(output / final_name), args.bucket, prefix + "/" + final_name)
        print(json.dumps({"run_id": args.run_id, "publication": prefix + "/" + final_name,
                          "status": status["status"]}), flush=True)
    if failure:
        raise failure
