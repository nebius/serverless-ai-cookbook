"""The job's entry point: resume from the bucket, train, save the result.

1. Copy the newest complete `$CKPT_DIR/checkpoint-N` from the bucket into
   Axolotl's `output_dir`. config.yaml sets `auto_resume_from_checkpoints`,
   so Axolotl continues from it.
2. Run `axolotl train`, forwarding SIGTERM to it. checkpoint_plugin.py
   saves a last checkpoint and exits.
3. When training finishes, copy the adapter to `$CKPT_DIR/final`.
"""

import shutil
import signal
import subprocess
import sys
from pathlib import Path

from checkpoint_plugin import CKPT_DIR, MARKER, copy_dir

CONFIG = Path("/app/config.yaml")
OUTPUT_DIR = Path("/workspace/output")  # output_dir in config.yaml
FINAL_DIR = CKPT_DIR / "final"


def step(checkpoint: Path) -> int:
    """The training step of a `checkpoint-N` folder."""
    return int(checkpoint.name.removeprefix("checkpoint-"))


def restore() -> None:
    """Copy the latest complete checkpoint from the bucket, if there is one."""
    checkpoints = CKPT_DIR.glob("checkpoint-*")
    complete = [p for p in checkpoints if (p / MARKER).exists()]
    if not complete:
        print("no checkpoint in the bucket, starting fresh", flush=True)
        return
    latest = max(complete, key=step)
    copy_dir(latest, OUTPUT_DIR / latest.name)
    print(f"resuming from {latest.name}", flush=True)


def save_final() -> None:
    """Copy the trained adapter to the bucket and mark training done."""
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT_DIR.iterdir():
        if path.is_file():
            shutil.copyfile(path, FINAL_DIR / path.name)
    (FINAL_DIR / MARKER).write_text("ok")
    print(f"training done, adapter in {FINAL_DIR}", flush=True)


def main() -> None:
    if (FINAL_DIR / MARKER).exists():
        print("training already done in an earlier attempt", flush=True)
        return
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    restore()

    axolotl = subprocess.Popen(
        ["axolotl", "train", str(CONFIG), "--launcher", "python"]
    )
    # The platform sends SIGTERM to this process; pass it on to Axolotl.
    signal.signal(signal.SIGTERM, lambda *_: axolotl.terminate())
    code = axolotl.wait()
    if code != 0:
        # A negative code means Axolotl was killed by a signal; exit non-zero.
        sys.exit(code if code > 0 else 1)
    save_final()


if __name__ == "__main__":
    main()
