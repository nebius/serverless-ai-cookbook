#!/usr/bin/env python3
"""Submit one real scientific-batch input and retain hash-verified evidence.

The output directory is the resume boundary. Re-running it polls the saved
operation; it never silently resubmits after ambiguous admission.
"""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


TERMINAL = {"failed", "cancelled", "expired", "preempted"}


class ExplicitRejection(RuntimeError):
    def __init__(self, error: dict):
        allowed = ("type", "code", "message", "request_id", "idempotency_key",
                   "retryable", "retry_after_seconds", "durable_admission")
        self.error = {key: error[key] for key in allowed if key in error}
        super().__init__(self.error.get("message", "Gateway explicitly rejected the request."))


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def check(response):
    if not response.is_success:
        raise RuntimeError(f"Platform returned HTTP {response.status_code}; inspect the saved evidence.")
    return response


def unpack(response):
    data = response.model_dump(mode="json", by_alias=True)
    if data.get("isError"):
        text = next((item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"), "")
        try:
            error = json.loads(text).get("error", {})
        except (TypeError, ValueError, AttributeError):
            error = {}
        if error.get("durable_admission") is False:
            raise ExplicitRejection(error)
        raise RuntimeError("MCP tool failed: " + text[:500])
    if data.get("structuredContent") is not None:
        return data["structuredContent"]
    texts = [item["text"] for item in data.get("content", []) if item.get("type") == "text"]
    if len(texts) != 1:
        raise RuntimeError("Expected one JSON MCP result.")
    return json.loads(texts[0])


async def call(client, name: str, arguments: dict):
    return unpack(await client.call_tool(name, arguments))


async def upload(http, model: str, data: bytes, media_type: str, compression: str,
                 idempotency_key: str) -> dict:
    measured = {"model_id": model, "sha256": digest(data), "size_bytes": len(data),
                "media_type": media_type, "compression": compression}
    begun = check(await http.post("/v1/scientific-artifacts/uploads", json=measured,
                                 headers={"idempotency-key": idempotency_key})).json()
    if len(data) <= begun["max_content_bytes"]:
        target = begun["content_path"]
        if not isinstance(target, str) or not target.startswith("/") or target.startswith("//"):
            raise RuntimeError("Unsafe same-origin upload path.")
        check(await http.put(target, content=data, headers={"content-type": media_type,
                                                            "content-length": str(len(data))}))
    else:
        handle = begun.get("handle", {})
        if urlparse(handle.get("url", "")).scheme != "https":
            raise RuntimeError("Large upload did not return an HTTPS object-storage handle.")
        async with httpx2.AsyncClient(timeout=600, trust_env=False, follow_redirects=False) as storage:
            check(await storage.put(handle["url"], content=data, headers=handle.get("headers", {})))
    result = check(await http.post(
        "/v1/scientific-artifacts/uploads/" + quote(begun["upload_id"], safe="") + ":finalize",
        json={"operation_id": begun["operation_id"]},
    )).json()
    for key, value in measured.items():
        if key != "model_id" and result.get(key) != value:
            raise RuntimeError("Finalized artifact metadata mismatch.")
    return result


async def download(http, reference: dict, target: Path) -> dict:
    response = check(await http.get("/v1/artifacts/" + quote(reference["artifact_id"], safe="") + "/content"))
    data = response.content
    if len(data) != reference["size_bytes"] or digest(data) != reference["sha256"]:
        raise RuntimeError("Downloaded artifact hash or size mismatch.")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(target, "wb", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
        output.write(data)
    return {"artifact_id": reference["artifact_id"], "path": str(target),
            "size_bytes": len(data), "sha256": digest(data)}


async def run(args) -> None:
    endpoint = os.environ["SCIENTIFIC_MODELS_MCP_URL"]
    key = os.environ["SCIENTIFIC_MODELS_API_KEY"]
    origin = endpoint.removesuffix("/mcp").removesuffix("/mcp/")
    source = args.source.read_bytes()
    parameters = json.loads(args.parameters.read_text())
    identity = {"model_id": args.model, "source_sha256": digest(source),
                "parameters_sha256": digest(canonical(parameters)), "endpoint": endpoint,
                "caller_fingerprint": digest(key.encode()), "idempotency_key": args.idempotency_key}
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_path = args.output / "receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
        "identity": identity, "state": "prepared", "manifest_id": "scientist-cohort-" + str(uuid4())}
    if receipt["identity"] != identity:
        raise ValueError("Output directory belongs to a different request.")
    save(receipt_path, receipt)
    headers = {"authorization": "Bearer " + key}
    async with httpx2.AsyncClient(base_url=origin, headers=headers, timeout=180,
                                  trust_env=False, follow_redirects=False) as http:
        async with httpx2.AsyncClient(headers=headers, timeout=180, trust_env=False) as mcp_http:
            async with Client(streamable_http_client(endpoint, http_client=mcp_http)) as client:
                tools = (await client.list_tools()).tools
                tool = next((item for item in tools if item.name == args.tool), None)
                if tool is None:
                    raise RuntimeError("Requested scientific-batch tool is unavailable.")
                save(args.output / "contract.json", tool.model_dump(mode="json", by_alias=True))
                if not receipt.get("operation_id"):
                    if receipt["state"] in {"submitting", "admission_unknown"}:
                        raise RuntimeError("Previous admission is ambiguous; inspect evidence before retrying.")
                    if "source_artifact" not in receipt:
                        receipt["source_artifact"] = await upload(
                            http, args.model, source, args.media_type, args.compression,
                            args.idempotency_key + "-source")
                        save(receipt_path, receipt)
                    if parameters.get("source", {}).get("kind") == "uploaded-bundle":
                        parameters = {**parameters, "source": {
                            "kind": "uploaded-bundle", **receipt["source_artifact"]}}
                    manifest = {"schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1",
                                "manifest_id": receipt["manifest_id"], "entries": [{
                                    "name": args.entry_name, "semantic_type": args.semantic_type,
                                    "artifact": receipt["source_artifact"]}]}
                    save(args.output / "input-manifest.json", manifest)
                    if "manifest_artifact" not in receipt:
                        receipt["manifest_artifact"] = await upload(
                            http, args.model, canonical(manifest),
                            "application/vnd.fs2.scientific-manifest+json", "none",
                            args.idempotency_key + "-manifest")
                        save(receipt_path, receipt)
                    request = {"schema": "fs2-serve.nebius.ai/scientific-run-request/v1",
                               "operation": args.operation, "service_class": args.service_class,
                               "input_manifest": receipt["manifest_artifact"], "parameters": parameters,
                               "client_context": {"display_name": args.display_name,
                                                  "correlation_id": args.idempotency_key},
                               "idempotency_key": args.idempotency_key}
                    Draft202012Validator(tool.input_schema).validate(request)
                    save(args.output / "request.json", request)
                    receipt["state"] = "submitting"
                    save(receipt_path, receipt)
                    try:
                        accepted = await call(client, args.tool, request)
                    except ExplicitRejection as error:
                        receipt.update(state="rejected", last_rejection=error.error)
                        save(receipt_path, receipt)
                        raise
                    except Exception:
                        receipt["state"] = "admission_unknown"
                        save(receipt_path, receipt)
                        raise
                    save(args.output / "submission.json", accepted)
                    operation = accepted.get("operation", accepted)
                    receipt.update(operation_id=operation.get("id") or operation["operation_id"],
                                   state=operation.get("status", "queued"))
                    save(receipt_path, receipt)
                deadline = time.monotonic() + args.wait_seconds
                while True:
                    status = await call(client, "get_scientific_status", {"operation_id": receipt["operation_id"]})
                    save(args.output / "status.json", status)
                    operation = status.get("operation", status)
                    receipt["state"] = operation["status"]
                    save(receipt_path, receipt)
                    if operation["status"] in TERMINAL:
                        raise RuntimeError("Scientific batch ended in " + operation["status"] + ".")
                    if status.get("batch", {}).get("result_published"):
                        result = await call(client, "get_scientific_result", {"operation_id": receipt["operation_id"]})
                        save(args.output / "result.json", result)
                        if result.get("terminal_status") != "succeeded" or result.get("semantic_validation", {}).get("status") != "passed":
                            raise RuntimeError("Published result did not pass semantic validation.")
                        manifest_info = await download(http, result["output_manifest"], args.output / "output-manifest.json")
                        output_manifest = json.loads((args.output / "output-manifest.json").read_text())
                        artifacts = []
                        for index, entry in enumerate(output_manifest.get("entries", [])):
                            extension = ".artifact"
                            artifacts.append(await download(http, entry["artifact"], args.output / f"output-{index:02d}{extension}"))
                        receipt.update(state="verified", output_manifest=manifest_info,
                                       verified_artifacts=artifacts)
                        save(receipt_path, receipt)
                        print(json.dumps({"model": args.model, "operation_id": receipt["operation_id"],
                                          "state": "verified", "artifacts": len(artifacts)}))
                        return
                    if time.monotonic() >= deadline:
                        print(json.dumps({"model": args.model, "operation_id": receipt["operation_id"],
                                          "state": receipt["state"], "resume": str(args.output)}))
                        return
                    await asyncio.sleep(args.poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--media-type", required=True)
    parser.add_argument("--compression", choices=("none", "gzip", "zstd"), default="none")
    parser.add_argument("--entry-name", required=True)
    parser.add_argument("--semantic-type", required=True)
    parser.add_argument("--parameters", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--service-class", choices=("customer-batch", "bulk-backfill"), default="customer-batch")
    parser.add_argument("--wait-seconds", type=float, default=1800)
    parser.add_argument("--poll-seconds", type=float, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
