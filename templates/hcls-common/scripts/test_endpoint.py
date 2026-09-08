#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


def request_json(
    base_url: str,
    token: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc


def require_unauthorized(base_url: str) -> None:
    try:
        urllib.request.urlopen(f"{base_url}/healthz", timeout=30)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return
        raise RuntimeError(f"unauthenticated request returned HTTP {exc.code}") from exc
    raise RuntimeError("endpoint accepted an unauthenticated health request")


def wait_run(base_url: str, token: str, run_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        record = request_json(base_url, token, "GET", f"/v1/runs/{run_id}")
        if record["status"] in TERMINAL_STATES:
            return record
        time.sleep(2)
    raise TimeoutError(f"run {run_id} did not finish within {timeout_seconds} seconds")


def verify_result_artifact(base_url: str, token: str, record: dict[str, Any]) -> dict[str, Any]:
    artifact = next(item for item in record["artifacts"] if item["name"] == "result.json")
    request = urllib.request.Request(
        f"{base_url}{artifact['download_path']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    digest = hashlib.sha256(body).hexdigest()
    if digest != artifact["sha256"]:
        raise RuntimeError("downloaded result artifact does not match its published SHA-256")
    return {"bytes": len(body), "sha256": digest}


async def mcp_run(
    base_url: str,
    token: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http_client:
        async with streamable_http_client(f"{base_url}/mcp", http_client=http_client) as streams:
            read, write = streams
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                names = sorted(tool.name for tool in tools.tools)
                expected = {"get_capabilities", "submit_run", "get_run", "list_run_artifacts"}
                if not expected.issubset(names):
                    raise RuntimeError(f"MCP tools missing: {sorted(expected.difference(names))}")
                submitted = await session.call_tool(
                    "submit_run",
                    {
                        "input": payload,
                        "client_request_id": f"mcp-smoke-{uuid.uuid4().hex}",
                        "research_use_acknowledgement": True,
                    },
                )
                if submitted.is_error or not submitted.structured_content:
                    raise RuntimeError("MCP submit_run failed")
                run_id = str(submitted.structured_content["run_id"])
                deadline = time.monotonic() + timeout_seconds
                while time.monotonic() < deadline:
                    result = await session.call_tool("get_run", {"run_id": run_id})
                    if result.is_error or not result.structured_content:
                        raise RuntimeError("MCP get_run failed")
                    if result.structured_content["status"] in TERMINAL_STATES:
                        return {
                            "server": initialized.server_info.name,
                            "protocol_version": initialized.protocol_version,
                            "tools": names,
                            "record": result.structured_content,
                        }
                    await asyncio.sleep(2)
                raise TimeoutError(f"MCP run {run_id} did not finish in time")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test an HCLS endpoint through REST and MCP.")
    parser.add_argument("endpoint_url")
    parser.add_argument("--payload", required=True, help="JSON object passed as the run input")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    token = os.environ.get("HCLS_ENDPOINT_TOKEN", "")
    if not token:
        raise SystemExit("Set HCLS_ENDPOINT_TOKEN; never put it in the URL")
    payload = json.loads(args.payload)
    if not isinstance(payload, dict):
        raise SystemExit("--payload must be a JSON object")
    base_url = args.endpoint_url.rstrip("/")

    require_unauthorized(base_url)
    health = request_json(base_url, token, "GET", "/v1/health/ready")
    submitted = request_json(
        base_url,
        token,
        "POST",
        "/v1/runs",
        {
            "input": payload,
            "client_request_id": f"rest-smoke-{uuid.uuid4().hex}",
            "research_use_acknowledgement": True,
        },
    )
    rest = wait_run(base_url, token, submitted["run_id"], args.timeout)
    if rest["status"] != "succeeded":
        raise RuntimeError(f"REST run failed: {rest.get('error')}")
    rest_artifact = verify_result_artifact(base_url, token, rest)

    mcp = asyncio.run(mcp_run(base_url, token, payload, args.timeout))
    if mcp["record"]["status"] != "succeeded":
        raise RuntimeError(f"MCP run failed: {mcp['record'].get('error')}")
    shared = request_json(base_url, token, "GET", f"/v1/runs/{mcp['record']['run_id']}")
    mcp_artifact = verify_result_artifact(base_url, token, shared)
    print(
        json.dumps(
            {
                "health": health,
                "rest": {
                    "run_id": rest["run_id"],
                    "result": rest["result"],
                    "artifact": rest_artifact,
                },
                "mcp": {
                    "server": mcp["server"],
                    "protocol_version": mcp["protocol_version"],
                    "tools": mcp["tools"],
                    "run_id": mcp["record"]["run_id"],
                    "result": mcp["record"]["result"],
                    "artifact_verified_through_rest": mcp_artifact,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
