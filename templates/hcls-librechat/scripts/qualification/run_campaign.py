#!/usr/bin/env python3
"""Durable customer-key MCP study runner, with independent artifact evaluation.

Each scientist executes at most one case at a time. Retries preserve the logical
request identity; every request, response, wait and terminal failure is retained.
This runner qualifies the public MCP path. LibreChat sessions are a separate gate.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, deque
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import time
import traceback
from urllib.parse import quote

import httpx
from jsonschema import Draft202012Validator

from manage_campaign import ORIGIN, save


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def journal(folder, event):
    """Append-only evidence survives retries and cohort resumes."""
    with open(folder / "events.jsonl", "a", opener=lambda p, f: os.open(p, f, 0o600)) as output:
        output.write(json.dumps({"at": now(), **event}, sort_keys=True) + "\n")


def elapsed(receipt):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(receipt["started_at"])).total_seconds()


def interleave(cases):
    groups = defaultdict(deque)
    for case in cases:
        groups[case["model_id"]].append(case)
    ordered = []
    while any(groups.values()):
        for group in groups.values():
            if group:
                ordered.append(group.popleft())
    return ordered


def evaluator_environment():
    """Fail before any GPU admission if this interpreter cannot score results."""
    packages = {"numpy": "numpy", "Bio": "biopython", "gemmi": "gemmi",
                "rdkit": "rdkit", "h5py": "h5py", "nibabel": "nibabel", "PIL": "Pillow"}
    for module in packages:
        try:
            importlib.import_module(module)
        except ImportError as error:
            raise RuntimeError("Qualification evaluator dependencies are missing; use the pinned "
                               "requirements.txt environment before submitting model work") from error
    return {package: version(package) for package in packages.values()}


def freeze_assignments(output, *, cohort, manifest_sha256, cases, people):
    """Reject a resume that would silently move logical work to another key."""
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Case IDs must be unique within a cohort")
    value = {"cohort": cohort, "manifest_sha256": manifest_sha256,
             "selected_cases_sha256": digest(cases), "people": [p["id"] for p in people],
             "assignments": {p["id"]: case_ids[index::len(people)] for index, p in enumerate(people)}}
    path = output / "assignments.json"
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError("Resume selection changes frozen case ownership; use the original selection or a new cohort")
    elif (output / "campaign.json").exists():
        raise ValueError("Legacy cohort has no frozen assignment; preserve its original process/receipts and migrate explicitly")
    else:
        save(path, value)
    return value


class ToolError(RuntimeError):
    def __init__(self, error):
        self.error = error if isinstance(error, dict) else {"message": str(error)}
        super().__init__(self.error.get("code", "tool_error"))


def unpack(result):
    value = result.get("structuredContent")
    if value is None:
        text = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
        value = json.loads(text[0]) if len(text) == 1 else {"content": result.get("content", [])}
    if result.get("isError"):
        raise ToolError(value.get("error", value) if isinstance(value, dict) else value)
    return value


class MCP:
    def __init__(self, key):
        self.client = httpx.Client(base_url=ORIGIN, timeout=120, trust_env=False,
            headers={"authorization": "Bearer " + key, "accept": "application/json, text/event-stream"})
        self.counter = 0

    def close(self):
        self.client.close()

    def rpc(self, method, params=None, *, notification=False):
        self.counter += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            body["id"] = self.counter
        response = self.client.post("/mcp", json=body)
        response.raise_for_status()
        if response.headers.get("mcp-session-id"):
            self.client.headers["mcp-session-id"] = response.headers["mcp-session-id"]
        if notification:
            return None
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            messages = [json.loads(line[5:].strip()) for line in response.text.splitlines()
                        if line.startswith("data:") and line[5:].strip() != "[DONE]"]
            message = next(m for m in messages if m.get("id") == self.counter)
        else:
            message = response.json()
        if "error" in message:
            raise ToolError(message["error"])
        return message["result"]

    def initialize(self):
        result = self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                         "clientInfo": {"name": "scientific-qualification", "version": "1"}})
        self.client.headers["mcp-protocol-version"] = result["protocolVersion"]
        self.rpc("notifications/initialized", notification=True)
        return result

    def call(self, name, arguments):
        return unpack(self.rpc("tools/call", {"name": name, "arguments": arguments}))


def artifact(client, reference, folder):
    aid = reference["artifact_id"]
    response = client.get("/v1/artifacts/" + quote(aid, safe="") + "/content")
    response.raise_for_status()
    data = response.content
    if len(data) != reference["size_bytes"] or hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValueError("Artifact hash/size mismatch")
    target = folder / (aid + ".artifact")
    with open(target, "wb", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(data)
    return data


def resolve(client, envelope, folder):
    value = envelope.get("result", envelope)
    if isinstance(value, dict) and value.get("schema") == "fs2-serve.nebius.ai/operation-artifact-result/v1":
        raw = artifact(client, value["artifact"], folder)
        if "json" in value.get("content_type", ""):
            return json.loads(raw)
        return {"content_type": value.get("content_type"), "artifact_verified": True,
                "bytes": len(raw)}
    return value


def execute_case(mcp, person, case, args, manifest_path, tools):
    folder = args.output / person["id"] / case["case_id"]
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / "receipt.json"
    request_id = args.cohort + "-" + digest({"person": person["id"], "case": case})[:32]
    identity = {"case_sha256": digest(case), "key_id": person["key_id"], "cohort": args.cohort}
    receipt = json.loads(path.read_text()) if path.exists() else {
        "identity": identity, "case_id": case["case_id"], "model_id": case["model_id"],
        "scientist": person["id"], "tenant_id": person["tenant_id"], "started_at": now(),
        "idempotency_key": request_id, "state": "prepared", "attempts": [], "path": "public-typed-mcp"}
    if receipt["identity"] != identity:
        raise ValueError("Resume directory identity changed")
    if receipt["state"] in {"verified", "semantic_failed", "failed", "cancelled", "expired", "preempted", "unsupported_case", "rejected"}:
        return receipt
    save(path, receipt)
    journal(folder, {"event": "resume_or_start", "state": receipt["state"], "operation_id": receipt.get("operation_id")})
    if case["mode"] not in {"native", "scientific-batch"}:
        receipt.update(state="unsupported_case", error="Runner mode not implemented yet")
        save(path, receipt)
        return receipt
    batch = case["mode"] == "scientific-batch"
    if batch:
        from batch_transport import prepare_arguments
        arguments = prepare_arguments(mcp.client, case, manifest_path.parent, folder, request_id, receipt)
    else:
        from batch_transport import prepare_native_arguments
        arguments = {**prepare_native_arguments(mcp.client, case, manifest_path.parent, folder, request_id, receipt),
                     "idempotency_key": request_id, "wait_seconds": 0}
    tool = tools.get(case["tool"])
    if not tool:
        receipt.update(state="unsupported_case", error="Tool not found in live authorized catalog")
        save(path, receipt)
        return receipt
    Draft202012Validator(tool["inputSchema"]).validate(arguments)
    save(folder / "contract.json", tool)
    save(folder / "request.json", arguments)
    start = time.monotonic()
    while not receipt.get("operation_id"):
        if time.monotonic() - start > args.case_timeout:
            receipt.update(state="admission_deferred", updated_at=now())
            save(path, receipt)
            return receipt
        receipt["state"] = "submitting"
        save(path, receipt)
        try:
            accepted = mcp.call(case["tool"], arguments)
            save(folder / "submission.json", accepted)
            operation = accepted["operation"] if isinstance(accepted.get("operation"), dict) else accepted
            operation_id = operation.get("id") or operation.get("operation_id")
            if not operation_id:
                raise ValueError("Admission did not return a durable operation ID")
            receipt.update(operation_id=operation_id, state=operation.get("status", "admitted"),
                           admitted_at=now())
            receipt["attempts"].append({"at": now(), "outcome": "admitted"})
        except ToolError as error:
            receipt["attempts"].append({"at": now(), "outcome": "tool_error", "error": error.error})
            save(path, receipt)
            if error.error.get("durable_admission") is False and error.error.get("retryable"):
                receipt["state"] = "admission_wait"
                save(path, receipt)
                time.sleep(min(30, max(3, error.error.get("retry_after_seconds") or 5)))
                continue
            receipt.update(state="rejected", error=error.error)
            save(path, receipt)
            return receipt
        except (httpx.HTTPError, ValueError, KeyError) as error:
            # Keep an ambiguous admission durable; a later runner can reconcile
            # the exact idempotency key. Never generate a new key after timeout.
            receipt.update(state="admission_unknown", error_type=type(error).__name__)
            if isinstance(error, httpx.HTTPStatusError):
                # Record transport evidence without echoing headers, bearer
                # credentials or a potentially reflected raw response body.
                receipt["http_status"] = error.response.status_code
                receipt["response_request_id"] = error.response.headers.get("x-request-id")
                receipt["response_body_sha256"] = hashlib.sha256(error.response.content).hexdigest()
            save(path, receipt)
            return receipt
        save(path, receipt)
    while time.monotonic() - start < args.case_timeout:
        try:
            status = mcp.call("get_scientific_status" if batch else "get_operation", {"operation_id": receipt["operation_id"]})
            operation = status["operation"] if isinstance(status.get("operation"), dict) else status
        except (httpx.HTTPError, ToolError) as error:
            receipt["attempts"].append({"at": now(), "outcome": "poll_error", "error_type": type(error).__name__})
            save(path, receipt)
            time.sleep(5)
            continue
        save(folder / "operation.json", operation)
        journal(folder, {"event": "status", "status": status})
        receipt.update(state=operation["status"], updated_at=now())
        if operation["status"] in {"failed", "cancelled", "expired", "preempted"}:
            receipt.update(error_code=operation.get("error_code"), error_detail=operation.get("error_detail"),
                           elapsed_seconds=elapsed(receipt))
            save(path, receipt)
            return receipt
        if operation["status"] == "succeeded" and (not batch or status.get("batch", {}).get("result_published")):
            envelope = mcp.call("get_scientific_result" if batch else "get_operation_result", {"operation_id": receipt["operation_id"]})
            save(folder / "result-envelope.json", envelope)
            if batch:
                from batch_transport import resolve as resolve_batch
                value = resolve_batch(mcp.client, envelope, folder, artifact)
            else:
                value = resolve(mcp.client, envelope, folder)
            save(folder / "result.json", value)
            if case["expected"]["evaluator"] == "speech_transcription":
                from speech_study import evaluate as evaluate_speech
                evaluation = evaluate_speech(case, value)
            else:
                from evaluators import evaluate
                evaluation = evaluate(case, value, manifest_path.parent)
            if batch and value.get("platform_semantic_validation", {}).get("status") != "passed":
                evaluation.update(service_semantic_pass=False, platform_semantic_validation_failed=True)
            save(folder / "evaluation.json", evaluation)
            receipt.update(state="verified" if evaluation["service_semantic_pass"] else "semantic_failed",
                           elapsed_seconds=elapsed(receipt), finished_at=now(),
                           service_semantic_pass=evaluation["service_semantic_pass"])
            save(path, receipt)
            return receipt
        save(path, receipt)
        time.sleep(args.poll_seconds)
    receipt.update(state="still_pending", updated_at=now(), elapsed_seconds=elapsed(receipt))
    save(path, receipt)
    return receipt


def worker(person, cases, args, manifest_path):
    folder = args.output / person["id"]
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(folder / "worker.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        predecessor = None
        if args.wait_for_cohort:
            previous_lock = args.wait_for_cohort / person["id"] / "worker.lock"
            predecessor = open(previous_lock, "a")
            # A scientist completes the preceding study before starting this
            # queue. Other scientists can progress independently.
            fcntl.flock(predecessor, fcntl.LOCK_EX)
        mcp = MCP(person["api_key"])
        try:
            save(folder / "initialize.json", mcp.initialize())
            tools = {t["name"]: t for t in mcp.rpc("tools/list")["tools"]}
            save(folder / "tools.json", {"tools": list(tools.values())})
            results = []
            for case in cases:
                if datetime.now(timezone.utc) >= datetime.fromisoformat(args.deadline):
                    break
                if (folder / "pause-after-current").exists() and not (folder / case["case_id"] / "receipt.json").exists():
                    # Leave existing durable work to finish before handing
                    # this exact identity to an interactive scientist.
                    journal(folder, {"event": "paused_before_new_case", "next_case": case["case_id"]})
                    break
                try:
                    result = execute_case(mcp, person, case, args, manifest_path, tools)
                except Exception as error:
                    result = {"case_id": case["case_id"], "scientist": person["id"],
                              "state": "harness_error", "error_type": type(error).__name__,
                              "traceback": traceback.format_exc()}
                    save(folder / case["case_id"] / "harness-error.json", result)
                results.append(result)
                journal(folder / case["case_id"], {"event": "case_outcome", "receipt": result})
                print(json.dumps({k: result.get(k) for k in
                    ("scientist", "case_id", "model_id", "state", "operation_id", "elapsed_seconds", "error_type")}), flush=True)
                save(folder / "summary.json", results)
                # Never admit another operation when the previous one may still
                # consume this scientist's concurrency slot.
                if result["state"] in {"admission_unknown", "still_pending", "harness_error"}:
                    break
                time.sleep(args.think_seconds)
            return results
        finally:
            mcp.close()
            if predecessor:
                predecessor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scientists", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--only", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--models", default="", help="Comma-separated App IDs to select")
    parser.add_argument("--interleave", action="store_true", help="Mix Apps instead of exhausting one model first")
    parser.add_argument("--wait-for-cohort", type=Path, help="Wait for each scientist's preceding worker lock")
    parser.add_argument("--parallel", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--poll-seconds", type=float, default=3)
    parser.add_argument("--think-seconds", type=float, default=2)
    parser.add_argument("--case-timeout", type=int, default=1800)
    parser.add_argument("--deadline", default="2026-09-19T06:04:00+00:00")
    args = parser.parse_args()
    os.umask(0o077)
    evaluation_environment = evaluator_environment()
    manifest = json.loads(args.manifest.read_text())
    cases = manifest["cases"]
    if args.models:
        cases = [case for case in cases if case["model_id"] in args.models.split(",")]
    if args.interleave:
        cases = interleave(cases)
    cases = cases[:args.limit or None]
    people = json.loads(args.scientists.read_text())["scientists"]
    if args.only:
        people = [p for p in people if p["id"] in args.only.split(",")]
    people = people[:args.parallel]
    if not people or not cases:
        raise ValueError("Campaign needs selected identities and cases")
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", c["case_id"]) for c in cases):
        raise ValueError("Case IDs must be safe path components")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    save(args.output / ("evaluator-environment-" + digest(evaluation_environment)[:12] + ".json"),
         evaluation_environment)
    freeze_assignments(args.output, cohort=args.cohort, manifest_sha256=digest(manifest), cases=cases, people=people)
    if not (args.output / "campaign.json").exists():
        save(args.output / "campaign.json", {"at": now(), "cohort": args.cohort, "cases": len(cases),
             "manifest_sha256": digest(manifest), "people": [p["id"] for p in people], "deadline": args.deadline})
    with ThreadPoolExecutor(max_workers=len(people)) as pool:
        futures = [pool.submit(worker, person, cases[index::len(people)], args, args.manifest)
                   for index, person in enumerate(people)]
        results = []
        for future in as_completed(futures):
            results.extend(future.result())
    save(args.output / "summary.json", results)
    counts = {state: sum(r["state"] == state for r in results) for state in {r["state"] for r in results}}
    print(json.dumps({"cohort": args.cohort, "counts": counts, "rows": len(results)}), flush=True)


if __name__ == "__main__":
    main()
