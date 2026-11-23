# /// script
# requires-python = ">=3.10"
# dependencies = ["prefect==3.9.4"]
# ///
"""Fine-tune Qwen2.5-0.5B with Axolotl on a spot H100, as a Prefect flow.

The fine-tune is one Prefect task that creates a Nebius job with the
`nebius` CLI and waits for it. If the spot VM is preempted, or no spot VM
is free, Prefect retries the task: a new job resumes from the last
checkpoint in the bucket. Any other failure fails the flow.

    uv run src/prefect/flow.py --bucket-id storagebucket-...

Add `--prefect-api-url` to report to a remote Prefect server or Prefect
Cloud. Its credentials are read from `~/.prefect/token`.
"""

import argparse
import sys
import time
from pathlib import Path

from prefect import flow, get_run_logger, task
from prefect.artifacts import create_link_artifact
from prefect.context import get_run_context
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    temporary_settings,
)

# This file runs as a script from src/prefect/. Put the example's folder on
# the import path, as it is for the scripts at the top.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.nebius_jobs import (  # noqa: E402
    DEFAULT_MAX_HOURS,
    RETRY_DELAY_SECONDS,
    RETRY_REASONS,
    console_url,
    create_gpu_job,
    end_reason,
    new_run_name,
    wait_for_job,
)


class SpotUnavailable(Exception):
    """The spot VM was taken away, or none was free. The task is retried."""


def should_retry(task, task_run, state) -> bool:
    """Retry only when the spot VM was unavailable.

    Prefect calls this with the failed task run's final state.
    """
    return isinstance(state.result(raise_on_failure=False), SpotUnavailable)


@task(retry_delay_seconds=RETRY_DELAY_SECONDS, retry_condition_fn=should_retry)
def fine_tune(run_name: str, bucket_id: str, deadline: float) -> str:
    """Run one GPU job until it ends. Return its id if it completed.

    After `deadline` (a time.time() value), an unavailable spot VM is no
    longer retried.
    """
    log = get_run_logger()
    attempt = get_run_context().task_run.run_count
    job_id = create_gpu_job(f"{run_name}-{attempt}", run_name, bucket_id)
    log.info("attempt %d: created %s", attempt, job_id)

    # A link to the job on the flow run's Artifacts tab, one per attempt.
    create_link_artifact(
        key=f"attempt-{attempt}",
        link=console_url(job_id),
        link_text=job_id,
        description=f"Attempt {attempt} of run {run_name}",
    )

    status = wait_for_job(job_id, log)
    if status["state"] == "COMPLETED":
        return job_id

    reason = end_reason(status)
    if reason not in RETRY_REASONS:
        raise RuntimeError(f"{job_id} ended {status['state']} {reason}")
    if time.time() > deadline:
        raise RuntimeError(f"{job_id} ended {reason}; no time left to retry")
    raise SpotUnavailable(f"{job_id} ended {reason}")


@flow(name="spot-axolotl", flow_run_name="{run_name}")
def pipeline(run_name: str, bucket_id: str, max_hours: int = DEFAULT_MAX_HOURS) -> str:
    """Fine-tune, starting a new GPU job whenever the spot VM was unavailable.

    No new attempt starts after `max_hours`.
    """
    deadline = time.time() + max_hours * 3600
    # Prefect needs a number of retries. Each attempt takes at least the
    # retry delay, so this many cannot run out before the deadline does.
    retries = max_hours * 3600 // RETRY_DELAY_SECONDS
    return fine_tune.with_options(retries=retries)(run_name, bucket_id, deadline)


def prefect_settings(api_url: str | None, token_file: Path) -> dict:
    """Settings to reach a remote Prefect, or none for a temporary local one."""
    if api_url is None:
        return {}
    settings = {PREFECT_API_URL: api_url}
    if token_file.exists():
        token = token_file.read_text().strip()
        # Prefect Cloud takes an API key; a self-hosted server "user:password".
        if "api.prefect.cloud" in api_url:
            settings[PREFECT_API_KEY] = token
        else:
            settings[PREFECT_API_AUTH_STRING] = token
    return settings
