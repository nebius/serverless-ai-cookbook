"""One Nebius GPU job: prepare public data, run BFL's SO-101 LoRA, publish checkpoints."""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from calibration import ID as CALIBRATION_ID, check_model_overlap
from prepare_dataset import prepare
from publish import publish

HERE = Path(__file__).resolve().parent
RECIPE = json.loads((HERE / "recipe.json").read_text())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wandb_options(run_name: str) -> list[str]:
    if not os.environ.get("WANDB_API_KEY"):
        return []
    options = [
        "--wandb.enable=true",
        "--wandb.disable_artifact=true",
        f"--wandb.project={os.environ.get('WANDB_PROJECT') or 'flux-so101-orange'}",
        f"--job_name={run_name}",
    ]
    if entity := os.environ.get("WANDB_ENTITY"):
        options.append(f"--wandb.entity={entity}")
    return options


def training_steps(mode: str) -> int:
    if mode == "smoke":
        return 100
    value = os.environ.get("FULL_STEPS", "10000")
    if not re.fullmatch(r"[1-9][0-9]*", value) or int(value) < 10_000 or int(value) % 5_000:
        raise SystemExit("FULL_STEPS must be at least 10000 and a multiple of 5000")
    return int(value)


def download_models(work: Path) -> tuple[Path, Path]:
    from huggingface_hub import snapshot_download

    policy = work / "models/so101"
    encoders = work / "models/base"
    snapshot_download(
        RECIPE["policy"]["repo_id"],
        revision=RECIPE["policy"]["revision"],
        local_dir=policy,
        ignore_patterns=["variants/*"],
    )
    snapshot_download(
        RECIPE["encoders"]["repo_id"],
        revision=RECIPE["encoders"]["revision"],
        local_dir=encoders,
        allow_patterns=["video_vae.safetensors", "text_encoder/*"],
    )
    from lerobot.policies.flux3.configuration_flux3 import Flux3Config

    config = Flux3Config.from_pretrained(policy)
    if (config.action_dim, config.fps, config.camera_order) != (
        6, 30, ["observation.images.scene", "observation.images.wrist"]
    ):
        raise ValueError("downloaded checkpoint does not match the SO-101 contract")
    if not (policy / "policy_preprocessor.json").is_file():
        raise FileNotFoundError("SO-101 preprocessor is missing")
    if not (policy / "policy_postprocessor.json").is_file():
        raise FileNotFoundError("SO-101 postprocessor is missing")
    if not (encoders / "video_vae.safetensors").is_file():
        raise FileNotFoundError("shared video VAE is missing")
    return policy, encoders


def train(work: Path, result: Path, policy: Path, encoders: Path, steps: int) -> list[dict]:
    output = work / "trainer"
    command = [
        sys.executable, "-m", "lerobot.scripts.lerobot_train",
        "--config_path=/opt/lerobot/examples/flux3/lora.json",
        f"--policy.path={policy}",
        "--policy.device=cuda",
        f"--policy.video_vae_id={encoders / 'video_vae.safetensors'}",
        f"--policy.text_encoder_id={encoders / 'text_encoder'}",
        f"--dataset.repo_id={RECIPE['dataset']['repo_id']}",
        f"--dataset.root={work / 'dataset'}",
        f"--dataset.revision={RECIPE['dataset']['revision']}",
        "--dataset.video_backend=pyav",
        '--rename_map={"observation.images.front":"observation.images.scene"}',
        f"--steps={steps}",
        f"--save_freq={steps if steps < 500 else 500 if steps == 10_000 else 5000}",
        f"--eval_steps={steps if steps >= 10_000 else 0}",
        f"--output_dir={output}",
        *wandb_options(os.environ["RUN_NAME"]),
    ]
    (result / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    stop = threading.Event()
    errors = []

    def watch() -> None:
        while not stop.wait(30):
            try:
                publish(output, result, CALIBRATION_ID)
            except Exception as error:
                errors.append(error)
                return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    log_path = work / "train.log"
    try:
        with log_path.open("w") as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                log.write(line)
                log.flush()
            status = process.wait()
    finally:
        stop.set()
        watcher.join()
        if log_path.is_file():
            shutil.copyfile(log_path, result / "train.log")
    if errors:
        raise RuntimeError(f"checkpoint publication failed: {errors[0]}") from errors[0]
    published = publish(output, result, CALIBRATION_ID)
    if status != 0:
        raise RuntimeError(f"LeRobot trainer exited {status}")
    if not published or published[-1]["step"] != steps:
        raise RuntimeError(f"trainer exited without complete step-{steps} checkpoint")
    return published


def main() -> None:
    mode = os.environ.get("RUN_MODE")
    run_name = os.environ.get("RUN_NAME", "")
    if mode not in {"smoke", "full"}:
        raise SystemExit("RUN_MODE must be smoke or full")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_name):
        raise SystemExit("RUN_NAME must be letters, digits, dash, or underscore")
    bucket = Path(os.environ.get("ARTIFACT_ROOT", "/workspace/data"))
    if not bucket.is_dir():
        raise FileNotFoundError(f"Object Storage mount is missing: {bucket}")
    result = bucket / "runs" / run_name
    result.mkdir(parents=True, exist_ok=False)
    steps = training_steps(mode)
    record = {
        "run_name": run_name,
        "mode": mode,
        "started_utc": now(),
        "image": os.environ.get("IMAGE_REF"),
        "recipe": RECIPE,
        "microsteps": steps,
        "optimizer_updates": steps // 4,
        "calibration_id": CALIBRATION_ID,
    }
    work = Path("/workspace/work")
    work.mkdir(parents=True, exist_ok=False)
    report = prepare(work / "dataset", RECIPE["dataset"], result, RECIPE["instruction"])
    policy, encoders = download_models(work)
    overlap = check_model_overlap(work / "dataset", policy, result / "calibration-report.json")
    if overlap["frames"] != RECIPE["dataset"]["frames"]:
        raise ValueError("calibrated dataset frame count mismatch")
    started = time.monotonic()
    published = train(work, result, policy, encoders, steps)
    selected_checkpoint = f"checkpoints/{published[-1]['directory']}/pretrained_model"
    if not (result / selected_checkpoint).is_dir():
        raise FileNotFoundError(f"published checkpoint missing: {selected_checkpoint}")
    record.update({
        "status": "trained",
        "finished_utc": now(),
        "train_seconds": round(time.monotonic() - started, 2),
        "dataset_report": report,
        "calibration_report": overlap,
        "checkpoints": published,
        "selected_checkpoint": selected_checkpoint,
        "quality_evaluation": "pending",
    })
    (result / "TRAIN_COMPLETE.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
