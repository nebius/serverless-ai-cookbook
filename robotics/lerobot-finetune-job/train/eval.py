from __future__ import annotations

from pathlib import Path

import typer
from lerobot.policies.act.modeling_act import ACTPolicy
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console(force_terminal=True)


@app.command()
def main(
    checkpoint: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Path to checkpoint directory (from S3 sync).",
    ),
) -> None:
    """Load an ACT checkpoint and print a short summary."""

    console.print(f"[cyan]Loading checkpoint from[/cyan] {checkpoint}")
    config_path = checkpoint / "config.json"
    weights_path = checkpoint / "model.safetensors"
    if not config_path.exists():
        console.print(
            "[red]config.json not found in checkpoint. Sync the entire run directory from S3 (including config.json/model.safetensors).[/red]"
        )
        raise typer.Exit(code=1)
    if not weights_path.exists():
        console.print(
            "[red]model.safetensors not found in checkpoint. Sync the entire run directory from S3 (including config.json/model.safetensors).[/red]"
        )
        raise typer.Exit(code=1)

    policy = ACTPolicy.from_pretrained(checkpoint)
    policy.eval()
    console.print("[green]Loaded policy and set to eval().[/green]")
    console.print(
        "[green]- Checkpoint files (config + weights) found\n- Backbone weights downloaded/cached on first run\n- No errors during load[/green]"
    )


if __name__ == "__main__":
    app()
