# /// script
# requires-python = ">=3.10"
# ///
"""Imitate a spot preemption: stop the VM under a running GPU job.

Waits until the job is RUNNING, then stops the job's VM with
`nebius compute instance stop`, as a spot preemption does. The container
gets SIGTERM, then SIGKILL a few seconds later; the checkpoint plugin saves
a checkpoint in between.

On a spot job the platform reports this as a preemption: the job ends
FAILED with code Preempted, so flow.py and run_supervisor.py start the
next attempt, which resumes from that checkpoint. (On an on-demand job it
ends ERROR with code VMStopped, which is not retried.)

    uv run simulate_job_preemption.py aijob-...

Uses the active Nebius profile.
"""

import argparse
import subprocess
import sys
import time

from src.nebius_jobs import FINAL_STATES, POLL_SECONDS, end_reason, nebius


def wait_for_state(job_id: str, states: set[str]) -> dict:
    """Poll the job until its state is one of `states`. Return its status."""
    while True:
        status = nebius("ai", "job", "get", job_id)["status"]
        if status["state"] in states:
            return status
        time.sleep(POLL_SECONDS)


def vm_of(status: dict) -> str:
    """The id of the VM under the job, or "" before it has one."""
    instances = status.get("instances") or []
    return instances[0].get("compute_instance_id", "") if instances else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", help="The GPU job to preempt: aijob-...")
    job_id = parser.parse_args().job_id

    print(f"{job_id}: waiting for RUNNING")
    status = wait_for_state(job_id, {"RUNNING"} | FINAL_STATES)
    vm = vm_of(status)
    if status["state"] != "RUNNING" or not vm:
        print(f"{job_id} is {status['state']}; no VM to stop")
        return 1

    print(f"stopping {vm} under {job_id}")
    stop = subprocess.run(["nebius", "compute", "instance", "stop", "--id", vm])
    # The stop can fail with OperationAborted when the platform takes over
    # the VM's shutdown. The VM still stops, so keep watching the job.
    if stop.returncode != 0:
        print("stop returned an error; checking whether the job ends anyway")

    status = wait_for_state(job_id, FINAL_STATES)
    print(f"{job_id} ended {status['state']} {end_reason(status)}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
