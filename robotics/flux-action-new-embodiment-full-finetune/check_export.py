"""Reload a published full-weight export and score pinned held-out windows."""

import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download

from flux_action.data.lerobot.index import index_dataset
from flux_action.inference.evaluate import evaluate_export

HERE = Path(__file__).resolve().parent
WORK = Path("/workspace/work")


def main() -> None:
    run_name = os.environ["RUN_NAME"]
    check_name = os.environ["CHECK_NAME"]
    for value in (run_name, check_name):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
            raise ValueError(f"invalid run or check name: {value!r}")
    run = Path("/workspace/data/runs") / run_name
    receipt = json.loads((run / "TRAIN_COMPLETE.json").read_text())
    if receipt["status"] != "trained" or receipt["run_name"] != run_name:
        raise ValueError("training completion receipt does not match this run")
    check = run / "checks" / check_name
    check.mkdir(parents=True, exist_ok=False)
    WORK.mkdir(parents=True, exist_ok=True)

    export = WORK / "export"
    shutil.copytree(run / receipt["export"], export)
    model = export / "model.safetensors"
    with model.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != receipt["export_model_sha256"]:
        raise ValueError("published export SHA-256 does not match the training receipt")

    recipe = json.loads((run / "recipe.json").read_text())
    contract = recipe["dataset"]
    source = WORK / "source"
    snapshot_download(
        repo_id=contract["repo_id"], revision=contract["revision"],
        repo_type="dataset", local_dir=source,
        allow_patterns=["meta/**", "data/**", "videos/**"],
    )
    index = WORK / "index"
    config = json.loads((run / "train.json").read_text())
    index_dataset(
        source, index, contract["cameras"],
        state_key=contract["state_key"], action_key=contract["action_key"],
        chunk_size=config["policy"]["chunk_size"], val_episodes=contract["val_episodes"],
        dataset_id=contract["repo_id"], revision=contract["revision"],
        action_parameterization=recipe["action_parameterization"],
        absolute_action_dims=recipe["absolute_action_dims"], hash_files=True,
    )
    if (index / "manifest.json").read_bytes() != (run / "manifest.json").read_bytes():
        raise ValueError("rebuilt dataset index differs from the published training index")
    report = evaluate_export(
        export, source, index, output=check / "offline-val.json", device="cpu",
        split="val", windows_per_episode=1, max_windows=1,
        frame_hw=tuple(config["frame_hw"]), decoder=config["decoder"],
    )
    for key in ("action_mse_normalized", "action_mse_raw"):
        if not math.isfinite(report[key]):
            raise ValueError(f"nonfinite offline evaluation metric: {key}")
    (check / "COMPLETE.json").write_text(json.dumps({
        "status": "checked", "run_name": run_name, "check_name": check_name,
        "export_model_sha256": digest, "windows": report["n_windows"],
        "device": "cpu",
        "action_mse_normalized": report["action_mse_normalized"],
        "action_mse_raw": report["action_mse_raw"],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
