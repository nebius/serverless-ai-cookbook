#!/usr/bin/env python3
"""Hardened, demo-only ClawBio MCP surface for the workbench."""

from __future__ import annotations

from typing import Any

from clawbio.mcp_server import (
    describe_skill as upstream_describe_skill,
    list_skills as upstream_list_skills,
    run_skill as upstream_run_skill,
)
from mcp.server.fastmcp import FastMCP


DEMO_ALIASES = {
    "gwas": "gwas",
    "gwas-lookup": "gwas",
    "gwas-prs": "prs",
    "pharmgx": "pharmgx",
    "pharmgx-reporter": "pharmgx",
    "prs": "prs",
    "profile": "profile",
    "profile-report": "profile",
}

app = FastMCP("clawbio-workbench")


def _mark_image_readiness(entry: dict[str, Any]) -> dict[str, Any]:
    item = dict(entry)
    candidates = {str(item.get("name", "")).lower(), str(item.get("cli_alias", "")).lower()}
    item["demo_runnable_in_image"] = any(candidate in DEMO_ALIASES for candidate in candidates)
    return item


@app.tool()
def list_skills(query: str = "") -> list[dict[str, Any]]:
    """Search 95 redistributable ClawBio contracts; runnable status is reported per entry."""
    return [_mark_image_readiness(entry) for entry in upstream_list_skills(query)]


@app.tool()
def describe_skill(name: str) -> dict[str, Any]:
    """Read one ClawBio contract and its image-specific demo readiness."""
    return _mark_image_readiness(upstream_describe_skill(name))


@app.tool()
def run_skill(skill: str, demo: bool = False) -> dict[str, Any]:
    """Run an approved bundled demo only; arbitrary patient/local-file access is unavailable."""
    normalized = skill.strip().lower()
    registry_key = DEMO_ALIASES.get(normalized)
    if demo is not True:
        raise PermissionError("Only explicit ClawBio demo runs are enabled in the browser workbench.")
    if registry_key is None:
        raise PermissionError(
            "This ClawBio contract is available for discovery, but its demo is not qualified in this image."
        )
    result = upstream_run_skill(registry_key, demo=True, timeout=300)
    return {
        "skill": normalized,
        "demo": True,
        "success": bool(result.get("success")),
        "exit_code": result.get("exit_code"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


if __name__ == "__main__":
    app.run()
