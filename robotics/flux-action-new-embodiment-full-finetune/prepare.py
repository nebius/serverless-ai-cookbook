"""Download a pinned LeRobot example and build its new-embodiment index."""

import json
import os
import re
from pathlib import Path

from huggingface_hub import snapshot_download

from flux_action.data.lerobot.index import feature_names, index_dataset

HERE = Path(__file__).resolve().parent
WORK = Path("/workspace/work")
BUCKET = Path("/workspace/data")


def prepare(mode: str) -> Path:
    if mode not in {"smoke", "full"}:
        raise ValueError("mode must be smoke or full")
    run_name = os.environ["RUN_NAME"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_name):
        raise ValueError("RUN_NAME must contain only letters, digits, dash and underscore")
    if not BUCKET.is_dir():
        raise FileNotFoundError(f"Object Storage mount is missing: {BUCKET}")
    result = BUCKET / "runs" / run_name
    result.mkdir(parents=True, exist_ok=False)
    WORK.mkdir(parents=True, exist_ok=True)

    recipe = json.loads((HERE / "recipe.json").read_text())
    contract = recipe["dataset"]
    source = WORK / "source"
    snapshot_download(
        repo_id=contract["repo_id"],
        revision=contract["revision"],
        repo_type="dataset",
        local_dir=source,
        allow_patterns=["meta/**", "data/**", "videos/**"],
    )
    info = json.loads((source / "meta" / "info.json").read_text())
    expected = {"robot_type": contract["robot_type"], "total_episodes": contract["episodes"],
                "total_frames": contract["frames"], "fps": contract["fps"]}
    for key, value in expected.items():
        if info.get(key) != value:
            raise ValueError(f"dataset {key}: expected {value!r}, got {info.get(key)!r}")
    names = contract["channels"]
    for key in (contract["state_key"], contract["action_key"]):
        actual = feature_names(info["features"][key], len(names))
        if actual != names:
            raise ValueError(f"dataset {key} channel order differs from recipe: {actual}")
    for feature in contract["cameras"].values():
        if info["features"][feature]["dtype"] != "video":
            raise ValueError(f"dataset camera is not a video: {feature}")

    config = json.loads((HERE / "train.json").read_text())
    policy = config["policy"]
    if (policy["action_dim"] != len(names) or policy["fps"] != contract["fps"]
            or policy["camera_keys"] != [f"images.{key}" for key in contract["cameras"]]
            or policy["action_parameterization"] != recipe["action_parameterization"]
            or policy["absolute_action_dims"] != recipe["absolute_action_dims"]):
        raise ValueError("train.json does not match the embodiment contract")
    revision = recipe["base"]["revision"]
    if any(f"@{revision}" not in policy[key] for key in ("trunk_weights", "video_vae_id", "text_encoder_id")):
        raise ValueError("train.json does not pin the selected action-pretrained base")
    summary = index_dataset(
        source, WORK / "index", contract["cameras"],
        state_key=contract["state_key"], action_key=contract["action_key"],
        chunk_size=policy["chunk_size"], val_episodes=contract["val_episodes"],
        dataset_id=contract["repo_id"], revision=contract["revision"],
        action_parameterization=recipe["action_parameterization"],
        absolute_action_dims=recipe["absolute_action_dims"], hash_files=True,
    )
    counts = summary["counts"]
    if counts["train_episodes"] < 1 or counts["val_episodes"] != contract["val_episodes"]:
        raise ValueError(f"index has insufficient train/validation episodes: {counts}")
    if mode == "smoke":
        config.update(steps=4, frozen_steps=0, trunk_warmup_steps=1,
                      heads_warmup_steps=1, cooldown_start=None, cooldown_steps=0,
                      checkpoint_every=4, log_every=1)
    (WORK / "train.json").write_text(json.dumps(config, indent=2) + "\n")
    for name in ("manifest.json", "statistics.json"):
        (result / name).write_bytes((WORK / "index" / name).read_bytes())
    (result / "train.json").write_bytes((WORK / "train.json").read_bytes())
    (result / "recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    (result / "PREPARED.json").write_text(json.dumps({
        "run_name": run_name, "mode": mode, "image": os.environ.get("IMAGE_REF"),
        "gpu_count": 1,
        "dataset": contract["repo_id"], "dataset_revision": contract["revision"],
        "base_revision": revision, "index": summary,
    }, indent=2) + "\n")
    return result
