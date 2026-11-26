"""Axolotl plugin: copy every checkpoint to the bucket, save one on SIGTERM.

Enabled by `plugins:` in config.yaml (the job sets PYTHONPATH=/app).

- Each checkpoint the Trainer saves is copied to `$CKPT_DIR/checkpoint-N`,
  then a `COMPLETE` file is written into it. A folder without the marker
  is a partial copy and is ignored on resume.
- On SIGTERM (the spot VM is being stopped), the Trainer saves one more
  checkpoint after the current step, then the process exits.
"""

import os
import shutil
import signal
import sys
from pathlib import Path

from axolotl.integrations.base import BasePlugin
from transformers import TrainerCallback

CKPT_DIR = Path(os.environ["CKPT_DIR"])
MARKER = "COMPLETE"


def copy_dir(src: Path, dst: Path) -> None:
    """Copy a directory tree, file contents only.

    The bucket mount rejects chmod and utime, so `shutil.copytree` fails there.
    """
    for path in sorted(src.rglob("*")):
        target = dst / path.relative_to(src)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def upload(checkpoint: Path) -> None:
    """Copy a checkpoint to the bucket, mark it complete, drop older ones."""
    target = CKPT_DIR / checkpoint.name
    copy_dir(checkpoint, target)
    (target / MARKER).write_text("ok")
    print(f"copied {checkpoint.name} to the bucket", flush=True)
    for old in CKPT_DIR.glob("checkpoint-*"):
        if old != target:
            shutil.rmtree(old, ignore_errors=True)


class SaveToBucket(TrainerCallback):
    """Trainer callback that uploads checkpoints and handles SIGTERM."""

    def __init__(self) -> None:
        self.stopping = False
        signal.signal(signal.SIGTERM, self.on_sigterm)

    def on_sigterm(self, signum, frame) -> None:
        # Only set a flag; the Trainer saves at the end of the current step.
        self.stopping = True

    def on_step_end(self, args, state, control, **kwargs):
        if self.stopping:
            print("SIGTERM: saving a last checkpoint", flush=True)
            control.should_save = True
            control.should_training_stop = True
        return control

    def on_save(self, args, state, control, **kwargs):
        upload(Path(args.output_dir) / f"checkpoint-{state.global_step}")
        if self.stopping:
            sys.exit(128 + signal.SIGTERM)  # the usual "terminated" exit code
        return control


class CheckpointPlugin(BasePlugin):
    """Registers SaveToBucket with the Trainer Axolotl builds."""

    def add_callbacks_post_trainer(self, cfg, trainer):
        return [SaveToBucket()]
