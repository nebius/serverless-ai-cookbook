#!/usr/bin/env python3
"""Read-only, bounded reservation/wait evidence; never measures GPU utilization."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median


def seconds_between(start: str, end: str) -> float:
    value = (datetime.fromisoformat(end.replace("Z", "+00:00"))
             - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()
    if value < 0:
        raise ValueError("negative observed interval")
    return value


def summarize_reservations(rows: list[dict]) -> dict:
    """Preserve absent measurements and do not substitute registered GPUs."""
    fields = ("schedulable_allocatable_gpus", "schedulable_reserved_gpus")
    measured = [r for r in rows if all(isinstance(r.get(k), (int, float)) for k in fields)]
    residual = [r[fields[0]] - r[fields[1]] for r in measured]
    if any(value < 0 for value in residual):
        raise ValueError("inconsistent reservation snapshot")
    ranges = {k: {"min": min(r[k] for r in measured), "max": max(r[k] for r in measured)}
              for k in fields} if measured else {}
    return {
        "samples": len(rows), "measured_samples": len(measured),
        "reservation_ranges": ranges,
        "unreserved_resource_units": ({"min": min(residual), "max": max(residual),
                                       "median": median(residual)} if residual else None),
        "pending_gpu_pod_samples": sum(bool(r.get("pending_gpu_pods")) for r in rows),
        "readyz_http_counts": dict(Counter(str(r.get("health_http")) for r in rows
                                           if r.get("health_route") == "/readyz")),
        "is_gpu_utilization": False,
        "is_model_placement_headroom": False,
    }


def per_pool_reservations(nodes: list[dict], pods: list[dict]) -> list[dict]:
    """Mirror retained observer's regular-container reservation definition."""
    reserved: Counter = Counter()
    for pod in pods:
        if pod.get("status", {}).get("phase") not in {"Succeeded", "Failed"}:
            reserved[pod["spec"].get("nodeName")] += sum(
                int(c.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0))
                for c in pod["spec"].get("containers", []))
    pools = defaultdict(lambda: {"ready_gpu_units": 0, "reserved_gpu_units": 0, "nodes": 0})
    for node in nodes:
        spec, status = node.get("spec", {}), node.get("status", {})
        ready = any(c.get("type") == "Ready" and c.get("status") == "True"
                    for c in status.get("conditions", []))
        unavailable = {"node.kubernetes.io/not-ready", "node.kubernetes.io/unreachable",
                       "node.cloudprovider.kubernetes.io/shutdown"}
        if not ready or spec.get("unschedulable") or any(t["key"] in unavailable
                                                       for t in spec.get("taints", [])):
            continue
        count = int(status.get("allocatable", {}).get("nvidia.com/gpu", 0))
        if not count:
            continue
        row = pools[node["metadata"].get("labels", {}).get("accelerator.fs2.nebius/pool-id", "unknown")]
        row["nodes"] += 1
        row["ready_gpu_units"] += count
        row["reserved_gpu_units"] += reserved[node["metadata"]["name"]]
    return [dict(pool_id=pool, **row,
                 unreserved_gpu_units=row["ready_gpu_units"] - row["reserved_gpu_units"])
            for pool, row in sorted(pools.items())]


