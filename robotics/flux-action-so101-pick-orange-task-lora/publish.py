"""Copy only complete LeRobot checkpoints to the mounted bucket."""

import hashlib
import json
import os
import shutil
from pathlib import Path


ADAPTER_HASH_KEYS = {
    "pretrained_model": "adapter_sha256",
    "pretrained_model_ema": "ema_adapter_sha256",
}


def adapter_hash(path: Path) -> str:
    adapter = path / "adapter_model.safetensors"
    if not adapter.is_file() or not (path / "adapter_config.json").is_file():
        raise ValueError(f"incomplete adapter checkpoint: {path}")
    with adapter.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_adapter(path: Path, record: dict) -> str:
    key = ADAPTER_HASH_KEYS.get(path.name)
    if key is None or key not in record:
        raise ValueError(f"no published checksum for adapter checkpoint: {path}")
    actual = adapter_hash(path)
    if actual != record[key]:
        raise ValueError("published adapter checksum mismatch")
    return actual


def publish(source: Path, destination: Path, calibration_id: str | None = None) -> list[dict]:
    checkpoints = source / "checkpoints"
    last = checkpoints / "last"
    if not last.is_symlink():
        return []
    latest = os.readlink(last)
    if not latest.isdigit():
        raise ValueError(f"unexpected last checkpoint target: {latest}")
    published = []
    for checkpoint in sorted(checkpoints.iterdir(), key=lambda path: int(path.name) if path.name.isdigit() else -1):
        if not checkpoint.is_dir() or not checkpoint.name.isdigit() or int(checkpoint.name) > int(latest):
            continue
        target = destination / "checkpoints" / checkpoint.name
        marker = target / "COMPLETE.json"
        if marker.exists():
            record = json.loads(marker.read_text())
            if record.get("calibration_id") != calibration_id:
                raise ValueError(f"checkpoint {checkpoint.name} calibration differs from this run")
            published.append(record)
            continue
        for path in checkpoint.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"checkpoint contains symlink: {path}")
            relative = path.relative_to(checkpoint)
            output = target / relative
            if path.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, output)
        record = {"step": int(checkpoint.name), "directory": checkpoint.name}
        for directory, key in ADAPTER_HASH_KEYS.items():
            path = target / directory
            if directory == "pretrained_model" or path.exists():
                record[key] = adapter_hash(path)
        if calibration_id is not None:
            record["calibration_id"] = calibration_id
        marker.write_text(json.dumps(record, indent=2) + "\n")
        published.append(record)
        print(f"published checkpoint {checkpoint.name}", flush=True)
    return published
