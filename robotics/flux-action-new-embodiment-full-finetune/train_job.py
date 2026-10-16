"""Prepare the example, train on one GPU, and publish checkpoints and export."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import torch

from flux_action.training.checkpoint import export_policy, latest_checkpoint
from flux_action.training.distributed import init_distributed
from flux_action.training.trainer import TrainConfig, Trainer

from prepare import prepare

WORK = Path("/workspace/work")


def copy_files(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file() and path.name != "COMPLETE":
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            if target.stat().st_size != path.stat().st_size:
                raise IOError(f"incomplete copy: {target}")


class PublishingTrainer(Trainer):
    """Copy each checkpoint to the bucket only after the trainer completes it."""

    def __init__(self, config: TrainConfig, destination: Path):
        super().__init__(config)
        self.destination = destination

    def _checkpoint(self) -> None:
        super()._checkpoint()
        checkpoint = latest_checkpoint(self.output_dir)
        if checkpoint is None:
            raise RuntimeError("trainer did not write a complete checkpoint")
        target = self.destination / "checkpoints" / checkpoint.name
        copy_files(checkpoint, target)
        shutil.copyfile(checkpoint / "COMPLETE", target / "COMPLETE")
        shutil.copyfile(self.output_dir / "metrics.jsonl", self.destination / "metrics.jsonl")
        print(f"Published {checkpoint.name}", flush=True)


def worker() -> None:
    run_name = os.environ["RUN_NAME"]
    result = Path("/workspace/data/runs") / run_name
    if not (result / "PREPARED.json").is_file():
        raise FileNotFoundError("dataset preparation has not completed")
    if torch.cuda.device_count() != 1:
        raise RuntimeError("this example needs one visible GPU")
    init_distributed()
    config = TrainConfig.from_file(WORK / "train.json")
    PublishingTrainer(config, result).run()
    checkpoint = latest_checkpoint(config.output_dir)
    if checkpoint is None or checkpoint.name != f"step-{config.steps}":
        raise RuntimeError(f"missing final step-{config.steps} checkpoint")
    export = WORK / "export"
    export_policy(checkpoint, export, profile="model", dtype="bfloat16")
    copy_files(export, result / "export")
    model = result / "export" / "model.safetensors"
    if not model.is_file():
        raise FileNotFoundError(f"exported weights missing: {model}")
    with model.open("rb") as stream:
        model_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    receipt = {
        "status": "trained", "run_name": run_name, "optimizer_updates": config.steps,
        "checkpoint": f"checkpoints/{checkpoint.name}",
        "export": "export", "export_model_sha256": model_hash,
        "quality_evaluation": "pending",
    }
    (result / "TRAIN_COMPLETE.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "worker":
        worker()
        return
    prepare(mode)
    subprocess.run([
        "torchrun", "--standalone", "--nnodes=1", "--nproc-per-node=1",
        "/app/cookbook/train_job.py", "worker",
    ], check=True)


if __name__ == "__main__":
    main()