def build(root: Path, start: str, end: str) -> dict:
    evidence = {}

    def read(relative: str):
        raw = (root / relative).read_bytes()
        evidence[relative] = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
        return json.loads(raw)

    rows = [read(str(p.relative_to(root))) for p in sorted((root / "observations").glob("*/summary.json"))
            if start <= p.parent.name <= end]
    snapshots = {}
    for stamp in ("20260919T025752Z", "20260919T031552Z", end):
        prefix = f"observations/{stamp}"
        nodes, pods = read(prefix + "/nodes.json")["items"], read(prefix + "/pods.json")["items"]
        queues = read(prefix + "/capacity.json")["body"]["data"]["kueue"]["cluster_queues"]
        queue = next(x for x in queues if x["name"] == "inference-accelerators")
        bind = next((p for p in pods if p["metadata"].get("uid") ==
                     "fc8db5a5-c708-4a7e-8dc5-e8138752f14f"), None)
        snapshots[stamp] = {
            "pools": per_pool_reservations(nodes, pods),
            "queue_strategy": queue["queueing_strategy"], "queue_workloads": queue["workloads"],
            "bindcraft_pod": None if bind is None else {
                "uid": bind["metadata"]["uid"], "phase": bind["status"]["phase"],
                "node": bind["spec"]["nodeName"], "node_selector": bind["spec"].get("nodeSelector"),
                "affinity": bind["spec"].get("affinity"),
                "containers": [{"name": c["name"], "resources": c.get("resources")}
                               for c in bind["spec"]["containers"]],
                "container_restarts": {c["name"]: c["restartCount"]
                                       for c in bind["status"].get("containerStatuses", [])},
            },
        }
    events = read("observations/20260919T031552Z/events.json")["items"]
    bind_events = [{k: e.get(k) for k in ("reason", "message", "firstTimestamp", "lastTimestamp", "count")}
                   for e in events if e.get("involvedObject", {}).get("uid") ==
                   "940aa3ad-f1b4-45ac-aa52-ddc0f1f6e234"]
    witnesses = []
    selections = (
        "design-heldout-r177/scientist-01/mosaic-ubiquitin-s42-l80",
        "proteina-multisample-r178/scientist-02/proteina-complexa-pdl1-s1-n4",
        "diffdock-http-identity-public-r179-a/scientist-06/diffdock-1a52-est-s19-n4",
        "rfdiffusion-refolds-r179/scientist-01/refold-inverse-rfdiffusion-unconditional-s1-l256-backbone1-design1",
    )
    for case in selections:
        receipt = read(f"cohorts/{case}/receipt.json")
        witnesses.append({k: receipt.get(k) for k in ("model_id", "operation_id", "tenant_id", "scientist",
                         "state", "started_at", "admitted_at", "finished_at", "elapsed_seconds")})
    read("heldout-bindcraft-observation-0404.json")
    read("backend-baseline179/profiles.json")
    incident_events = read("observations/20260918T221631Z/events.json")["items"]
    incident = [{"object": e.get("involvedObject", {}).get("name"),
                 **{k: e.get(k) for k in ("reason", "message", "lastTimestamp")}}
                for e in incident_events
                if ("12ca44823a06" in e.get("involvedObject", {}).get("name", "")
                    or "e00srhk44n11yvn2n9" in e.get("involvedObject", {}).get("name", ""))
                and e.get("reason") in {"TriggeredScaleUp", "Scheduled", "NodeNotReady",
                                        "TaintManagerEviction", "Failed", "InspectFailed"}]
    providers = []
    for node in ("computeinstance-e00e0ga28zazapewdb", "computeinstance-e00krj1rq710382765"):
        envelope = read(f"capacity-preemption-2211/{node}-provider.json")
        body = json.loads(envelope["stdout"])
        providers.append({"node": node, "at": envelope["at"], "state": body["status"]["state"],
                          "preemptible": body["spec"].get("preemptible"), "cause": "not recorded by provider response"})
    original = read("esmfold-preemption-diagnosis/public-result.json")
    replay = read("cohorts/esmfold-preemption-repaired-r1/scientist-01/esmfold2-1tim-pdb70-depth64/receipt.json")
    return {
        "schema": "scientific-qualification/capacity-evidence/v1",
        "window": {"start_sample_inclusive": start, "end_sample_inclusive": end},
        "reservations": summarize_reservations(rows), "snapshots": snapshots,
        "bindcraft_queue_events": bind_events, "concurrent_completion_witnesses": witnesses,
        "capacity_incident": {"events": incident, "provider_captures": providers,
                              "original_operation_id": original["operation_id"], "original_error": original.get("error"),
                              "separate_replay_operation_id": replay["operation_id"],
                              "separate_replay_state": replay["state"], "automatic_recovery_qualified": False},
        "evidence_root": "protected scientific-qualification-20260918 directory",
        "evidence": evidence,
        "limitations": ["60-second, non-atomic snapshots", "reservations are not GPU busy time",
                        "aggregate free resources are not placement-qualified capacity",
                        "BestEffortFIFO and observed progress do not establish bounded fairness",
                        "selected witnesses are not campaign operation counts"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, "20260919T025641Z", "20260919T044118Z"), indent=2))
