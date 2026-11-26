# /// script
# requires-python = ">=3.10"
# ///
"""Retry spot GPU jobs from a supervisor CPU job. No Prefect needed.

The same script runs in two places:

- On your machine, it creates the supervisor: a regular (non-preemptible)
  CPU job that runs this script again with `--supervise`.
- In the supervisor, it runs the fine-tune on spot GPU jobs, one attempt
  at a time. After a preemption, or when no spot VM was free, it starts a
  new attempt, which resumes from the last checkpoint in the bucket. Any
  other failure stops it.

    uv run run_supervisor.py --bucket-id storagebucket-... \\
        --credentials ~/.nebius/spot-flow-credentials.json
"""

import argparse
import itertools
import logging
import sys
import time
from pathlib import Path

from src.nebius_jobs import (
    DEFAULT_MAX_HOURS,
    GPU_TIMEOUT_HOURS,
    RETRY_DELAY_SECONDS,
    RETRY_REASONS,
    create_cpu_job,
    create_gpu_job,
    end_reason,
    new_run_name,
    wait_for_job,
)

log = logging.getLogger("supervisor")


def supervise(run_name: str, bucket_id: str, max_hours: int) -> None:
    """Run GPU attempts until one completes, for at most `max_hours`.

    No new attempt starts after that; the supervisor exits non-zero instead.
    """
    deadline = time.time() + max_hours * 3600
    for attempt in itertools.count(1):
        job_id = create_gpu_job(f"{run_name}-{attempt}", run_name, bucket_id)
        log.info("attempt %d: created %s", attempt, job_id)

        status = wait_for_job(job_id, log)
        if status["state"] == "COMPLETED":
            log.info("completed %s. Adapter: spot-axolotl/%s/final/", job_id, run_name)
            return

        reason = end_reason(status)
        if reason not in RETRY_REASONS:
            sys.exit(f"{job_id} ended {status['state']} {reason}")
        if time.time() > deadline:
            sys.exit(f"{job_id} ended {reason}; no time left to retry")
        log.info("%s ended %s, retrying in %d s", job_id, reason, RETRY_DELAY_SECONDS)
        time.sleep(RETRY_DELAY_SECONDS)


def start_supervisor(args: argparse.Namespace) -> None:
    """Create the supervisor CPU job that runs `supervise()`."""
    command = [
        "python3", "/app/run_supervisor.py", "--supervise",
        "--bucket-id", args.bucket_id,
        "--run-name", args.run_name,
        "--max-hours", str(args.max_hours),
    ]
    # No new attempt starts after max_hours, but the last one may still run
    # to its own timeout.
    timeout_hours = args.max_hours + GPU_TIMEOUT_HOURS

    job_id = create_cpu_job(
        f"{args.run_name}-supervisor", command, args.credentials, timeout_hours
    )
    print(f"Created supervisor {job_id}. Logs: nebius ai job logs {job_id} --follow")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket-id", required=True)
    parser.add_argument(
        "--credentials",
        type=Path,
        help="Service account credentials from `nebius iam auth-public-key generate`.",
    )
    parser.add_argument(
        "--run-name",
        default=new_run_name(),
        help="Reuse a name to continue its checkpoints.",
    )
    parser.add_argument(
        "--max-hours",
        type=int,
        default=DEFAULT_MAX_HOURS,
        help="Stop starting new attempts after this many hours.",
    )
    parser.add_argument(
        "--supervise",
        action="store_true",
        help="Run the attempts here. Used inside the supervisor job.",
    )
    args = parser.parse_args()

    if args.supervise:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        supervise(args.run_name, args.bucket_id, args.max_hours)
    elif args.credentials is None:
        parser.error("--credentials is required to start the supervisor")
    else:
        start_supervisor(args)
