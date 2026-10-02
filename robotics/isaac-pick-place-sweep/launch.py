"""Submit one Nebius AI Job per Franka pick-and-place sweep point."""

import argparse
import itertools
import json
import math
import re
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def expand_sweep(config):
    axes = ("pick_x", "place_y")
    if set(config) != set(axes):
        raise ValueError("sweep.json must contain only pick_x and place_y")
    for axis in axes:
        values = config[axis]
        if not isinstance(values, list) or not values or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in values
        ):
            raise ValueError(f"{axis} must be a nonempty list of finite numbers")
    return [dict(zip(axes, values)) for values in itertools.product(*(config[axis] for axis in axes))]


def job_command(options, run_id, case_id, point):
    container_args = shlex.join(
        [
            "/opt/isaac-sweep/run.py",
            "--run-id", run_id,
            "--case-id", case_id,
            "--pick-x", str(point["pick_x"]),
            "--place-y", str(point["place_y"]),
        ]
    )
    command = [
        "nebius", "ai", "job", "create",
        "--name", f"isaac-pick-{run_id}-{case_id}",
        "--image", options.image,
        "--container-command", "/isaac-sim/python.sh",
        "--platform", options.platform,
        "--preset", options.preset,
        "--disk-size", "250Gi",
        "--timeout", options.timeout,
        "--env", "ACCEPT_EULA=Y",
        "--env", f"S3_BUCKET={options.bucket}",
        "--env", f"S3_ENDPOINT_URL={options.endpoint}",
        "--env", f"AWS_DEFAULT_REGION={options.region}",
        "--env", f"S3_PREFIX={options.prefix.strip('/')}",
        "--env-secret", f"AWS_ACCESS_KEY_ID={options.access_key_secret}",
        "--env-secret", f"AWS_SECRET_ACCESS_KEY={options.secret_key_secret}",
        "--args", container_args,
        "--format", "jsonpath={.metadata.id}",
    ]
    if options.subnet_id:
        command.extend(["--subnet-id", options.subnet_id])
    if options.profile:
        command.extend(["--profile", options.profile])
    return command


def job_id_from_output(output):
    ids = set(re.findall(r"\baijob-[a-z0-9]+\b", output))
    if len(ids) != 1:
        raise ValueError(f"expected one job ID in CLI output, found {len(ids)}")
    return ids.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("sweep.json"))
    parser.add_argument("--image", required=True, help="pushed image built from this recipe's Dockerfile")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--endpoint", required=True, help="S3 endpoint URL")
    parser.add_argument("--region", required=True)
    parser.add_argument("--access-key-secret", required=True, help="MysteryBox selector for AWS_ACCESS_KEY_ID")
    parser.add_argument("--secret-key-secret", required=True, help="MysteryBox selector for AWS_SECRET_ACCESS_KEY")
    parser.add_argument("--prefix", default="isaac-pick-place")
    parser.add_argument("--platform", default="gpu-l40s-a")
    parser.add_argument("--preset", default="1gpu-8vcpu-32gb")
    parser.add_argument("--timeout", default="2h")
    parser.add_argument("--subnet-id")
    parser.add_argument("--profile", help="Nebius CLI profile (defaults to the active profile)")
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args()

    if not options.prefix.strip("/"):
        parser.error("--prefix must contain a path component")
    try:
        points = expand_sweep(json.loads(options.config.read_text()))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    manifest = Path(__file__).with_name("runs") / run_id / "jobs.jsonl"
    if not options.dry_run:
        manifest.parent.mkdir(parents=True)
    print(f"run_id={run_id} jobs={len(points)}", flush=True)
    for index, point in enumerate(points):
        case_id = f"case-{index:03d}"
        command = job_command(options, run_id, case_id, point)
        uri = f"s3://{options.bucket}/{options.prefix.strip('/')}/{run_id}/{case_id}/"
        if options.dry_run:
            print(shlex.join(command))
            continue
        try:
            created = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            print(exc.stderr, file=sys.stderr)
            raise SystemExit(f"submission stopped; earlier job IDs are in {manifest}") from exc
        try:
            job_id = job_id_from_output(created.stdout + created.stderr)
        except ValueError as exc:
            raise SystemExit(f"{exc}; inspect Nebius Jobs before retrying; earlier IDs are in {manifest}") from exc
        with manifest.open("a") as output:
            output.write(json.dumps({"case_id": case_id, "params": point, "job_id": job_id, "s3_uri": uri}) + "\n")
        print(f"{case_id} {job_id} {uri}", flush=True)
    if not options.dry_run:
        print(f"job manifest: {manifest}")


if __name__ == "__main__":
    main()
