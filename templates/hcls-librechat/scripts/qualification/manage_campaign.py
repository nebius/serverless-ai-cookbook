#!/usr/bin/env python3
"""Provision task-owned scientist identities and save private campaign evidence.

No credentials are printed. Existing customer policies are never changed.
The manifest is the resume boundary; keep it outside the source repository.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

import httpx

ORIGIN = "https://89.169.99.188"
KUBECONFIG = "/home/tux/secure-handoff/cosmos-stockholm-sandbox2-20260917.kubeconfig"
CONTEXT = "fs2-remediation-sandbox2"
CLI = ["nebius", "--profile", "sandbox2", "--no-browser", "--timeout", "60s"]
PERSONAS = [
    "structural-bioinformatician", "complex-structure-researcher", "protein-designer",
    "binder-designer", "computational-chemist", "genomicist", "aging-researcher",
    "medical-nlp-researcher", "conversation-evaluator", "robotics-researcher",
]
SCOPES = ["catalog.read", "inference.invoke", "mcp.invoke", "operations.read",
          "operations.result", "artifacts.write", "operations.cancel", "operations.acknowledge"]


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    temporary.replace(path)
    path.chmod(0o600)


def kube(*args):
    command = ["kubectl", "--kubeconfig", KUBECONFIG, "--context", CONTEXT,
               "--request-timeout=30s", *args, "-o", "json"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=50)
    if result.returncode:
        raise RuntimeError("Kubernetes read failed; no secret output disclosed")
    return json.loads(result.stdout)


@contextmanager
def admin_client():
    raw = kube("-n", "fs2-system", "get", "secret", "fs2-serve-admin")
    token = base64.b64decode(raw["data"]["token"]).decode().strip()
    client = httpx.Client(base_url=ORIGIN, headers={"origin": ORIGIN}, timeout=90, trust_env=False)
    response = client.post("/admin/api/v1/session", headers={"authorization": "Bearer " + token})
    if response.status_code != 200:
        client.close()
        raise RuntimeError(f"Admin session returned {response.status_code}")
    try:
        yield client
    finally:
        client.close()


def request(client, method, path, payload=None, statuses=(200,)):
    response = client.request(method, path, json=payload)
    if response.status_code not in statuses:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
    return response.json().get("data", response.json())


def prepare(args):
    path = args.output / "scientists-private.json"
    if path.exists():
        manifest = json.loads(path.read_text())
    else:
        # These selectors reuse the approved deployment's provider credentials;
        # every scientist receives their own model key and S3 credential below.
        endpoint = json.loads(subprocess.check_output(CLI + [
            "ai", "endpoint", "get", "aiendpoint-e00hf15nz04eqt6b9q", "--format", "json"
        ], text=True))
        env = endpoint["spec"]["environment_variables"]
        manifest = {"campaign_id": "scientific-qualification-20260918", "created_at": now(),
                    "deadline": "2026-09-19T06:04:00+00:00", "project_id": "project-e00rene",
                    "subnet_id": endpoint["spec"]["subnet_id"], "scientists": [],
                    "source_endpoint_id": endpoint["metadata"]["id"],
                    "source_image": endpoint["spec"]["image"], "source_env": env}
        save(path, manifest)
    providers = {item["name"]: item["mysterybox_secret"] for item in manifest["source_env"]
                 if "mysterybox_secret" in item}
    manifest["token_factory_secret_selector"] = providers["NEBIUS_API_KEY"]["secret_id"]
    manifest["tavily_secret_selector"] = providers["TAVILY_API_KEY"]["secret_id"]
    save(path, manifest)
    with admin_client() as admin:
        for index, persona in enumerate(PERSONAS, 1):
            sid = f"scientist-{index:02d}"
            row = next((r for r in manifest["scientists"] if r["id"] == sid), None)
            if row is None:
                lab = "a" if index <= 4 else "b" if index <= 7 else "c"
                row = {"id": sid, "persona": persona, "tenant_id": f"qualification-20260918-lab-{lab}",
                       "principal_id": sid, "email": f"{sid}@qualification.example.invalid",
                       "password": secrets.token_urlsafe(24), "created_at": now()}
                manifest["scientists"].append(row)
                save(path, manifest)
            if not row.get("user_id"):
                listing = request(admin, "GET", "/admin/api/v1/users?tenant_id=" + row["tenant_id"] + "&limit=1000")
                existing = [r for r in listing["items"] if r["principal_id"] == sid]
                if existing:
                    user = existing[0]
                else:
                    user = request(admin, "POST", "/admin/api/v1/users", {
                        "tenant_id": row["tenant_id"], "principal_id": sid, "kind": "human",
                        "display_name": "Qualification: " + persona, "team": "scientific-qualification-20260918"
                    }, (201,))
                row["user_id"] = user["id"]
                save(path, manifest)
            if not row.get("api_key"):
                key_name = "scientific-qualification-20260918-" + sid
                keys = request(admin, "GET", f"/admin/api/v1/users/{row['user_id']}/keys")["items"]
                if any(k.get("name") == key_name and k.get("state") == "active" for k in keys):
                    raise RuntimeError(f"{sid}: existing undisclosed campaign key; reconcile before reissuing")
                issued = request(admin, "POST", f"/admin/api/v1/users/{row['user_id']}/keys", {
                    "tenant_id": row["tenant_id"], "principal_id": sid, "name": key_name,
                    "models": ["*"], "scopes": SCOPES, "max_concurrency": 1,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                }, (201,))
                row.update(api_key=issued["secret"], key_id=issued["key"]["id"], max_concurrency=1)
                save(path, manifest)
            print(json.dumps({"scientist": sid, "user": "ready", "key": "ready", "concurrency": 1}), flush=True)
    print(json.dumps({"manifest": str(path), "scientists": len(manifest["scientists"])}))


def storage(args):
    path = args.output / "scientists-private.json"
    deadline = time.monotonic() + args.wait_seconds
    while True:
        manifest = json.loads(path.read_text())
        pending = 0
        for row in manifest["scientists"]:
            if row.get("s3_secret_access_key"):
                continue
            with httpx.Client(base_url=ORIGIN, headers={"authorization": "Bearer " + row["api_key"]},
                              timeout=60, trust_env=False) as client:
                response = client.get("/v1/storage")
                response.raise_for_status()
                info = response.json()
                row["storage_state"] = info["state"]
                if info["state"] == "ready":
                    response = client.post("/v1/storage/credentials")
                    response.raise_for_status()
                    credentials = response.json()
                    row.update(bucket_name=credentials["bucket_name"], s3_access_key_id=credentials["access_key_id"],
                               s3_secret_access_key=credentials["secret_access_key"],
                               s3_endpoint=credentials["endpoint"], s3_region=credentials["region"])
                else:
                    pending += 1
            save(path, manifest)
            print(json.dumps({"scientist": row["id"], "storage_state": row["storage_state"]}), flush=True)
        if pending == 0 or time.monotonic() >= deadline:
            break
        time.sleep(15)
    print(json.dumps({"storage_pending": pending, "manifest": str(path)}))


def inventory(args):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = args.output / "baseline" / stamp
    nodes = kube("get", "nodes")
    pods = kube("get", "pods", "-A")
    deployments = kube("get", "deployments", "-A")
    save(target / "nodes.json", nodes)
    save(target / "pods.json", pods)
    save(target / "deployments.json", deployments)
    gpu_total = sum(int(n["status"].get("allocatable", {}).get("nvidia.com/gpu", 0)) for n in nodes["items"])
    gpu_reserved = sum(int(c.get("resources", {}).get("requests", {}).get("nvidia.com/gpu", 0))
                       for p in pods["items"] if p["status"]["phase"] not in ("Succeeded", "Failed")
                       and p["spec"].get("nodeName") for c in p["spec"]["containers"])
    summary = {"at": now(), "gpu_total": gpu_total, "gpu_reserved": gpu_reserved,
               "gpu_unreserved": gpu_total-gpu_reserved, "evidence": str(target)}
    with admin_client() as admin:
        for name, route in [("apps", "/admin/api/v1/apps"), ("models", "/admin/api/v1/models"),
                            ("capacity", "/admin/api/v1/capacity"), ("operations", "/admin/api/v1/operations?limit=100")]:
            response = admin.get(route)
            save(target / (name + ".json"), {"status": response.status_code,
                 "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else None})
        manifest = args.output / "scientists-private.json"
        if manifest.exists():
            key = json.loads(manifest.read_text())["scientists"][0]["api_key"]
            for name, route in [("serving-catalog", "/v1/models"), ("scientific-catalog", "/v1/scientific-models")]:
                response = httpx.get(ORIGIN+route, headers={"authorization": "Bearer " + key}, timeout=60)
                save(target / (name + ".json"), {"status": response.status_code, "body": response.json()})
    save(target / "summary.json", summary)
    print(json.dumps(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "storage", "inventory"))
    parser.add_argument("--output", type=Path, default=Path("/home/tux/secure-handoff/scientific-qualification-20260918"))
    parser.add_argument("--wait-seconds", type=int, default=600)
    args = parser.parse_args()
    os.umask(0o077)
    globals()[args.action](args)


if __name__ == "__main__":
    main()
