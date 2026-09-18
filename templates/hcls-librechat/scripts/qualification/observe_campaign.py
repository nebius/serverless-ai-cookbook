#!/usr/bin/env python3
"""Read-only campaign capacity, health and App metric sampling."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import time

import httpx

from manage_campaign import ORIGIN, admin_client, kube, save
from run_campaign import journal


def gpu_capacity(nodes, pods):
    """Retain registered totals, but distinguish live schedulable capacity."""
    ready = {n["metadata"]["name"] for n in nodes if any(
        c["type"] == "Ready" and c["status"] == "True" for c in n["status"].get("conditions", []))}
    available = {n["metadata"]["name"] for n in nodes if n["metadata"]["name"] in ready
        and not n.get("spec", {}).get("unschedulable", False)
        and not any(t["key"] in {"node.cloudprovider.kubernetes.io/shutdown", "node.kubernetes.io/unreachable",
                                  "node.kubernetes.io/not-ready"} for t in n.get("spec", {}).get("taints", []))}
    active = [p for p in pods if p["status"]["phase"] not in ("Succeeded", "Failed") and p["spec"].get("nodeName")]
    def allocated(selected):
        return sum(int(n["status"].get("allocatable", {}).get("nvidia.com/gpu", 0)) for n in nodes
                   if n["metadata"]["name"] in selected)
    def reserved(selected):
        return sum(int(c.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0))
                   for p in active if p["spec"]["nodeName"] in selected for c in p["spec"]["containers"])
    return {"ready_allocatable_gpus": allocated(ready), "schedulable_allocatable_gpus": allocated(available),
            "ready_reserved_gpus": reserved(ready), "schedulable_reserved_gpus": reserved(available),
            "registered_unready_gpus": allocated({n["metadata"]["name"] for n in nodes} - ready)}


def sample(output, include_metrics=False):
    at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = output / at
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {"at": at}
    cluster_data = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {name: pool.submit(kube, "get", name, "-A")
                   for name in ("nodes", "pods", "events")}
        for name, future in pending.items():
            try:
                data = future.result()
                cluster_data[name] = data["items"]
                save(folder / (name + ".json"), data)
                if name == "nodes":
                    result["allocatable_gpus"] = sum(int(n["status"].get("allocatable", {}).get("nvidia.com/gpu", 0))
                                                     for n in data["items"])
                if name == "pods":
                    result["reserved_gpus"] = sum(int(c.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0))
                        for p in data["items"] if p["status"]["phase"] not in ("Succeeded", "Failed") and p["spec"].get("nodeName")
                        for c in p["spec"]["containers"])
                    result["pending_gpu_pods"] = [p["metadata"]["namespace"] + "/" + p["metadata"]["name"]
                        for p in data["items"] if p["status"]["phase"] == "Pending" and any(
                            int(c.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0))
                            for c in p["spec"]["containers"])]
            except Exception as error:
                result[name + "_error"] = type(error).__name__
    if "nodes" in cluster_data and "pods" in cluster_data:
        result.update(gpu_capacity(cluster_data["nodes"], cluster_data["pods"]))
    with httpx.Client(base_url=ORIGIN, timeout=20, trust_env=False) as public:
        start = time.monotonic()
        try:
            response = public.get("/readyz")
            result["health_route"] = "/readyz"
            result["health_http"] = response.status_code
        except httpx.HTTPError as error:
            result["health_error"] = type(error).__name__
        result["health_elapsed_seconds"] = time.monotonic() - start
    try:
        with admin_client() as admin:
            for route in ("capacity", "overview"):
                response = admin.get("/admin/api/v1/" + route)
                save(folder / (route + ".json"), {"status": response.status_code, "body": response.json()})
            if include_metrics:
                response = admin.get("/admin/api/v1/apps")
                response.raise_for_status()
                for app in response.json()["data"]["items"]:
                    metrics = admin.get("/admin/api/v1/apps/" + app["app_id"] + "/metrics")
                    save(folder / (app["public_model_id"] + "-metrics.json"),
                         {"status": metrics.status_code, "body": metrics.json()})
    except Exception as error:
        result["admin_error"] = type(error).__name__
    save(folder / "summary.json", result)
    journal(output, result)
    print(json.dumps(result), flush=True)


def main():
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline", default="2026-09-19T06:04:00+00:00")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    count = 0
    while datetime.now(timezone.utc) < datetime.fromisoformat(args.deadline):
        started = time.monotonic()
        sample(args.output, include_metrics=count % 10 == 0)
        count += 1
        time.sleep(max(0, args.interval - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
