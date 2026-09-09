"""Small typed-MCP acceptance calls; discovery-only unless --execute is set.

Requires mcp 2.x, httpx2 and jsonschema. Read FS2_MCP_URL and FS2_API_KEY from
the environment. Keep --evidence outside source control. Reuse that directory
to resume saved operations (including after a process/client disconnect).

Execution is sequential by default because a participant key can have a
bounded outstanding-operation allowance. Use --parallel-submissions only when
the tested account is explicitly provisioned for concurrent admission.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

MODELS = ("diffdock", "proteinmpnn", "genmol", "molmim", "msa-search-pdb70",
          "openfold3", "qwen3-8b", "boltz2", "openfold2", "phenoage")
TERMINAL = {"succeeded", "failed", "cancelled", "preempted", "expired"}


def now():
    return datetime.now(timezone.utc).isoformat()


def unpack(response):
    value = response.model_dump(mode="json", by_alias=True)
    if value.get("isError"):
        raise ValueError("MCP tool returned isError: " + json.dumps(value))
    if value.get("structuredContent") is not None:
        return value["structuredContent"]
    texts = [item["text"] for item in value.get("content", []) if item["type"] == "text"]
    if len(texts) != 1:
        raise ValueError("Expected one structured or JSON tool result")
    return json.loads(texts[0])


async def call(client, name, arguments):
    return unpack(await client.call_tool(name, arguments))


def save(path, value):
    # Only private synthetic serving receipts; no auth headers or signed handles.
    text = json.dumps(value, indent=2)
    secret = os.environ.get("FS2_API_KEY", "")
    if secret:
        text = text.replace(secret, "[REDACTED]")
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        os.chmod(temporary, 0o600)
        handle.write(text + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def announce(model, record):
    print(json.dumps({"model": model, "state": record.get("state"),
                      "operation_id": record.get("operation_id"),
                      "result_saved": "result" in record}), flush=True)


async def settle(client, records, evidence, wait_seconds):
    deadline = time.monotonic() + wait_seconds
    while True:
        pending = False
        for model, record in records.items():
            if not record.get("operation_id") or "result" in record:
                continue
            path = evidence / (model + ".json")
            operation = await call(client, "get_operation", {"operation_id": record["operation_id"]})
            previous = record["state"]
            record.update(state=operation["status"], operation=operation, checked_at=now())
            if operation["status"] == "succeeded" and operation.get("result_available"):
                result = await call(client, "get_operation_result", {"operation_id": record["operation_id"]})
                if result["operation"]["id"] != record["operation_id"] or result.get("result") is None:
                    raise ValueError("Result identity mismatch or missing result")
                record["result"] = result["result"]
            elif operation["status"] not in TERMINAL or operation["status"] == "succeeded":
                pending = True
            save(path, record)
            if previous != record["state"] or "result" in record:
                announce(model, record)
        if not pending or time.monotonic() >= deadline:
            break
        await asyncio.sleep(min(10, max(0, deadline - time.monotonic())))


async def run(args):
    endpoint, key = os.environ["FS2_MCP_URL"], os.environ["FS2_API_KEY"]
    identity = hashlib.sha256((endpoint + "\n" + key).encode()).hexdigest()
    args.evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = {}
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + key},
                                 timeout=60, trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http)) as client:
            if args.refresh_catalog:
                tools, cursor = [], None
                while True:
                    listing = await client.list_tools(cursor=cursor) if cursor else await client.list_tools()
                    tools.extend(tool.model_dump(mode="json", by_alias=True) for tool in listing.tools)
                    cursor = getattr(listing, "next_cursor", None)
                    if not cursor:
                        break
                save(args.evidence / "mcp-tools.json", tools)
                schemas = {}
                for tool in tools:
                    meta = tool.get("_meta") or {}
                    if "fs2_model_id" not in meta:
                        continue
                    model, protocol = meta["fs2_model_id"], meta["fs2_protocol"]
                    schema = await call(client, "get_model_schema", {"model_id": model, "protocol": protocol})
                    contract = next(c for c in schema["contracts"] if c["tool_name"] == tool["name"])
                    if contract["input_schema"] != tool["inputSchema"]:
                        raise ValueError("Tool and discovery schemas disagree")
                    for example in contract["examples"]:
                        Draft202012Validator(contract["input_schema"]).validate(example)
                    schemas[model] = {"protocol": protocol, "schema": schema}
                save(args.evidence / "model-schemas.json", {"schemas": schemas})
                print(json.dumps({"tools": len(tools), "verified_contracts": len(schemas)}), flush=True)
            if args.check_invalid:
                if not args.execute:
                    raise ValueError("--check-invalid requires --execute")
                schema = await call(client, "get_model_schema", {"model_id": "openfold2", "protocol": "native"})
                contract = schema["contracts"][0]
                invalid = dict(contract["examples"][0], unsupported_acceptance_field=True)
                invalid["idempotency_key"] = "skill-invalid-" + str(uuid4())
                invalid["wait_seconds"] = 0
                try:
                    await client.call_tool(contract["tool_name"], invalid)
                except MCPError as exc:
                    error = exc.error.model_dump(mode="json")
                    if error["code"] != -32602 or (error.get("data") or {}).get("type") != "model_input_validation":
                        raise
                    save(args.evidence / "invalid-input.json", {"checked_at": now(), "error": error})
                    print("Invalid input: -32602 model_input_validation confirmed", flush=True)
                else:
                    raise ValueError("Invalid input did not return the expected JSON-RPC rejection")
            for model in args.models:
                path = args.evidence / (model + ".json")
                if path.exists():
                    record = json.loads(path.read_text())
                    if record["identity"] != identity:
                        raise ValueError("Evidence belongs to a different endpoint or key")
                else:
                    schema = await call(client, "get_model_schema", {"model_id": model})
                    protocol = "openai-chat" if model == "qwen3-8b" else "native"
                    contract = next(c for c in schema["contracts"] if c["protocol"] == protocol)
                    payload = dict(contract["examples"][0])
                    payload.update(idempotency_key="skill-live-" + str(uuid4()), wait_seconds=0)
                    Draft202012Validator(contract["input_schema"]).validate(payload)
                    record = {"identity": identity, "model": model, "schema": schema,
                              "tool": contract["tool_name"], "arguments": payload,
                              "created_at": now(), "state": "prepared"}
                    save(path, record)
                records[model] = record
                if args.execute and not record.get("operation_id") and record["state"] in {"prepared", "submitting"}:
                    # Persist the exact payload before admission; uncertain transport
                    # failures may replay only this same idempotency identity.
                    record.update(state="submitting", submitted_at=now())
                    save(path, record)
                    try:
                        accepted = await call(client, record["tool"], record["arguments"])
                        record.update(operation_id=accepted["id"], accepted=accepted,
                                      state=accepted["status"])
                    except MCPError as exc:
                        record.update(state="rejected", error=str(exc))
                    except ValueError as exc:
                        record.update(state="tool_error", error=str(exc))
                    save(path, record)
                announce(model, record)
                if args.execute and not args.parallel_submissions:
                    await settle(client, {model: record}, args.evidence, args.wait_seconds)
                    if record.get("state") not in TERMINAL or (
                        record.get("state") == "succeeded" and "result" not in record
                    ):
                        # Preserve the saved operation for a later resume. Do
                        # not submit another model while this key still has an
                        # unfinished operation occupying its admission slot.
                        return

            if not args.execute:
                return
            if args.parallel_submissions:
                await settle(client, records, args.evidence, args.wait_seconds)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=MODELS, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument("--check-invalid", action="store_true")
    parser.add_argument("--parallel-submissions", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=60)
    asyncio.run(run(parser.parse_args()))
