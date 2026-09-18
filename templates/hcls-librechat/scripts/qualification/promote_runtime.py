#!/usr/bin/env python3
"""Coordinate explicitly selected reviewed runtime repairs through owner APIs.

Run with the exact backend source environment. This never patches generated
Deployments, modifies a quota, or changes another App. Helm reference changes
are a separate explicitly reviewed release step between drain and apply.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from fs2_serve.model_deployment import ModelDeploymentSpec, ValidationDisposition, spec_digest

from manage_campaign import admin_client, kube, save


def identity(spec):
    return spec_digest(ModelDeploymentSpec.model_validate(spec))


def drained(spec):
    result = copy.deepcopy(spec)
    result["lifecycle"]["desiredState"] = "Draining"
    result["availability"]["minReplicas"] = 0
    return result


def read(client, path):
    response = client.get(path)
    response.raise_for_status()
    return response.json()["data"]


def post(client, path, payload, receipt):
    response = client.post(path, json=payload)
    save(receipt, {"http_status": response.status_code, "body": response.json()})
    response.raise_for_status()
    return response.json()["data"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "drain", "apply", "verify"))
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--models", required=True, nargs="+", help="Exact reviewed canonical model set")
    args = parser.parse_args()
    original = json.loads((args.candidate / "rollback-app-proposals.json").read_text())
    proposed = {p["name"]: p for p in json.loads((args.candidate / "app-proposals.json").read_text())}
    if (not original or len(original) != len(set(args.models))
        or {r["spec"]["modelRef"] for r in original} != set(args.models)
        or {r["name"] for r in original} != set(proposed)
        or any(r["name"] != r["spec"]["modelRef"] for r in original)
        or any(r["name"] != r["spec"]["modelRef"] for r in proposed.values())):
        raise ValueError("Promotion must match the explicit canonical App/model set exactly")
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with admin_client() as client:
        current = {}
        for row in original:
            name = row["name"]
            current[name] = read(client, "/admin/api/v1/model-deployments/" + name)
            save(args.output / (args.action + "-before-" + name + ".json"), current[name])
            expected = {identity(row["spec"]), identity(drained(row["spec"])), identity(proposed[name]["spec"])}
            if identity(current[name]["spec"]) not in expected or current[name]["etag"] != identity(current[name]["spec"]):
                raise ValueError("App changed outside this exact prepared promotion: " + name)
        for row in original:
            name, namespace = row["name"], row["namespace"]
            value = current[name]
            if args.action == "drain":
                if value["etag"] == identity(row["spec"]):
                    post(client, f"/admin/api/v1/model-deployments/{name}:drain", {
                        "base_etag": value["etag"], "idempotency_key": "qualification-20260918-drain-" + name + "-" + value["etag"][:12],
                    }, args.output / ("drain-" + name + ".json"))
                elif value["etag"] != identity(drained(row["spec"])):
                    raise ValueError("Refuse to drain an already promoted App")
            elif args.action == "apply":
                if value["etag"] == identity(proposed[name]["spec"]):
                    print(json.dumps({"name": name, "state": "already_applied"}), flush=True)
                    continue
                observation = kube("-n", namespace, "get", "modeldeployment", name)
                status = observation.get("status", {})
                replicas = status.get("replicas", {})
                if (value["etag"] != identity(drained(row["spec"])) or status.get("specDigest") != value["etag"]
                    or status.get("observedGeneration") != observation["metadata"]["generation"]
                    or status.get("phase") != "Cold"
                    or any(replicas.get(key) != 0 for key in ("desired", "ready", "available"))):
                    raise ValueError("App has not fully drained the matching observed revision: " + name)
                proposal = {**proposed[name], "base_etag": value["etag"]}
                preview = post(client, "/admin/api/v1/model-deployments:plan-preview", proposal,
                               args.output / ("preview-" + name + ".json"))
                if preview["decision"]["disposition"] != ValidationDisposition.ACCEPTED or preview.get("render") is None:
                    raise ValueError("Prepared replacement was not accepted: " + name)
                post(client, "/admin/api/v1/model-deployments:apply", {
                    "preview_id": preview["preview_id"], "proposed_etag": preview["proposed_etag"],
                    "proposal": proposal, "idempotency_key": "qualification-20260918-apply-" + name + "-" + preview["proposed_etag"][:12],
                }, args.output / ("apply-" + name + ".json"))
            observation = kube("-n", namespace, "get", "modeldeployment", name)
            save(args.output / (args.action + "-observation-" + name + ".json"), observation)
            status = observation.get("status", {})
            print(json.dumps({"name": name, "action": args.action, "phase": status.get("phase"),
                              "image": observation["spec"]["runtime"]["image"],
                              "replicas": status.get("replicas")}), flush=True)
            if args.action == "verify":
                if value["etag"] != identity(proposed[name]["spec"]):
                    raise ValueError("App does not have the prepared runtime")
                if status.get("phase") != "Ready" or status.get("specDigest") != value["etag"]:
                    raise ValueError("App replacement has not reached matching Ready observation")


if __name__ == "__main__":
    main()
