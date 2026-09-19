#!/usr/bin/env python3
"""Compare fresh scientific Pods with normal load and a registered snapshot.

Only a disposable qualification tenant's model startup choice is changed. The
prior policy is restored with revision checks. These are warm-node/fresh-Pod
measurements, not cold-node or cold-registry-cache claims. Three repetitions
are exploratory evidence, not a new 20-sample Fast Start qualification.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

from manage_campaign import admin_client, save
from qualify_worker_recovery import now


def policy_body(desired, startup, *, revision=None):
    return {"expected_revision": desired["revision"] if revision is None else revision,
            "paused": desired["paused"], "max_active_runs": desired["max_active_runs"],
            "reason": desired["reason"], "startup_policies": startup}


def observe(client, tenant, model):
    response = client.get("/admin/api/v1/scientific-model-policies", params={"tenant_id": tenant})
    response.raise_for_status()
    return next(item for item in response.json()["data"]["items"] if item["model_id"] == model)


def change(client, tenant, model, body):
    response = client.put("/admin/api/v1/scientific-model-policies/" + quote(model, safe=""),
                          params={"tenant_id": tenant}, json=body)
    response.raise_for_status()
    return response.json()["data"]["desired"]


def mechanisms(folder):
    witnesses = {}
    for path in sorted((folder / "worker-logs").glob("*.json")):
        captured = json.loads(path.read_text())
        for container in captured["containers"].values():
            for line in container["text"].splitlines():
                timestamp, _, payload = line.partition(" ")
                if '"scientific_snapshot_request"' not in payload:
                    continue
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                if event.get("event") == "scientific_snapshot_request":
                    witnesses[(captured["pod_uid"], timestamp)] = {
                        "pod_uid": captured["pod_uid"], "at": timestamp,
                        "mechanism": event.get("mechanism")}
    return list(witnesses.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientists", required=True, type=Path)
    parser.add_argument("--scientist", required=True)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=3, choices=range(1, 21))
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    person = next(p for p in json.loads(args.scientists.read_text())["scientists"] if p["id"] == args.scientist)
    tenant = person["tenant_id"]
    if not tenant.startswith("qualification-"):
        raise ValueError("Startup comparisons may only change a disposable qualification tenant")
    identity = {"tenant_id": tenant, "model": args.model, "stage": args.stage,
                "bundle": args.bundle, "key_id": person["key_id"], "run_id": args.run_id}
    receipt_path = args.output / "comparison.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
        "identity": identity, "started_at": now(), "samples": [],
        "measurement_scope": "warm-node-fresh-pod-not-cold-node"}
    if receipt["identity"] != identity:
        raise ValueError("Comparison identity changed")
    with admin_client() as admin:
        observed = observe(admin, tenant, args.model)
        if args.bundle not in observed["startup_options"].get(args.stage, []):
            raise ValueError("Snapshot bundle is not registered for this exact model stage")
        if "baseline" not in receipt:
            receipt["baseline"] = observed["desired"]
            receipt["last_revision"] = observed["desired"]["revision"]
            save(args.output / "baseline-policy.json", observed)
            save(receipt_path, receipt)
        elif observed["desired"]["revision"] != receipt["last_revision"]:
            raise ValueError("Policy changed outside this comparison; refusing to overwrite it")
        baseline = receipt["baseline"]
        try:
            for repetition in range(1, args.repetitions + 1):
                for mode in ("normal-load", "cuda-criu"):
                    run_id = f"{args.run_id}-r{repetition}-{mode}"
                    if any(sample["run_id"] == run_id for sample in receipt["samples"]):
                        continue
                    startup = dict(baseline["startup_policies"])
                    startup[args.stage] = {"backend": mode, "bundle_id": args.bundle if mode == "cuda-criu" else None}
                    applied = change(admin, tenant, args.model,
                        policy_body(baseline, startup, revision=receipt["last_revision"]))
                    receipt.update(last_revision=applied["revision"], policy_active=True)
                    save(receipt_path, receipt)
                    folder = args.output / run_id
                    command = [sys.executable, str(Path(__file__).with_name("qualify_worker_recovery.py")),
                               "--scientists", str(args.scientists), "--scientist", args.scientist,
                               "--request", str(args.request), "--stage", args.stage, "--tool", args.tool,
                               "--run-id", run_id, "--output", str(folder), "--capture-worker-logs"]
                    outcome = subprocess.run(command, check=False)
                    if outcome.returncode:
                        raise RuntimeError("Comparison worker failed; retained operation must be reconciled")
                    result = json.loads((folder / "receipt.json").read_text())
                    if result["state"] == "still_pending":
                        raise RuntimeError("Comparison still pending; resume the same durable operation")
                    sample = {"run_id": run_id, "requested_backend": mode,
                              "state": result["state"], "operation_id": result.get("operation_id"),
                              "observed_mechanisms": mechanisms(folder),
                              "started_at": result["started_at"], "finished_at": result.get("finished_at")}
                    receipt["samples"].append(sample)
                    save(receipt_path, receipt)
                    print(json.dumps(sample), flush=True)
        finally:
            if receipt.get("policy_active"):
                restored = change(admin, tenant, args.model,
                    policy_body(baseline, baseline["startup_policies"], revision=receipt["last_revision"]))
                receipt.update(last_revision=restored["revision"], policy_active=False,
                               restored_at=now())
                save(receipt_path, receipt)


if __name__ == "__main__":
    main()
