#!/usr/bin/env python3
"""Capture the exact mounted runtime baseline for an offline promotion review.

Read-only. No credentials are emitted; complete manifests stay in the protected
evidence directory. The model profiles are read from an actual Ready gateway,
not assumed to match whichever files are currently in the shared worktree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from manage_campaign import CONTEXT, KUBECONFIG, kube, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settled-values", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    deployment = kube("-n", "fs2-system", "get", "deployment", "fs2-serve-control-plane")
    template = deployment["spec"]["template"]["spec"]
    container = next(c for c in template["containers"] if c["name"] == "control-plane")
    values = json.loads(args.settled_values.read_text())
    selector = ",".join(f"{k}={v}" for k, v in deployment["spec"]["selector"]["matchLabels"].items())
    pods = kube("-n", "fs2-system", "get", "pods", "-l", selector)
    pod = next(p for p in pods["items"] if not p["metadata"].get("deletionTimestamp")
               and any(c["name"] == "control-plane" and c["ready"] for c in p["status"].get("containerStatuses", []))
               and any(c["name"] == "control-plane" and c["image"] == container["image"] for c in p["spec"]["containers"]))
    env = {e["name"]: e["value"] for e in container["env"] if "value" in e}
    command = ["kubectl", "--kubeconfig", KUBECONFIG, "--context", CONTEXT,
               "--request-timeout=30s", "-n", "fs2-system", "exec", pod["metadata"]["name"],
               "-c", "control-plane", "--", "cat", env["FS2_CATALOG_DIR"] + "/contracts/scientific-workload-profiles.json"]
    raw = subprocess.check_output(command, timeout=50)
    profiles = json.loads(raw)
    names = sorted({v["configMap"]["name"] for v in template["volumes"] if "configMap" in v})
    maps = {"apiVersion": "v1", "kind": "List", "items": [kube("-n", "fs2-system", "get", "configmap", name) for name in names]}
    scheduling_name = next(v["configMap"]["name"] for v in template["volumes"] if v["name"] == "scientific-batch-scheduling")
    scheduling_raw = next(c for c in maps["items"] if c["metadata"]["name"] == scheduling_name)["data"]["kueue-scheduling.json"]
    if hashlib.sha256(scheduling_raw.encode()).hexdigest() != env["FS2_SCIENTIFIC_BATCH_SCHEDULING_CONTRACT_SHA256"]:
        raise ValueError("Mounted scheduling contract digest mismatch")
    for name, value in (("values", values), ("gateway-deployment", deployment), ("configmaps", maps),
                        ("profiles", profiles)):
        save(args.output / (name + ".json"), value)
    scheduling_path = args.output / "scheduling.json"
    scheduling_path.write_bytes(scheduling_raw.encode())
    scheduling_path.chmod(0o600)
    receipt = {"gateway_pod": pod["metadata"]["name"], "gateway_pod_uid": pod["metadata"]["uid"],
               "image": container["image"], "mounted_maps": names,
               "profiles_sha256": hashlib.sha256(raw).hexdigest(), "profile_count": len(profiles["profiles"]),
               "scheduling_sha256": hashlib.sha256(scheduling_raw.encode()).hexdigest()}
    save(args.output / "capture-receipt.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
