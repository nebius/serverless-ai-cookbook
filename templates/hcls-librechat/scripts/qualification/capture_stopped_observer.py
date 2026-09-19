#!/usr/bin/env python3
"""Capture exact provider/node/observer evidence without deleting anything."""
import argparse
import json
from pathlib import Path
import subprocess

from manage_campaign import CLI, kube, now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pod", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pod = kube("-n", "fs2-system", "get", "pod", args.pod)
    owners = pod["metadata"].get("ownerReferences", [])
    owner = next(item for item in owners if item["kind"] == "DaemonSet" and item.get("controller"))
    if owner["name"] != "fs2-serve-control-plane-gpu-observer":
        raise ValueError("Not the intended observer DaemonSet")
    daemonset = kube("-n", "fs2-system", "get", "daemonset", owner["name"])
    if daemonset["metadata"]["uid"] != owner["uid"]:
        raise ValueError("Observer owner identity changed")
    node = kube("get", "node", pod["spec"]["nodeName"])
    provider = json.loads(subprocess.check_output(CLI + ["compute", "instance", "get", "--id", node["metadata"]["name"], "--format", "json"], text=True, timeout=70))
    events = kube("-n", "fs2-system", "get", "events", "--field-selector", "involvedObject.uid=" + pod["metadata"]["uid"])
    for name, value in (("pod", pod), ("node", node), ("provider", provider), ("daemonset", daemonset), ("events", events)):
        save(args.output / (name + ".json"), value)
    receipt = {"captured_at": now(), "pod": args.pod, "pod_uid": pod["metadata"]["uid"],
               "node": node["metadata"]["name"], "node_uid": node["metadata"]["uid"],
               "deletion_timestamp": pod["metadata"].get("deletionTimestamp"),
               "provider_state": provider["status"]["state"], "mutation_performed": False}
    save(args.output / "receipt.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
