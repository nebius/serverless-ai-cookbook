#!/usr/bin/env python3
"""Qualify one durable scientific operation across its own worker eviction.

The optional fault is a real Kubernetes Eviction API call against one exact Pod
owned by the newly submitted qualification operation. No node, other workload,
queue, retry limit or customer setting is changed. This proves API-initiated
worker-disruption behavior, not a provider-preemption or whole-node-loss event.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import quote
from uuid import UUID

from batch_transport import resolve
from collect_lifecycle import event_pages
from manage_campaign import CONTEXT, KUBECONFIG, admin_client, kube, save
from run_campaign import MCP, artifact

LABEL = "fs2.nebius.ai/"


def now():
    return datetime.now(timezone.utc).isoformat()


def request_identity(request, *, run_id):
    value = {key: val for key, val in request.items()
             if key not in {"idempotency_key", "client_context"}}
    digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return {**value, "idempotency_key": run_id,
            "client_context": {"display_name": run_id, "correlation_id": run_id}}, digest


def eviction_body(pod, *, operation_id, workload_id, tenant_id, stage_id):
    """Refuse unrelated, replaced, non-GPU or terminal Pods before mutation."""
    UUID(operation_id)
    UUID(workload_id)
    metadata = pod["metadata"]
    labels = metadata.get("labels", {})
    expected = {"operation-id": operation_id, "workload-id": workload_id,
                "tenant-id": tenant_id, "stage-id": stage_id}
    if any(labels.get(LABEL + key) != value for key, value in expected.items()):
        raise ValueError("Worker ownership differs from the qualification operation")
    if metadata.get("deletionTimestamp") or pod.get("status", {}).get("phase") != "Running":
        raise ValueError("Only the active owned worker may be evicted")
    if not any(owner.get("kind") == "Job" and owner.get("controller")
               for owner in metadata.get("ownerReferences", [])):
        raise ValueError("Worker is not controlled by the scientific Job")
    if not any(int(c.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0)) > 0
               for c in pod["spec"]["containers"]):
        raise ValueError("Selected worker has no GPU allocation")
    if not labels.get(LABEL + "attempt-id") or not pod["spec"].get("nodeName"):
        raise ValueError("Selected worker has no attempt or node identity")
    return {"apiVersion": "policy/v1", "kind": "Eviction",
            "metadata": {"name": metadata["name"], "namespace": metadata["namespace"]},
            "deleteOptions": {"preconditions": {"uid": metadata["uid"]}}}


def evict(pod, body):
    metadata = pod["metadata"]
    path = ("/api/v1/namespaces/" + quote(metadata["namespace"], safe="") +
            "/pods/" + quote(metadata["name"], safe="") + "/eviction")
    command = ["kubectl", "--kubeconfig", KUBECONFIG, "--context", CONTEXT,
               "--request-timeout=30s", "create", "--raw", path, "-f", "-"]
    outcome = subprocess.run(command, input=json.dumps(body), capture_output=True,
                             text=True, timeout=45)
    if outcome.returncode:
        raise RuntimeError("Owned worker eviction failed; retained operation must be reconciled")
    return json.loads(outcome.stdout)


def recovery_verified(attempts, eviction):
    """A successful retry is not enough unless the evicted attempt is accounted for."""
    if len(attempts) != 2 or not eviction:
        return False
    first, second = sorted(attempts, key=lambda attempt: attempt["attempt_number"])
    return (first["attempt_id"] == eviction["attempt_id"]
            and first["attempt_id"] != second["attempt_id"]
            and first["attempt_number"] == 1 and second["attempt_number"] == 2
            and first["outcome"] == "failed" and first["failure_kind"] == "infrastructure"
            and second["outcome"] == "succeeded"
            and all(attempt["resource_released"] for attempt in attempts))


def worker_logs(pod):
    """Capture only this operation's GPU container; retain payloads privately."""
    metadata = pod["metadata"]
    output = {"pod_uid": metadata["uid"], "observed_at": now(), "containers": {}}
    for container in pod["spec"]["containers"]:
        if not int(container.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0)):
            continue
        result = subprocess.run(
            ["kubectl", "--kubeconfig", KUBECONFIG, "--context", CONTEXT,
             "--request-timeout=10s", "-n", metadata["namespace"], "logs", metadata["name"],
             "-c", container["name"], "--timestamps", "--tail=2000"],
            capture_output=True, text=True, timeout=15)
        output["containers"][container["name"]] = {
            "available": result.returncode == 0, "text": result.stdout,
            "error": result.stderr[:500] if result.returncode else None}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientists", required=True, type=Path)
    parser.add_argument("--scientist", default="scientist-01")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--tool", default="submit_esmfold2")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stage", default="fold")
    parser.add_argument("--evict-owned-worker", action="store_true")
    parser.add_argument("--capture-worker-logs", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=1800)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    person = next(p for p in json.loads(args.scientists.read_text())["scientists"]
                  if p["id"] == args.scientist)
    if not person["tenant_id"].startswith("qualification-"):
        raise ValueError("This fixture only operates on disposable qualification identities")
    request, digest = request_identity(json.loads(args.request.read_text()), run_id=args.run_id)
    identity = {"request_sha256": digest, "key_id": person["key_id"], "run_id": args.run_id,
                "tool": args.tool, "evict_owned_worker": args.evict_owned_worker,
                "stage": args.stage}
    receipt_path = args.output / "receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
        "identity": identity, "started_at": now(), "state": "prepared",
        "fault_kind": "kubernetes_api_worker_eviction" if args.evict_owned_worker else "none"}
    if receipt["identity"] != identity:
        raise ValueError("Recovery run identity changed")
    if receipt.get("state") in {"verified", "failed", "cancelled", "expired"}:
        print(json.dumps(receipt))
        return
    save(receipt_path, receipt)
    mcp = MCP(person["api_key"])
    try:
        save(args.output / "initialize.json", mcp.initialize())
        if not receipt.get("operation_id"):
            save(args.output / "request.json", request)
            receipt["state"] = "submitting"
            save(receipt_path, receipt)
            admitted = mcp.call(args.tool, request)
            save(args.output / "admission.json", admitted)
            receipt.update(operation_id=admitted["operation"]["id"],
                           workload_id=admitted["batch"]["workload_id"],
                           namespace=admitted["batch"]["workload_namespace"], state="accepted")
            save(receipt_path, receipt)
        until = time.monotonic() + args.wait_seconds
        index = max((int(path.name.split("-", 1)[0]) for path in
                     (args.output / "observations").glob("*-status.json")), default=0)
        previous = None
        next_log_capture = 0
        while time.monotonic() < until:
            index += 1
            status = mcp.call("get_scientific_status", {"operation_id": receipt["operation_id"]})
            save(args.output / "observations" / f"{index:05d}-status.json", status)
            operation = status["operation"]
            if operation["id"] != receipt["operation_id"]:
                raise ValueError("Durable operation identity changed")
            pods = kube("-n", receipt["namespace"], "get", "pods", "-l",
                        LABEL + "operation-id=" + receipt["operation_id"])
            save(args.output / "observations" / f"{index:05d}-pods.json", pods)
            if args.capture_worker_logs and time.monotonic() >= next_log_capture:
                for pod in pods["items"]:
                    if pod["metadata"].get("labels", {}).get(LABEL + "stage-id") == args.stage:
                        save(args.output / "worker-logs" / f"{index:05d}-{pod['metadata']['uid']}.json",
                             worker_logs(pod))
                next_log_capture = time.monotonic() + 10
            if args.evict_owned_worker and not receipt.get("eviction_intent"):
                for pod in pods["items"]:
                    if (pod["metadata"].get("labels", {}).get(LABEL + "stage-id") != args.stage
                            or pod.get("status", {}).get("phase") != "Running"):
                        continue
                    body = eviction_body(pod, operation_id=receipt["operation_id"],
                        workload_id=receipt["workload_id"], tenant_id=person["tenant_id"], stage_id=args.stage)
                    receipt["eviction_intent"] = {"at": now(), "pod_uid": pod["metadata"]["uid"],
                        "pod_name": pod["metadata"]["name"], "node_name": pod["spec"]["nodeName"],
                        "attempt_id": pod["metadata"]["labels"][LABEL + "attempt-id"]}
                    # Persist before mutation. An interrupted fixture never
                    # evicts another attempt or treats an uncertain fault as absent.
                    save(receipt_path, receipt)
                    save(args.output / "eviction-request.json", body)
                    save(args.output / "eviction-response.json", evict(pod, body))
                    receipt["eviction_accepted_at"] = now()
                    save(receipt_path, receipt)
                    break
            stages = status.get("batch", {}).get("stages", [])
            state = {"status": operation["status"], "stages": [
                {"stage": s["stage_id"], "status": s["status"], "attempts": len(s["attempts"])} for s in stages]}
            if state != previous:
                print(json.dumps({"at": now(), "operation_id": receipt["operation_id"], **state}), flush=True)
                previous = state
            terminal = operation["status"] in {"failed", "cancelled", "expired", "preempted"}
            published = operation["status"] == "succeeded" and status["batch"]["result_published"]
            if published and not all(a["resource_released"] for s in stages for a in s["attempts"]):
                time.sleep(2)
                continue
            if terminal or published:
                save(args.output / "status.json", status)
                receipt.update(state=operation["status"], finished_at=now())
                save(args.output / "events.json", event_pages(mcp.client, receipt["operation_id"]))
                with admin_client() as admin:
                    detail = admin.get("/admin/api/v1/scientific-runs/" + receipt["operation_id"])
                    detail.raise_for_status()
                    save(args.output / "operator-accounting.json", detail.json())
                if operation["status"] == "succeeded" and status["batch"]["result_published"]:
                    envelope = mcp.call("get_scientific_result", {"operation_id": receipt["operation_id"]})
                    save(args.output / "result-envelope.json", envelope)
                    outputs = resolve(mcp.client, envelope, args.output, artifact)
                    save(args.output / "verified-artifacts.json", outputs)
                    attempted = next(s for s in stages if s["stage_id"] == args.stage)["attempts"]
                    receipt.update(verified_artifacts=outputs["verified_artifacts"],
                        semantic_validation=envelope["semantic_validation"], gpu_attempts=len(attempted),
                        recovery_verified=bool(receipt.get("eviction_accepted_at"))
                            and recovery_verified(attempted, receipt.get("eviction_intent")))
                    if envelope["semantic_validation"]["status"] != "passed":
                        raise ValueError("Model semantic output check failed")
                    replay = mcp.call(args.tool, request)
                    save(args.output / "idempotent-replay.json", replay)
                    if (replay["operation"]["id"] != receipt["operation_id"]
                            or replay["batch"]["workload_id"] != receipt["workload_id"]):
                        raise ValueError("Replaying the same scientific request created different work")
                    receipt["same_identity_replay_verified"] = True
                    receipt["state"] = "verified" if (not args.evict_owned_worker or receipt["recovery_verified"]) else "fault_not_qualified"
                save(receipt_path, receipt)
                print(json.dumps(receipt), flush=True)
                return
            time.sleep(2)
        receipt.update(state="still_pending", observed_at=now())
        save(receipt_path, receipt)
        print(json.dumps(receipt), flush=True)
    finally:
        mcp.close()


if __name__ == "__main__":
    main()
