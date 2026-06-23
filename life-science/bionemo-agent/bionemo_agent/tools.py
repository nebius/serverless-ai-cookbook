"""Tooling for a research-only BioNeMo assistant."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from urllib import error, request
from urllib.parse import urljoin, urlparse

from nat.builder.builder import Builder
from nat.builder.function import FunctionGroup
from nat.cli.register_workflow import register_function_group
from nat.data_models.function import FunctionGroupBaseConfig
from pydantic import BaseModel, Field

from bionemo_agent.catalog import (
    SAFETY_NOTICE,
    SERVICE_PATHS,
    list_capabilities,
    route_request,
)

logger = logging.getLogger(__name__)


class BioNeMoResearchToolsConfig(FunctionGroupBaseConfig, name="bionemo_research_tools"):
    """Configuration for BioNeMo research assistant tools."""

    include: list[str] = Field(
        default_factory=lambda: [
            "list_capabilities",
            "route_request",
            "call_bionemo_skill",
            "call_bionemo_service",
        ],
        description="The BioNeMo tool functions to expose to the agent.",
    )
    bionemo_base_url: str | None = Field(
        default=None,
        description="Optional base URL for a BioNeMo-compatible service.",
    )
    bionemo_api_key: str | None = Field(
        default=None,
        description="Optional bearer token for the BioNeMo-compatible service.",
    )
    request_timeout: float = Field(
        default=30.0,
        gt=0.0,
        description="Timeout, in seconds, for BioNeMo-compatible HTTP calls.",
    )


class BioNeMoServiceRequest(BaseModel):
    """Request for a configured BioNeMo-compatible HTTP service."""

    method: str = Field(
        default="POST",
        description="HTTP method for the configured service call. Supported values: GET or POST.",
    )
    path: str = Field(
        default="/v1/chat/completions",
        description="Relative API path on the configured BioNeMo-compatible service.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON payload to send to the configured BioNeMo-compatible service.",
    )


class BioNeMoSkillRequest(BaseModel):
    """Request for a named self-hosted BioNeMo skill."""

    skill: str = Field(
        description=(
            "One of capabilities, chat, protein_embedding, structure_prediction, "
            "literature_retrieval, molecular_dynamics, or genomics_generation."
        ),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON payload for the selected BioNeMo skill.",
    )


def _validate_relative_path(path: str) -> str:
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise ValueError("BioNeMo service path must be relative to BIONEMO_BASE_URL.")
    normalized = "/" + path.lstrip("/")
    if normalized == "/":
        raise ValueError("BioNeMo service path must not be empty.")
    return normalized


def _request_json(
    method: str, url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if method == "POST" else None
    req = request.Request(url=url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as response:
        response_body = response.read().decode("utf-8")
        if not response_body:
            return {"status_code": response.status, "body": None}
        try:
            body_json = json.loads(response_body)
        except json.JSONDecodeError:
            body_json = response_body
        return {"status_code": response.status, "body": body_json}


async def call_bionemo_service(
    config: BioNeMoResearchToolsConfig, service_request: BioNeMoServiceRequest
) -> str:
    """Call a configured BioNeMo-compatible service or return a dry-run payload."""
    path = _validate_relative_path(service_request.path)
    method = service_request.method.strip().upper()
    if method not in {"GET", "POST"}:
        raise ValueError("BioNeMo service method must be GET or POST.")

    if not config.bionemo_base_url:
        return json.dumps(
            {
                "configured": False,
                "safety_notice": SAFETY_NOTICE,
                "message": (
                    "Set BIONEMO_BASE_URL and, if required, BIONEMO_API_KEY to enable "
                    "live service calls."
                ),
                "request": {
                    "method": method,
                    "path": path,
                    "payload": service_request.payload,
                },
            },
            indent=2,
        )

    url = urljoin(config.bionemo_base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {"Accept": "application/json"}
    if method == "POST":
        headers["Content-Type"] = "application/json"
    if config.bionemo_api_key:
        headers["Authorization"] = f"Bearer {config.bionemo_api_key}"

    try:
        result = await asyncio.to_thread(
            _request_json,
            method,
            url,
            service_request.payload,
            headers,
            config.request_timeout,
        )
    except error.HTTPError as exc:
        logger.warning("BioNeMo service call failed with HTTP status %s", exc.code)
        response_body = exc.read().decode("utf-8", errors="replace")
        return json.dumps(
            {"configured": True, "status_code": exc.code, "error": response_body}, indent=2
        )
    except error.URLError as exc:
        logger.warning("BioNeMo service call failed: %s", exc)
        return json.dumps({"configured": True, "error": str(exc.reason)}, indent=2)

    result["configured"] = True
    return json.dumps(result, indent=2)


async def call_bionemo_skill(
    config: BioNeMoResearchToolsConfig, skill_request: BioNeMoSkillRequest
) -> str:
    """Call a named self-hosted BioNeMo skill through BIONEMO_BASE_URL."""
    skill = skill_request.skill.strip().lower().replace("-", "_")
    if skill not in SERVICE_PATHS:
        return json.dumps(
            {
                "configured": bool(config.bionemo_base_url),
                "error": f"Unknown BioNeMo skill: {skill_request.skill}",
                "available_skills": sorted(SERVICE_PATHS),
            },
            indent=2,
        )

    return await call_bionemo_service(
        config=config,
        service_request=BioNeMoServiceRequest(
            method="GET" if skill == "capabilities" else "POST",
            path=SERVICE_PATHS[skill],
            payload=skill_request.payload,
        ),
    )


@register_function_group(config_type=BioNeMoResearchToolsConfig)
async def bionemo_research_tools(
    config: BioNeMoResearchToolsConfig, _builder: Builder
) -> AsyncGenerator[FunctionGroup, None]:
    """Create BioNeMo research assistant tools."""
    group = FunctionGroup(config=config)

    async def _list_capabilities(query: str = "") -> str:
        """List BioNeMo-oriented research capabilities. Provide a query to filter them."""
        return list_capabilities(query=query)

    async def _route_request(request_text: str) -> str:
        """Route a research request to a BioNeMo capability and Serverless deployment shape."""
        return route_request(request_text=request_text)

    async def _call_bionemo_service(service_request: BioNeMoServiceRequest) -> str:
        """Call a configured BioNeMo-compatible HTTP service with a JSON payload."""
        return await call_bionemo_service(config=config, service_request=service_request)

    async def _call_bionemo_skill(skill_request: BioNeMoSkillRequest) -> str:
        """Call a named self-hosted BioNeMo skill with a JSON payload."""
        return await call_bionemo_skill(config=config, skill_request=skill_request)

    group.add_function(
        "list_capabilities", _list_capabilities, description=_list_capabilities.__doc__
    )
    group.add_function("route_request", _route_request, description=_route_request.__doc__)
    group.add_function(
        "call_bionemo_service",
        _call_bionemo_service,
        description=_call_bionemo_service.__doc__,
    )
    group.add_function(
        "call_bionemo_skill",
        _call_bionemo_skill,
        description=_call_bionemo_skill.__doc__,
    )

    yield group
