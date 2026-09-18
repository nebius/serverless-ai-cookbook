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


def request_json(base_url: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc


def wait_rest(base_url: str, token: str, run_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        record = request_json(base_url, token, "GET", f"/v1/runs/{run_id}")
        if record["status"] in TERMINAL_STATES:
            return record
        time.sleep(2)
    raise TimeoutError(f"REST run {run_id} did not finish within {timeout_seconds} seconds")


def verify_artifact(base_url: str, token: str, record: dict[str, Any]) -> dict[str, Any]:
    artifact = next(item for item in record["artifacts"] if item["name"] == "result.json")
    request = urllib.request.Request(
        f"{base_url}{artifact['download_path']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    digest = hashlib.sha256(body).hexdigest()
    if digest != artifact["sha256"]:
        raise RuntimeError("downloaded artifact SHA-256 does not match API metadata")
    return {"name": artifact["name"], "bytes": len(body), "sha256": digest}


async def mcp_smoke(
    base_url: str,
    token: str,
    steps: int,
    gpu_mode: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx2.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(f"{base_url}/mcp", http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                tool_names = sorted(tool.name for tool in tools.tools)
                expected = {"get_capabilities", "submit_run", "get_run", "list_run_artifacts"}
                if not expected.issubset(tool_names):
                    raise RuntimeError(f"MCP tools missing: {sorted(expected.difference(tool_names))}")

                capabilities = await session.call_tool("get_capabilities", {})
                if capabilities.is_error:
                    raise RuntimeError("MCP get_capabilities failed")
                submitted = await session.call_tool(
                    "submit_run",
                    {
                        "input": {"steps": steps, "gpu_mode": gpu_mode, "threads": 1},
                        "client_request_id": f"customer-mcp-{uuid.uuid4().hex}",
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
                    record = result.structured_content
                    if record["status"] in TERMINAL_STATES:
                        return {
                            "server": initialized.server_info.name,
                            "protocol_version": initialized.protocol_version,
                            "tools": tool_names,
                            "record": record,
                        }
                    await asyncio.sleep(2)
                raise TimeoutError(f"MCP run {run_id} did not finish within {timeout_seconds} seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise one HCLS GROMACS endpoint through REST and MCP.")
    parser.add_argument("endpoint_url", help="Managed HTTPS endpoint URL, without a trailing slash")
    parser.add_argument("--steps", type=int, default=10_000)
    parser.add_argument("--gpu-mode", choices=("gpu", "cpu", "auto"), default="gpu")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    token = os.environ.get("HCLS_ENDPOINT_TOKEN")
    if not token:
        raise SystemExit("Set HCLS_ENDPOINT_TOKEN in the environment; never put it in the URL")
    base_url = args.endpoint_url.rstrip("/")

    health = request_json(base_url, token, "GET", "/v1/health/ready")
    rest_submission = request_json(
        base_url,
        token,
        "POST",
        "/v1/runs",
        {
            "input": {"steps": args.steps, "gpu_mode": args.gpu_mode, "threads": 1},
            "client_request_id": f"customer-rest-{uuid.uuid4().hex}",
            "research_use_acknowledgement": True,
        },
    )
    rest_record = wait_rest(base_url, token, rest_submission["run_id"], args.timeout)
    if rest_record["status"] != "succeeded":
        raise RuntimeError(f"REST run failed: {rest_record.get('error')}")
    rest_artifact = verify_artifact(base_url, token, rest_record)

    mcp_result = asyncio.run(mcp_smoke(base_url, token, args.steps, args.gpu_mode, args.timeout))
    mcp_record = mcp_result["record"]
    if mcp_record["status"] != "succeeded":
        raise RuntimeError(f"MCP run failed: {mcp_record.get('error')}")
    # Prove that the run created through MCP is addressable through the REST API
    # and that the same endpoint token can retrieve its artifact.
    shared_record = request_json(base_url, token, "GET", f"/v1/runs/{mcp_record['run_id']}")
    mcp_artifact = verify_artifact(base_url, token, shared_record)

    print(
        json.dumps(
            {
                "health": health,
                "rest": {
                    "run_id": rest_record["run_id"],
                    "status": rest_record["status"],
                    "ns_per_day": rest_record["result"].get("ns_per_day"),
                    "artifact": rest_artifact,
                },
                "mcp": {
                    "server": mcp_result["server"],
                    "protocol_version": mcp_result["protocol_version"],
                    "run_id": mcp_record["run_id"],
                    "status": mcp_record["status"],
                    "ns_per_day": mcp_record["result"].get("ns_per_day"),
                    "artifact_verified_through_rest": mcp_artifact,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
