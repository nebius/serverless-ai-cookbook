"""Provision isolated scientist workbenches using the existing release template.

The input manifest and output directory contain credentials and must remain
outside Git. This is deployment setup, not scientific qualification evidence.
Run --only id1,id2 first; reruns reuse recorded resources. A pending create with
no receipt needs reconciliation instead of risking duplicate cloud resources.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

import httpx


def save(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def cloud(cli: list[str], arguments: list[str], folder: Path, label: str,
          payload: object | None = None) -> dict:
    result = subprocess.run(cli + arguments + ["--format", "json"] +
                            (["--file", "/dev/stdin"] if payload is not None else []),
                            input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, timeout=300)
    save(folder / (label + "-command.json"), {"returncode": result.returncode,
         "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError(label + " failed; protected command receipt contains details")
    return json.loads(result.stdout)


def deploy_command(command: list[str], environment: dict) -> subprocess.CompletedProcess:
    # deploy.sh starts a CLI child which may keep stdout open while waiting for
    # Serverless readiness. Killing only its shell on timeout leaves communicate
    # waiting forever. Stop our own process group; remote creation is reconciled.
    process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def reconcile_endpoint(cli: list[str], manifest: dict, state: dict, folder: Path) -> str:
    name = state.get("endpoint_name", "science-qualification-20260918-" + state["scientist_id"])
    # List is paginated, and the high-level CLI does not expose its page token.
    # Exact lookup must never mistake an absent first-page entry for no resource.
    # NotFound and every other lookup failure remain operator-reconciled: no
    # automatic second create follows an ambiguous original create.
    endpoint = cloud(cli, ["ai", "endpoint", "get-by-name", "--parent-id", manifest["project_id"],
                           "--name", name], folder, "endpoint-reconcile")
    metadata = endpoint.get("metadata", {})
    if metadata.get("name") != name or metadata.get("parent_id") != manifest["project_id"]:
        raise RuntimeError("Named endpoint identity differs; do not reuse it")
    if not metadata.get("id"):
        raise RuntimeError("Named endpoint has no ID; needs manual reconciliation")
    if endpoint.get("spec", {}).get("image") != state["image"]:
        raise RuntimeError("Named endpoint has a different image; do not reuse it")
    return metadata["id"]


def deploy(manifest: dict, person: dict, args: argparse.Namespace) -> dict:
    identifier = person["id"]
    chat_model = getattr(args, 'chat_model', 'zai-org/GLM-5.3-Flash')
    reasoning_effort = getattr(args, 'reasoning_effort', None)
    context_tokens = getattr(args, 'context_tokens', None)
    folder = args.output / identifier
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(folder / "setup.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cli = ["nebius", "--profile", args.profile, "--no-browser",
               "--auth-timeout", "20s", "--timeout", "120s", "--retries", "1"]
        state_path = folder / "deployment.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {
            "scientist_id": identifier, "tenant_id": person["tenant_id"],
            "principal_id": person["principal_id"], "bucket_name": person["bucket_name"],
            "email": person["email"], "image": args.image, "chat_model": chat_model,
            "reasoning_effort": reasoning_effort,
            "context_tokens": context_tokens,
            "project_id": manifest["project_id"], "state": "prepared",
            "endpoint_name": args.name_prefix + "-" + identifier}
        if state.get("endpoint_name", "science-qualification-20260918-" + identifier) != args.name_prefix + "-" + identifier:
            raise RuntimeError('Recorded endpoint name differs; use a separate preview output directory')
        if state.get('chat_model', 'zai-org/GLM-5.3-Flash') != chat_model:
            raise RuntimeError('Recorded chat model differs; use a separate comparison endpoint')
        if state.get('reasoning_effort') != reasoning_effort:
            raise RuntimeError('Recorded reasoning effort differs; use a separate comparison endpoint')
        if state.get('context_tokens') != context_tokens:
            raise RuntimeError('Recorded context ceiling differs; use a separate comparison endpoint')
        for key, value in {"image": args.image, "bucket_name": person["bucket_name"],
                           "principal_id": person["principal_id"],
                           "project_id": manifest["project_id"]}.items():
            if state[key] != value:
                raise RuntimeError("Recorded deployment identity changed: " + key)
        if state["state"] == "creating_secret":
            raise RuntimeError("An interrupted create must be reconciled using its protected receipt")
        if state["state"] == "creating_endpoint":
            state.update(endpoint_id=reconcile_endpoint(cli, manifest, state, folder), state="endpoint_created")
            save(state_path, state)
        if not state.get("secret_id") and args.source_deployments:
            source_path = args.source_deployments / identifier / 'deployment.json'
            source = json.loads(source_path.read_text())
            for field in ('scientist_id', 'tenant_id', 'principal_id', 'bucket_name', 'email', 'project_id'):
                if source.get(field) != state[field]:
                    raise RuntimeError('Source deployment identity differs: ' + field)
            secret_id = source.get('secret_id')
            if not secret_id:
                raise RuntimeError('Source deployment has no recorded secret')
            secret = cloud(cli, ['mysterybox', 'secret', 'get', '--id', secret_id], folder, 'secret-reuse-verify')
            if secret.get('metadata', {}).get('parent_id') != manifest['project_id']:
                raise RuntimeError('Source secret belongs to a different project')
            state.update(secret_id=secret_id, state='secret_reused', source_deployment=str(source_path))
            save(state_path, state)
        if not state.get("secret_id"):
            state["state"] = "creating_secret"
            save(state_path, state)
            secret = cloud(cli, ["mysterybox", "secret", "create"], folder, "secret-create", {
                "metadata": {"parent_id": manifest["project_id"],
                             "name": args.name_prefix + "-" + identifier},
                "spec": {"description": "Disposable scientist qualification workspace credentials",
                         "secret_version": {"set_primary": True, "payload": [
                             {"key": key, "string_value": value} for key, value in {
                                 "SCIENTIFIC_MODELS_API_KEY": person["api_key"],
                                 "S3_ACCESS_KEY_ID": person["s3_access_key_id"],
                                 "S3_SECRET_ACCESS_KEY": person["s3_secret_access_key"],
                                 "SEED_DEFAULT_USER_PASSWORD": person["password"],
                             }.items()]}}})
            state.update(secret_id=secret["metadata"]["id"], state="secret_created")
            save(state_path, state)
        if not state.get("endpoint_id"):
            environment = {**os.environ, "NEBIUS_PROFILE": args.profile,
                "NEBIUS_PROJECT_ID": manifest["project_id"],
                "NEBIUS_SUBNET_ID": manifest["subnet_id"],
                "ENDPOINT_NAME": args.name_prefix + "-" + identifier,
                "IMAGE": args.image, "TEAM_ID": person["tenant_id"],
                "TEAM_BUCKET_NAME": person["bucket_name"],
                "SEED_DEFAULT_USER_EMAIL": person["email"],
                "SCIENTIFIC_DEDICATED_CHAT_ENABLED": "false",
                "SCIENTIFIC_CHAT_MODEL": chat_model,
                "SCIENTIFIC_CHAT_REASONING_EFFORT": reasoning_effort or '',
                "SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS": str(context_tokens) if context_tokens else '',
                "SCIENTIFIC_CONTEXT_AUDIT_PATH": f'/workspace/{identifier}/qualification-context-sizes.jsonl'
                    if getattr(args, 'context_audit', False) else '',
                "TOKEN_FACTORY_SECRET_SELECTOR": manifest["token_factory_secret_selector"],
                "TAVILY_SECRET_SELECTOR": manifest["tavily_secret_selector"],
                "PLATFORM": manifest.get("platform", "cpu-d3"),
                "PRESET": manifest.get("preset", "4vcpu-16gb"),
                "DISK_SIZE": manifest.get("disk_size", "100Gi")}
            for key in ("SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR",
                        "S3_CREDENTIAL_SECRET_SELECTOR", "USER_PASSWORD_SECRET_SELECTOR"):
                environment[key] = state["secret_id"]
            if manifest.get("ssh_public_key_file"):
                environment["SSH_PUBLIC_KEY_FILE"] = manifest["ssh_public_key_file"]
            state["state"] = "creating_endpoint"
            save(state_path, state)
            try:
                result = deploy_command(["bash", str(Path(__file__).parents[1] / "scripts/deploy.sh")], environment)
                save(folder / "endpoint-create-command.json", {"returncode": result.returncode,
                     "stdout": result.stdout, "stderr": result.stderr})
                if result.returncode:
                    raise RuntimeError("Endpoint create failed; reconcile protected command receipt")
                endpoint = json.loads(result.stdout)
                endpoint_id = endpoint["metadata"]["id"]
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                # The CLI waits for readiness after creating the resource. Its
                # timeout does not mean creation failed, and some CLI versions
                # print a human summary despite --format json. Read exact state.
                endpoint_id = reconcile_endpoint(cli, manifest, state, folder)
            state.update(endpoint_id=endpoint_id, state="endpoint_created")
            save(state_path, state)
        deadline = time.monotonic() + args.wait_seconds
        while time.monotonic() < deadline:
            endpoint = cloud(cli, ["ai", "endpoint", "get", state["endpoint_id"]], folder, "endpoint-get")
            urls = endpoint.get("status", {}).get("public_endpoints", [])
            state["endpoint_state"] = endpoint.get("status", {}).get("state")
            if state["endpoint_state"] == "ERROR":
                error_path = folder / "endpoint-terminal-error.json"
                save(error_path, endpoint)
                state.update(state="endpoint_error", provider_status=endpoint["status"],
                             provider_error_receipt=str(error_path))
                save(state_path, state)
                raise RuntimeError("Endpoint entered terminal ERROR; inspect its protected provider receipt. "
                                   "No automatic retry or application setup was attempted.")
            url = next((value for value in urls if value.startswith("https://")), None)
            if url:
                state["url"] = url
                try:
                    with httpx.Client(base_url=url, timeout=60) as client:
                        response = client.post("/api/auth/login", json={"email": person["email"],
                                                                       "password": person["password"]})
                        response.raise_for_status()
                        token = response.json()["token"]
                        client.headers["Authorization"] = "Bearer " + token
                        response = client.put("/api/scientific-demos/settings", json={"api_key": person["api_key"]})
                        response.raise_for_status()
                        apps = client.get("/api/scientific-demos/apps")
                        apps.raise_for_status()
                        workspace = client.get("/api/scientific-demos/workspace")
                        workspace.raise_for_status()
                        actual_bucket = workspace.json()["info"].get("team_bucket_name")
                        if actual_bucket != person["bucket_name"]:
                            raise RuntimeError("Workspace bucket does not match the assigned scientist")
                        save(folder / "browser-state.json", {"cookies": [{
                            "name": item.name, "value": item.value, "domain": item.domain,
                            "path": item.path, "httpOnly": "HttpOnly" in item._rest,
                            "secure": item.secure, "sameSite": "Lax", "expires": item.expires or -1,
                        } for item in client.cookies.jar], "origins": []})
                        state.update(state="configured", authorized_apps=len(apps.json().get("data", [])),
                                     bucket_verified=True)
                        save(state_path, state)
                        return {key: state[key] for key in ("scientist_id", "endpoint_id", "url", "state",
                                                            "authorized_apps", "bucket_verified")}
                except httpx.HTTPError as error:
                    state["last_probe"] = type(error).__name__
            save(state_path, state)
            time.sleep(10)
        raise RuntimeError("Endpoint not ready before setup deadline; rerun to continue waiting")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--profile", default="sandbox2")
    parser.add_argument('--chat-model', default='zai-org/GLM-5.3-Flash',
                        help='Product-owner-approved Token Factory planning default; do not change without explicit approval.')
    parser.add_argument('--reasoning-effort', choices=['low', 'high', 'max'],
                        help='Explicit provider-supported planning variant; never changes token budget.')
    parser.add_argument('--context-tokens', type=int,
                        help='Explicit context ceiling for a controlled comparison, e.g. the existing GLM131072 ceiling.')
    parser.add_argument('--context-audit', action='store_true', help='Record only per-call context sizes in the scientist workspace.')
    parser.add_argument('--name-prefix', default='science-qualification-20260918')
    parser.add_argument('--source-deployments', type=Path, help='Reuse verified credentials from existing deployment receipts; preserve old instances.')
    parser.add_argument("--only", help="Comma-separated scientist IDs")
    parser.add_argument("--parallel", type=int, choices=[1, 2, 3, 4], default=2)
    parser.add_argument("--wait-seconds", type=int, default=1800)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.context_tokens is not None and args.context_tokens < 1024:
        parser.error('context-tokens must be at least1024')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}', args.name_prefix):
        parser.error('Use a short lowercase endpoint name prefix')
    os.umask(0o077)
    manifest = json.loads(args.manifest.read_text())
    people = manifest["scientists"]
    if args.only:
        selected = set(args.only.split(","))
        people = [person for person in people if person["id"] in selected]
        if {person["id"] for person in people} != selected:
            parser.error("Unknown --only scientist ID")
    if not 1 <= len(people) <= 10 or len({person["id"] for person in people}) != len(people):
        parser.error("Supply one to ten distinct scientist IDs")
    for person in people:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", person["id"]):
            parser.error("Scientist IDs must be lowercase letters, digits and hyphens")
        for key in ("email", "password", "api_key", "tenant_id", "principal_id", "bucket_name",
                    "s3_access_key_id", "s3_secret_access_key"):
            if not person.get(key):
                parser.error("Missing scientist field: " + key)
    if not args.execute:
        print(json.dumps({"action": "plan", "count": len(people), "project_id": manifest["project_id"],
                          "image": args.image, 'name_prefix': args.name_prefix,
                          'reuse_source_deployments': str(args.source_deployments) if args.source_deployments else None,
                          "scientists": [person["id"] for person in people]}))
        return
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    failed = False
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(deploy, manifest, person, args): person["id"] for person in people}
        for future in as_completed(futures):
            try:
                print(json.dumps(future.result()), flush=True)
            except Exception as error:
                failed = True
                print(json.dumps({"scientist_id": futures[future], "state": "setup_failed",
                                  "error": str(error)}), flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
