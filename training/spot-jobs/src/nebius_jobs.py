"""Create and watch Nebius AI jobs with the `nebius` CLI.

Shared by the scripts at the top of the example and by src/prefect/flow.py.
Standard library only.
"""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parent  # src/
ROOT = SRC.parent  # the example's folder
GPU_IMAGE = "docker.io/axolotlai/axolotl:main-20260309-py3.11-cu128-2.9.1"
CPU_IMAGE = "ghcr.io/astral-sh/uv:0.9.20-python3.12-bookworm"
FINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "ERROR"}
POLL_SECONDS = 30
GPU_TIMEOUT_HOURS = 2

# Why a GPU job can end and still be worth a new attempt: the spot VM was
# taken away, or there was no free VM to start it on.
RETRY_REASONS = {"Preempted", "NotEnoughResources"}
RETRY_DELAY_SECONDS = 120
# The number of attempts is not limited, only the time to keep retrying.
DEFAULT_MAX_HOURS = 12

# Local file -> path in the CPU job: the code, laid out under /app as here.
CPU_JOB_FILES = {
    ROOT / name: f"/app/{name}"
    for name in [
        "run_supervisor.py",
        "src/nebius_jobs.py",
        "src/prefect/cpu_job.sh",
        "src/prefect/flow.py",
        "src/axolotl/resumable_axolotl.py",
        "src/axolotl/checkpoint_plugin.py",
        "src/axolotl/config.yaml",
    ]
}
CREDENTIALS_PATH = "/secrets/nebius-credentials.json"


def new_run_name() -> str:
    """A name for a new run: its UTC start time and what it trains.

    Jobs are named after the run: `<run-name>-1`, `<run-name>-2`, ... for
    the GPU attempts, `<run-name>-supervisor` for the supervisor.
    """
    return f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}z-qwen05b-qlora"


def nebius(*args: str) -> dict:
    """Run a `nebius` CLI command and return its JSON output."""
    result = subprocess.run(
        ["nebius", *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def current_project_id() -> str:
    """The project of the active CLI profile."""
    result = subprocess.run(
        ["nebius", "config", "get", "parent-id"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def console_url(job_id: str) -> str:
    """The job's page in the Nebius web console."""
    project_id = current_project_id()
    return f"https://console.nebius.com/{project_id}/serverless/job/{job_id}"


def create_gpu_job(name: str, run_name: str, bucket_id: str) -> str:
    """Create one fine-tuning attempt on a spot H100 and return its id.

    Every attempt of a run uses the same checkpoint folder in the bucket,
    so a new attempt resumes where the previous one stopped. The files in
    src/axolotl/ go flat into /app, where resumable_axolotl.py finds them.
    """
    src = SRC / "axolotl"
    operation = nebius(
        "ai", "job", "create",
        "--name", name,
        "--image", GPU_IMAGE,
        "--container-command", "python",
        "--args", "-u /app/resumable_axolotl.py",
        "--platform", "gpu-h100-sxm",
        "--preset", "1gpu-16vcpu-200gb",
        "--preemptible", "--follows-spot-price",
        "--disk-size", "500Gi",
        "--timeout", f"{GPU_TIMEOUT_HOURS}h",
        "--volume", f"{bucket_id}:/ckpt:rw",
        "--env", f"CKPT_DIR=/ckpt/spot-axolotl/{run_name}",
        "--env", "PYTHONPATH=/app",
        "--inject-file", f"{src}/resumable_axolotl.py:/app/resumable_axolotl.py",
        "--inject-file", f"{src}/checkpoint_plugin.py:/app/checkpoint_plugin.py",
        "--inject-file", f"{src}/config.yaml:/app/config.yaml",
        "--async",
    )
    return operation["resource_id"]


def create_cpu_job(
    name: str,
    command: list[str],
    credentials: Path,
    timeout_hours: int,
    extra_files: dict[Path, str] | None = None,
) -> str:
    """Run `command` on a regular (non-preemptible) CPU job. Return its id.

    cpu_job.sh logs the `nebius` CLI in as the service account from
    `credentials` before running the command, so it can create GPU jobs.
    """
    files = {**CPU_JOB_FILES, credentials: CREDENTIALS_PATH, **(extra_files or {})}
    args = [
        "ai", "job", "create",
        "--name", name,
        "--image", CPU_IMAGE,
        "--container-command", "bash",
        "--args", " ".join(["/app/src/prefect/cpu_job.sh", *command]),
        "--platform", "cpu-d3",
        "--preset", "2vcpu-8gb",
        "--on-demand",
        "--disk-size", "50Gi",
        "--timeout", f"{timeout_hours}h",
        "--env", f"PROJECT_ID={current_project_id()}",
    ]
    for local, remote in files.items():
        args += ["--inject-file", f"{local}:{remote}"]
    return nebius(*args, "--async")["resource_id"]


def wait_for_job(job_id: str, log) -> dict:
    """Poll the job until it reaches a final state. Return its status.

    `log` is a logger; each state change is logged once.
    """
    last_state = None
    while True:
        time.sleep(POLL_SECONDS)
        status = nebius("ai", "job", "get", job_id)["status"]
        if status["state"] != last_state:
            last_state = status["state"]
            log.info("%s %s", job_id, last_state)
        if last_state in FINAL_STATES:
            return status


def end_reason(status: dict) -> str:
    """Why a job ended, e.g. "Preempted". Empty if the job did not say."""
    return (status.get("state_details") or {}).get("code", "")
