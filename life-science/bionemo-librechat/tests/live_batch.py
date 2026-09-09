"""One ESMFold2 synthetic batch with real uploads; never a LibreChat file bridge.

Uses the operator's public-input.json/public-input-manifest.json activation
fixtures, rematerialized for the current key. Requires the same SDK as
live_serving.py. Persist evidence outside the repository and reuse it to resume.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from live_serving import call, now, save


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify_bytes(ref, data):
    if len(data) != ref["size_bytes"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("Artifact size or SHA-256 mismatch")


async def upload(client, model, data, media_type, identity):
    measured = dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                    media_type=media_type, compression="none")
    begun = await call(client, "begin_scientific_artifact_upload",
                       dict(model_id=model, **measured, idempotency_key=identity))
    # Do not persist or display the reservation's signed handle.
    if len(data) > min(begun["max_content_bytes"], 1024 * 1024):
        raise ValueError("Fixture exceeds this small inline acceptance limit")
    ids = {key: begun[key] for key in ("operation_id", "upload_id")}
    await call(client, "put_scientific_artifact_bytes",
               dict(**ids, content_base64=base64.b64encode(data).decode()))
    ref = await call(client, "finalize_scientific_artifact_upload", ids)
    verify_bytes(ref, data)
    if any(ref[key] != value for key, value in measured.items()):
        raise ValueError("Finalized artifact metadata mismatch")
    return ref


async def download(client, ref, directory):
    # Server-issued UUID filenames only; signed handles never pass into evidence.
    from uuid import UUID
    identifier = str(UUID(ref["artifact_id"]))
    if ref["size_bytes"] > 1024 * 1024:
        raise ValueError("Output requires separate large-file acceptance")
    response = await call(client, "read_scientific_artifact_bytes", {"artifact_id": identifier})
    data = base64.b64decode(response["content_base64"], validate=True)
    verify_bytes(ref, data)
    path = directory / (identifier + ".artifact")
    with path.open("wb") as handle:
        os.chmod(path, 0o600)
        handle.write(data)
    return data


async def run(args):
    endpoint, key = os.environ["FS2_MCP_URL"], os.environ["FS2_API_KEY"]
    identity = hashlib.sha256((endpoint + "\n" + key).encode()).hexdigest()
    args.evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = args.evidence / "esmfold2-batch.json"
    record = json.loads(path.read_text()) if path.exists() else {
        "identity": identity, "idempotency_key": "skill-batch-" + str(uuid4()),
        "model": "esmfold2", "created_at": now(), "state": "prepared"}
    if identity != record["identity"]:
        raise ValueError("Evidence belongs to a different endpoint or key")
    save(path, record)
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + key},
                                 timeout=60, trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http)) as client:
            schema = await call(client, "get_model_schema", {"model_id": "esmfold2", "protocol": "scientific-batch-v1"})
            record["schema"] = schema
            contract = schema["contracts"][0]
            save(path, record)
            if not args.execute:
                print("ESMFold2 batch contract retrieved; no upload or run submitted.")
                return
            if not record.get("operation_id"):
                data = canonical(json.loads((args.activation / "public-input.json").read_text()))
                manifest = json.loads((args.activation / "public-input-manifest.json").read_text())
                if len(manifest["entries"]) != 1:
                    raise ValueError("Expected the single ESMFold2 acceptance input")
                if "input" not in record:
                    record["input"] = await upload(client, "esmfold2", data, "application/json", record["idempotency_key"] + "-input")
                    save(path, record)
                manifest["entries"][0]["artifact"] = record["input"]
                if "manifest" not in record:
                    record["manifest"] = await upload(client, "esmfold2", canonical(manifest),
                        "application/vnd.fs2.scientific-manifest+json", record["idempotency_key"] + "-manifest")
                    save(path, record)
                if "arguments" not in record:
                    request = dict(contract["examples"][0], input_manifest=record["manifest"],
                                   idempotency_key=record["idempotency_key"])
                    request["client_context"] = {"display_name": "Scientific agent ESMFold2 acceptance"}
                    Draft202012Validator(contract["input_schema"]).validate(request)
                    record["arguments"] = request
                    save(path, record)
                accepted = await call(client, contract["tool_name"], record["arguments"])
                record["accepted"] = accepted
                save(path, record)
                operation = accepted.get("operation", accepted)
                record["operation_id"] = operation.get("id") or operation["operation_id"]
                save(path, record)
            deadline = time.monotonic() + args.wait_seconds
            while True:
                status = await call(client, "get_scientific_status", {"operation_id": record["operation_id"]})
                record.update(status=status, checked_at=now())
                record["events"] = await call(client, "list_scientific_events", {"operation_id": record["operation_id"]})
                save(path, record)
                print(json.dumps({"model": "esmfold2", "operation_id": record["operation_id"],
                                  "state": status["operation"]["status"],
                                  "stages": [{"id": s["stage_id"], "state": s["status"]}
                                             for s in status["batch"]["stages"]]}), flush=True)
                operation = status.get("operation", status)
                if operation.get("status") in {"failed", "cancelled", "expired", "preempted"}:
                    break
                if status["batch"].get("result_published"):
                    record["result"] = await call(client, "get_scientific_result", {"operation_id": record["operation_id"]})
                    save(path, record)
                    result = record["result"]
                    if (result["operation_id"] != record["operation_id"]
                            or result["terminal_status"] != "succeeded"
                            or result["semantic_validation"]["status"] != "passed"
                            or result["input_manifest"] != record["manifest"]):
                        raise ValueError("Batch result identity or semantic validation failed")
                    manifest_bytes = await download(client, result["output_manifest"], args.evidence)
                    manifest = json.loads(manifest_bytes)
                    downloaded = []
                    for entry in manifest["entries"]:
                        await download(client, entry["artifact"], args.evidence)
                        downloaded.append(entry["artifact"])
                    record.update(verified_downloads=downloaded, state="verified", verified_at=now())
                    save(path, record)
                    print(json.dumps({"model": "esmfold2", "state": "verified", "downloaded": len(downloaded)}), flush=True)
                    break
                if time.monotonic() >= deadline:
                    break
                await asyncio.sleep(10)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activation", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=30)
    asyncio.run(run(parser.parse_args()))
