"""Periodic, verified optimizer-state checkpoints for explicit job resumption."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from .common import sha256_file, write_json
from .object_store import s3_client


def publish_resume_checkpoint(trainer, output, *, manifest_hashes, base_revision):
    bucket = os.getenv("CHECKPOINT_BUCKET")
    prefix = os.getenv("CHECKPOINT_PREFIX")
    if not bucket or not prefix or not prefix.startswith("runs/") or ".." in PurePosixPath(prefix).parts:
        raise ValueError("periodic_checkpoints_require_bucket_and_run_prefix")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    step = trainer.global_step
    path = output / f"step-{step:08d}.ckpt"
    temp = path.with_suffix(".tmp")
    trainer.save_checkpoint(str(temp))
    temp.replace(path)
    digest = sha256_file(path)
    client = s3_client()
    key = prefix.rstrip("/") + "/" + path.name
    client.upload_file(str(path), bucket, key)
    response = client.get_object(Bucket=bucket, Key=key)
    actual = hashlib.sha256()
    try:
        for chunk in response["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
            actual.update(chunk)
    finally:
        response["Body"].close()
    if actual.hexdigest() != digest:
        raise RuntimeError("resume_checkpoint_readback_mismatch")
    metadata = {"checkpoint_key": key, "sha256": digest, "global_step": step,
                "manifest_hashes": manifest_hashes, "base_revision": base_revision,
                "format": "pytorch_lightning_full_optimizer_state", "checkpoint_bytes": path.stat().st_size}
    pointer = output / "latest.json"
    write_json(pointer, metadata)
    # Pointer publication follows the full readback verification, never precedes it.
    client.upload_file(str(pointer), bucket, prefix.rstrip("/") + "/latest.json")


def stage_resume_checkpoint(pointer_key, output, *, manifest_hashes, base_revision):
    bucket = os.environ["CHECKPOINT_BUCKET"]
    key_path = PurePosixPath(pointer_key)
    if key_path.is_absolute() or ".." in key_path.parts or key_path.suffix != ".json":
        raise ValueError("invalid_resume_pointer")
    client = s3_client()
    response = client.get_object(Bucket=bucket, Key=pointer_key)
    try:
        metadata = json.loads(response["Body"].read(65537))
    finally:
        response["Body"].close()
    if metadata["manifest_hashes"] != manifest_hashes or metadata["base_revision"] != base_revision:
        raise ValueError("resume_dataset_or_base_revision_mismatch")
    checkpoint_key = metadata["checkpoint_key"]
    if PurePosixPath(checkpoint_key).parent != key_path.parent:
        raise ValueError("resume_pointer_outside_own_prefix")
    target = Path(output) / "resume.ckpt"
    client.download_file(bucket, checkpoint_key, str(target))
    if sha256_file(target) != metadata["sha256"]:
        target.unlink()
        raise ValueError("resume_checkpoint_sha256_mismatch")
    return str(target)
