# /// script
# requires-python = ">=3.10"
# ///
"""Run src/prefect/flow.py on a regular (non-preemptible) CPU job.

The GPU jobs are spot and can be preempted; the flow that retries them must
not be. Here the flow runs on an on-demand CPU VM, so your machine does not
have to stay on.

    uv run prefect_pipeline.py --bucket-id storagebucket-... \\
        --credentials ~/.nebius/spot-flow-credentials.json \\
        --prefect-api-url https://<prefect-server>/api
"""

import argparse
from pathlib import Path

from src.nebius_jobs import (
    DEFAULT_MAX_HOURS,
    GPU_TIMEOUT_HOURS,
    create_cpu_job,
    new_run_name,
)

PREFECT_TOKEN_PATH = "/secrets/prefect-token"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket-id", required=True)
    parser.add_argument(
        "--credentials",
        type=Path,
        required=True,
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
    parser.add_argument("--prefect-api-url", help="Passed on to the flow.")
    parser.add_argument(
        "--prefect-token-file",
        type=Path,
        default=Path.home() / ".prefect" / "token",
        help="Copied into the job when --prefect-api-url is set.",
    )
    args = parser.parse_args()

    command = [
        "uv", "run", "/app/src/prefect/flow.py",
        "--bucket-id", args.bucket_id,
        "--run-name", args.run_name,
        "--max-hours", str(args.max_hours),
    ]
    extra_files = {}
    if args.prefect_api_url:
        command += ["--prefect-api-url", args.prefect_api_url]
        if args.prefect_token_file.exists():
            command += ["--prefect-token-file", PREFECT_TOKEN_PATH]
            extra_files[args.prefect_token_file] = PREFECT_TOKEN_PATH

    # No new attempt starts after max_hours, but the last one may still run
    # to its own timeout.
    timeout_hours = args.max_hours + GPU_TIMEOUT_HOURS

    job_id = create_cpu_job(
        f"{args.run_name}-flow", command, args.credentials, timeout_hours, extra_files
    )
    print(f"Created {job_id}. Logs: nebius ai job logs {job_id} --follow")


if __name__ == "__main__":
    main()
