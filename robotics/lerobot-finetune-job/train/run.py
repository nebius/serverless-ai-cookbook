"""Fine-tune a LeRobot policy and optionally upload the checkpoint to S3."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

import typer
from pydantic import BaseModel, Field, ValidationError, field_validator
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    import boto3
    from botocore.config import Config as BotoConfig

    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False

console = Console(force_terminal=True)
app = typer.Typer(add_completion=False, no_args_is_help=True)


class Policy(str, Enum):
    ACT = "act"
    DIFFUSION = "diffusion"


class TrainConfig(BaseModel):
    policy: Policy = Policy.ACT
    dataset: str = Field(default="lerobot/pusht", min_length=1)
    env: str | None = None
    steps: int = Field(default=5000, gt=0)
    batch_size: int = Field(default=8, gt=0)
    eval_episodes: int = Field(default=0, ge=0)
    output_dir: Path | None = None

    @property
    def dataset_slug(self) -> str:
        return self.dataset.replace("/", "-")


class S3Config(BaseModel):
    bucket: str
    prefix: str = "lerobot"
    endpoint_url: str | None = None
    region: str = "eu-north1"
    access_key: str
    secret_key: str

    @field_validator("prefix")
    @classmethod
    def _normalize_prefix(cls, value: str) -> str:
        return value.rstrip("/")

    @classmethod
    def from_env(cls) -> S3Config | None:
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        bucket = os.environ.get("S3_BUCKET")
        if not all([access_key, secret_key, bucket]):
            return None
        return cls(
            bucket=bucket,
            prefix=os.environ.get("S3_PREFIX", "lerobot"),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
            region=os.environ.get("AWS_DEFAULT_REGION", "eu-north1"),
            access_key=access_key,
            secret_key=secret_key,
        )


def _build_train_cmd(
    cfg: TrainConfig,
    output_dir: Path,
    *,
    job_name: str | None = None,
    wandb_project: str | None = None,
    wandb_entity: str | None = None,
) -> list[str]:
    """Build the LeRobot training command."""
    venv_bin = Path(sys.executable).parent
    lerobot_train = venv_bin / "lerobot-train"
    if lerobot_train.is_file():
        base: list[str] = [str(lerobot_train)]
    else:
        import importlib.util

        module = (
            "lerobot.scripts.lerobot_train"
            if importlib.util.find_spec("lerobot.scripts.lerobot_train") is not None
            else "lerobot.scripts.train"
        )
        base = [sys.executable, "-m", module]

    wandb_on = bool(os.environ.get("WANDB_API_KEY"))
    flags: list[str] = [
        f"--policy.type={cfg.policy.value}",
        "--policy.push_to_hub=false",
        f"--dataset.repo_id={cfg.dataset}",
        f"--steps={cfg.steps}",
        f"--batch_size={cfg.batch_size}",
        f"--output_dir={output_dir}",
        f"--wandb.enable={'true' if wandb_on else 'false'}",
    ]
    if cfg.env:
        flags.append(f"--env.type={cfg.env}")
    if cfg.eval_episodes > 0 and cfg.env:
        flags.append(f"--eval.n_episodes={cfg.eval_episodes}")
    if wandb_on:
        if job_name:
            flags.append(f"--job_name={job_name}")
        if wandb_project:
            flags.append(f"--wandb.project={wandb_project}")
        if wandb_entity:
            flags.append(f"--wandb.entity={wandb_entity}")
    return base + flags


def _make_s3_client(cfg: S3Config | None):
    if cfg is None:
        console.print("[yellow]S3 upload skipped — missing env vars.[/yellow]")
        return None
    if not _BOTO3_AVAILABLE:
        console.print("[yellow]boto3 not installed — S3 upload skipped.[/yellow]")
        return None
    return boto3.client(
        "s3",
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key,
        region_name=cfg.region,
        endpoint_url=cfg.endpoint_url,
        config=BotoConfig(region_name=cfg.region),
    )


def _upload_checkpoint(output_dir: Path, cfg: S3Config | None) -> bool:
    client = _make_s3_client(cfg)
    if client is None:
        return False
    try:
        client.head_bucket(Bucket=cfg.bucket)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Cannot access bucket '{cfg.bucket}': {exc}[/yellow]")
        return False

    files = [p for p in output_dir.rglob("*") if p.is_file()]
    console.print(
        f"\nUploading {len(files)} files to s3://{cfg.bucket}/{cfg.prefix}/{output_dir.name}/"
    )
    for local_path in files:
        key = f"{cfg.prefix}/{output_dir.name}/{local_path.relative_to(output_dir).as_posix()}"
        client.upload_file(str(local_path), cfg.bucket, key)
        console.print(f"  {local_path.relative_to(output_dir)}")

    s3_path = f"s3://{cfg.bucket}/{cfg.prefix}/{output_dir.name}/"
    console.print(f"\nCheckpoint saved to {s3_path}")
    console.print(f'Download: aws s3 sync "{s3_path}" "./{output_dir.name}/"')
    return True


def _print_summary(cfg: TrainConfig, output_dir: Path, s3_cfg: S3Config | None) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_row("Policy", cfg.policy.value)
    table.add_row("Dataset", cfg.dataset)
    table.add_row("Steps", str(cfg.steps))
    table.add_row("Batch size", str(cfg.batch_size))
    if cfg.env:
        table.add_row("Env", cfg.env)
    if cfg.eval_episodes > 0:
        table.add_row("Eval episodes", str(cfg.eval_episodes))
    table.add_row("Output", str(output_dir))
    if s3_cfg:
        table.add_row("S3 bucket", s3_cfg.bucket)
        table.add_row("S3 prefix", s3_cfg.prefix)
    console.print(Panel(table, title="LeRobot Fine-tuning Job", expand=False))


@app.command()
def main(
    policy: Policy = typer.Option(Policy.ACT, "--policy", help="Policy architecture."),
    dataset: str = typer.Option(
        "lerobot/pusht", "--dataset", help="HuggingFace dataset repo_id."
    ),
    env: str | None = typer.Option(
        None, "--env", help="Environment for in-training evaluation (optional)."
    ),
    steps: int = typer.Option(5000, "--steps", help="Number of offline training steps.", min=1),
    batch_size: int = typer.Option(
        8, "--batch-size", help="Training batch size per GPU.", min=1
    ),
    eval_episodes: int = typer.Option(
        0,
        "--eval-episodes",
        help="Episodes evaluated at each checkpoint (requires --env).",
        min=0,
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Local checkpoint output directory. Auto-generated with timestamp if omitted.",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        help="Optional short suffix appended to the run/output name for disambiguation.",
    ),
    wandb_project: str | None = typer.Option(
        None,
        "--wandb-project",
        help="Override W&B project (defaults to $WANDB_PROJECT if set).",
    ),
    wandb_entity: str | None = typer.Option(
        None,
        "--wandb-entity",
        help="Override W&B entity (defaults to $WANDB_ENTITY if set).",
    ),
) -> None:
    try:
        cfg = TrainConfig(
            policy=policy,
            dataset=dataset,
            env=env,
            steps=steps,
            batch_size=batch_size,
            eval_episodes=eval_episodes,
            output_dir=output_dir,
        )
    except ValidationError as exc:
        console.print(f"[red]Invalid input:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

    run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    base_run_name = f"lerobot-{cfg.policy.value}-{cfg.dataset_slug}-{run_id}"
    run_name = f"{base_run_name}-{label}" if label else base_run_name
    target_dir = (
        cfg.output_dir
        if cfg.output_dir
        else Path("outputs") / "train" / run_name
    )
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    s3_cfg = S3Config.from_env()
    _print_summary(cfg, target_dir, s3_cfg)

    wandb_project = wandb_project or os.environ.get("WANDB_PROJECT")
    wandb_entity = wandb_entity or os.environ.get("WANDB_ENTITY")
    cmd = _build_train_cmd(
        cfg,
        target_dir,
        job_name=run_name,
        wandb_project=wandb_project,
        wandb_entity=wandb_entity,
    )
    console.print(f"[cyan]Job / W&B name:[/cyan] {run_name}")
    if wandb_project:
        console.print(f"[cyan]W&B project:[/cyan] {wandb_project}")
    if wandb_entity:
        console.print(f"[cyan]W&B entity:[/cyan] {wandb_entity}")
    # Tags skipped: lerobot-train CLI expects booleans for wandb.add_tags
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        console.print(f"[red]Training failed (exit {result.returncode}).[/red]")
        raise typer.Exit(code=result.returncode)

    if _upload_checkpoint(target_dir, s3_cfg):
        console.print("[green]S3 upload complete.[/green]")
    else:
        console.print("[yellow]S3 upload skipped.[/yellow]")


if __name__ == "__main__":
    app()
