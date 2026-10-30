"""Verify downloaded final adapters against their publication receipt (Python 3.11+)."""

import hashlib
import json
from pathlib import Path
import re
import sys


def verify(root: Path) -> None:
    receipt = json.loads((root / "TRAIN_COMPLETE.json").read_text())
    selected = receipt["selected_checkpoint"]
    if receipt["status"] != "trained" or not re.fullmatch(r"checkpoints/[0-9]+/pretrained_model", selected):
        raise ValueError("receipt does not identify a trained final checkpoint")
    checkpoint = (root / selected).parent
    marker = json.loads((checkpoint / "COMPLETE.json").read_text())
    if marker["step"] != receipt["microsteps"] or marker["calibration_id"] != receipt["calibration_id"]:
        raise ValueError("checkpoint step or calibration differs from receipt")
    recorded = receipt["checkpoints"][-1]
    if recorded["step"] != marker["step"] or int(checkpoint.name) != marker["step"]:
        raise ValueError("final checkpoint step differs from receipt")
    for folder, key in (("pretrained_model", "adapter_sha256"),
                        ("pretrained_model_ema", "ema_adapter_sha256")):
        path = checkpoint / folder / "adapter_model.safetensors"
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != marker[key] or digest != recorded[key]:
            raise ValueError(f"SHA-256 mismatch: {path}")
        print(f"Verified {path.relative_to(root)}: {digest}")
    print(f"PASS: {receipt['microsteps']} microsteps; raw and EMA adapter hashes match. Policy quality was not evaluated.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 scripts/verify.py RESULTS_DIRECTORY")
    verify(Path(sys.argv[1]))
