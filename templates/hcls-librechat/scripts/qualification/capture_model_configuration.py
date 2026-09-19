#!/usr/bin/env python3
"""Read-only owner/render bracket for a control-plane-only deployment.

Replica counts and status resource versions legitimately change with demand.
Compare App specs and generated Pod templates instead; never mutate workloads.
"""
import argparse
import hashlib
import json
from pathlib import Path

from manage_campaign import kube, now, save


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def capture():
    owners = kube("get", "modeldeployments", "-A")["items"]
    deployments = kube("get", "deployments", "-A")["items"]
    keys = {(item["metadata"]["namespace"], item["metadata"]["uid"]) for item in owners}
    rows = []
    for item in owners:
        meta, spec, status = item["metadata"], item["spec"], item.get("status", {})
        cache, fast = spec.get("cache", {}), status.get("fastStart", {})
        rows.append({"name": meta["namespace"] + "/" + meta["name"], "uid": meta["uid"],
                     "spec_sha256": digest(spec), "generation": meta["generation"],
                     "observed_generation": status.get("observedGeneration"),
                     "snapshot_preference": cache.get("snapshotPreference"),
                     "snapshot_ref": cache.get("snapshotRef"),
                     "qualified_level": fast.get("qualifiedLevel"),
                     "effective_level": fast.get("effectiveLevel"),
                     "cache_mechanisms": fast.get("cacheMechanisms", {})})
    rendered = {}
    for item in deployments:
        meta = item["metadata"]
        if any((meta["namespace"], owner["uid"]) in keys
               for owner in meta.get("ownerReferences", []) if owner.get("controller")):
            rendered[meta["namespace"] + "/" + meta["name"]] = digest(item["spec"]["template"])
    return {"at": now(), "read_only": True, "owners": sorted(rows, key=lambda row: row["name"]),
            "rendered_pod_templates": rendered}


def compare(before, after):
    old = {row["name"]: row for row in before["owners"]}
    new = {row["name"]: row for row in after["owners"]}
    return {"owner_set_unchanged": old.keys() == new.keys(),
            "owner_specs_unchanged": {key: row["spec_sha256"] for key, row in old.items()}
            == {key: row["spec_sha256"] for key, row in new.items()},
            "rendered_pod_templates_unchanged": before["rendered_pod_templates"] == after["rendered_pod_templates"],
            "qualified_levels_unchanged": {key: row["qualified_level"] for key, row in old.items()}
            == {key: row["qualified_level"] for key, row in new.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh evidence path")
    result = capture()
    if args.baseline:
        result["comparison"] = compare(json.loads(args.baseline.read_text()), result)
    save(args.output, result)
    print(json.dumps({"owners": len(result["owners"]), "templates": len(result["rendered_pod_templates"]),
                      "comparison": result.get("comparison"), "output": str(args.output)}))
