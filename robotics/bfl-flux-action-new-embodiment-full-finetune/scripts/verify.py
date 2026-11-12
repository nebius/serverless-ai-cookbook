"""Verify a downloaded final checkpoint marker and BF16 export (Python 3.11+)."""

import hashlib
import json
from pathlib import Path
import sys


def verify(root: Path) -> None:
    receipt = json.loads((root / "TRAIN_COMPLETE.json").read_text())
    steps = receipt["optimizer_updates"]
    checkpoint = f"checkpoints/step-{steps}"
    if receipt["status"] != "trained" or receipt["checkpoint"] != checkpoint or receipt["export"] != "export":
        raise ValueError("receipt does not identify the trained final checkpoint and export")
    if (root / checkpoint / "COMPLETE").read_text().strip() != str(steps):
        raise ValueError("checkpoint completion marker differs from receipt")
    model = root / "export/model.safetensors"
    with model.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != receipt["export_model_sha256"]:
        raise ValueError(f"SHA-256 mismatch: {model}")
    print(f"Verified export/model.safetensors: {digest}")
    print(f"PASS: {steps} optimizer updates; export hash matches. Policy quality was not evaluated.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 scripts/verify.py RESULTS_DIRECTORY")
    verify(Path(sys.argv[1]))
