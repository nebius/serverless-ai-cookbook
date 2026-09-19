#!/usr/bin/env python3
"""Exercise an App's existing replica range through its ordinary owner API.

Only minReplicas changes. The original spec is retained for exact restoration;
resource limits, maxReplicas, placement and other customers are untouched.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from manage_campaign import admin_client, save


def proposed_spec(original, replicas):
    result = copy.deepcopy(original)
    if isinstance(replicas, bool) or not isinstance(replicas, int):
        raise ValueError("Replica count must be an integer")
    if not 0 <= replicas <= original["availability"]["maxReplicas"]:
        raise ValueError("Test must remain inside the existing replica range")
    if original["lifecycle"]["desiredState"] != "Enabled":
        raise ValueError("Expected an enabled App")
    result["availability"]["minReplicas"] = replicas
    return result


def read(client, model):
    response = client.get("/admin/api/v1/model-deployments/" + model)
    response.raise_for_status()
    return response.json()["data"]


def post(client, path, payload, receipt):
    response = client.post(path, json=payload)
    save(receipt, {"http_status": response.status_code, "body": response.json()})
    response.raise_for_status()
    return response.json()["data"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "restore"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--replicas", required=True, type=int)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    with admin_client() as client:
        current = read(client, args.model)
        original_path = args.output / "original-owner.json"
        if original_path.exists():
            original = json.loads(original_path.read_text())
        elif args.action == "apply":
            original = current
            save(original_path, original)
        else:
            raise ValueError("Cannot restore without the retained original owner")
        if (original["spec"]["modelRef"] != args.model
                or original["spec"]["runtime"]["image"] != args.expected_image):
            raise ValueError("Original owner does not match the exact reviewed App/image")
        changed = proposed_spec(original["spec"], args.replicas)
        if current["spec"] not in (original["spec"], changed):
            raise ValueError("App changed outside this test; do not overwrite it")
        target = original["spec"] if args.action == "restore" else changed
        save(args.output / (args.action + "-before.json"), current)
        if current["spec"] == target:
            print(json.dumps({"model": args.model, "action": args.action, "already_applied": True}))
            return
        proposal = {"name": args.model, "namespace": original["namespace"],
                    "spec": target, "base_etag": current["etag"]}
        preview = post(client, "/admin/api/v1/model-deployments:plan-preview", proposal,
                       args.output / (args.action + "-preview.json"))
        if preview["decision"]["disposition"] != "accepted" or preview.get("render") is None:
            raise ValueError("Replica change was not accepted by the ordinary owner API")
        transaction = hashlib.sha256(str(args.output.resolve()).encode()).hexdigest()[:16]
        post(client, "/admin/api/v1/model-deployments:apply", {
            "preview_id": preview["preview_id"], "proposed_etag": preview["proposed_etag"],
            "proposal": proposal,
            "idempotency_key": f"qualification-replicas-{transaction}-{args.action}-{preview['proposed_etag'][:12]}",
        }, args.output / (args.action + "-receipt.json"))
        after = read(client, args.model)
        save(args.output / (args.action + "-after.json"), after)
        if after["spec"] != target:
            raise ValueError("Replica owner readback differs from accepted target")
        print(json.dumps({"model": args.model, "action": args.action,
                          "min_replicas": target["availability"]["minReplicas"],
                          "max_replicas": target["availability"]["maxReplicas"]}))


if __name__ == "__main__":
    main()
