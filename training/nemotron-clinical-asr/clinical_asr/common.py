import hashlib
import json
import os
from pathlib import Path

from . import BASE_FILENAME, BASE_REPOSITORY, BASE_REVISION


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path):
    with open(path, encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)


def base_checkpoint():
    from huggingface_hub import hf_hub_download
    return hf_hub_download(BASE_REPOSITORY, BASE_FILENAME, revision=BASE_REVISION)


def checked_checkpoint(path=None, expected_sha=None):
    if not path:
        return base_checkpoint()
    path = Path(path)
    if not path.is_file() or path.suffix != ".nemo":
        raise ValueError("model_path_must_be_existing_nemo")
    if not expected_sha:
        raise ValueError("custom_checkpoint_requires_sha256")
    if sha256_file(path) != expected_sha:
        raise ValueError("checkpoint_sha256_mismatch")
    return str(path)
