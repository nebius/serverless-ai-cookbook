"""Tooling for a research-only BioNeMo assistant."""

from __future__ import annotations

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

logger = logging.getLogger(__name__)

SAFETY_NOTICE = (
    "Research-only. Do not send PHI, patient records, confidential customer data, unpublished "
    "customer sequences, or proprietary molecule/protein inputs unless explicit approval exists. "
    "Do not use this agent for diagnosis, treatment recommendations, triage, patient-specific "
    "interpretation, or clinical decision support."
)

CAPABILITIES: list[dict[str, Any]] = [
    {
        "slug": "nvidia-nv-embedqa-e5-v5",
        "name": "NVIDIA NV-EmbedQA E5 v5",
        "task": "Biomedical retrieval and literature-search embeddings",
        "keywords": ["retrieval", "rag", "literature", "embedding", "pubmed", "semantic search"],
        "when_to_use": "Embed biomedical documents, abstracts, and research questions.",
        "sample_input": "Synthetic abstract: EGFR inhibitors in nonclinical kinase assays.",
        "serverless_fit": (
            "Endpoint for interactive RAG assistants; Job for batch embedding refreshes."
        ),
    },
    {
        "slug": "stanfordcrfm-biomedlm-2-7b",
        "name": "BioMedLM 2.7B",
        "task": "Biomedical text generation and educational summarization",
        "keywords": ["summarization", "biomedical", "question answering", "education", "text"],
        "when_to_use": "Summarize public biomedical text or explain nonclinical research concepts.",
        "sample_input": "Public abstract text about kinase inhibition assays.",
        "serverless_fit": "Endpoint for chat-style assistance; Job for batch summaries.",
    },
    {
        "slug": "boltz2-nim",
        "name": "Boltz2 NIM",
        "task": "Protein structure and biomolecular complex prediction",
        "keywords": ["protein", "structure", "complex", "binding", "folding", "boltz"],
        "when_to_use": "Prepare structure-prediction requests from public or synthetic sequences.",
        "sample_input": "Public benchmark protein sequence or synthetic toy sequence.",
        "serverless_fit": (
            "Job for bounded prediction tasks; Endpoint only for interactive low-latency use."
        ),
    },
    {
        "slug": "facebook-esm-2-650m-protein-embedding",
        "name": "ESM-2 650M Protein Embedding",
        "task": "Protein sequence embeddings",
        "keywords": ["protein", "embedding", "sequence", "esm", "representation"],
        "when_to_use": "Embed public or synthetic protein sequences for similarity search.",
        "sample_input": "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP.",
        "serverless_fit": (
            "Endpoint for interactive embedding demos; Job for larger sequence batches."
        ),
    },
    {
        "slug": "openmm-md-8-5-1-wrapper",
        "name": "OpenMM MD 8.5.1 Wrapper",
        "task": "Small molecular dynamics demo runs",
        "keywords": ["molecular dynamics", "simulation", "openmm", "trajectory", "energy"],
        "when_to_use": (
            "Run bounded, educational MD samples and return timing or artifact metadata."
        ),
        "sample_input": "Small public benchmark system with short run length.",
        "serverless_fit": "Job is preferred because MD runs are bounded batch workloads.",
    },
    {
        "slug": "huggingfacebio-carbon-3b-vllm-cuda13",
        "name": "Carbon 3B",
        "task": "Generative DNA/RNA sequence foundation model fallback",
        "keywords": ["genomics", "dna", "rna", "sequence", "carbon", "generative"],
        "when_to_use": (
            "Use as a conservative genomics demo path when larger models are unavailable."
        ),
        "sample_input": "Synthetic nonclinical DNA prompt.",
        "serverless_fit": "Endpoint for interactive sequence examples; Job for scripted batches.",
    },
]


class BioNeMoResearchToolsConfig(FunctionGroupBaseConfig, name="bionemo_research_tools"):
    """Configuration for BioNeMo research assistant tools."""

    include: list[str] = Field(
        default_factory=lambda: ["list_capabilities", "route_request", "call_bionemo_service"],
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

    path: str = Field(
        default="/v1/chat/completions",
        description="Relative API path on the configured BioNeMo-compatible service.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON payload to send to the configured BioNeMo-compatible service.",
    )


def _tokenize(text: str) -> set[str]:
    return {
        token.strip(".,:;()[]{}").lower()
        for token in text.split()
        if token.strip(".,:;()[]{}")
    }


def _capability_score(capability: dict[str, Any], query_tokens: set[str]) -> int:
    haystack = _tokenize(
        " ".join(
            [
                str(capability["slug"]),
                str(capability["name"]),
                str(capability["task"]),
                str(capability["when_to_use"]),
                " ".join(capability["keywords"]),
            ]
        )
    )
    return len(query_tokens & haystack)


def get_matching_capabilities(query: str = "", limit: int | None = None) -> list[dict[str, Any]]:
    """Return BioNeMo capabilities ranked by keyword overlap."""
    query_tokens = _tokenize(query)

    if not query_tokens:
        matches = CAPABILITIES
    else:
        scored = [
            (capability, _capability_score(capability, query_tokens))
            for capability in CAPABILITIES
        ]
        matches = [
            capability
            for capability, score in sorted(scored, key=lambda item: item[1], reverse=True)
            if score
        ]
        if not matches:
            matches = CAPABILITIES

    if limit is not None:
        return matches[:limit]
    return matches


def list_capabilities(query: str = "") -> str:
    """List BioNeMo-oriented research capabilities."""
    return json.dumps(
        {
            "safety_notice": SAFETY_NOTICE,
            "capabilities": get_matching_capabilities(query=query),
        },
        indent=2,
    )


def route_request(request_text: str) -> str:
    """Recommend a BioNeMo capability and Nebius Serverless shape."""
    capabilities = get_matching_capabilities(query=request_text, limit=3)
    primary = capabilities[0]
    return json.dumps(
        {
            "safety_notice": SAFETY_NOTICE,
            "request": request_text,
            "recommended_capability": primary,
            "alternatives": capabilities[1:],
            "serverless_guidance": {
                "endpoint": (
                    "Use a Nebius Serverless Endpoint for an interactive assistant served by "
                    "NVIDIA NeMo Agent Toolkit."
                ),
                "job": (
                    "Use a Nebius Serverless Job for one-shot or bounded batch work such as "
                    "embedding refreshes, protein prediction, or molecular dynamics."
                ),
            },
        },
        indent=2,
    )


def _validate_relative_path(path: str) -> str:
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise ValueError("BioNeMo service path must be relative to BIONEMO_BASE_URL.")
    normalized = "/" + path.lstrip("/")
    if normalized == "/":
        raise ValueError("BioNeMo service path must not be empty.")
    return normalized


def _post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
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

    if not config.bionemo_base_url:
        return json.dumps(
            {
                "configured": False,
                "safety_notice": SAFETY_NOTICE,
                "message": (
                    "Set BIONEMO_BASE_URL and, if required, BIONEMO_API_KEY to enable "
                    "live service calls."
                ),
                "request": {"path": path, "payload": service_request.payload},
            },
            indent=2,
        )

    url = urljoin(config.bionemo_base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {"Content-Type": "application/json"}
    if config.bionemo_api_key:
        headers["Authorization"] = f"Bearer {config.bionemo_api_key}"

    try:
        result = await asyncio.to_thread(
            _post_json, url, service_request.payload, headers, config.request_timeout
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

    group.add_function(
        "list_capabilities", _list_capabilities, description=_list_capabilities.__doc__
    )
    group.add_function("route_request", _route_request, description=_route_request.__doc__)
    group.add_function(
        "call_bionemo_service",
        _call_bionemo_service,
        description=_call_bionemo_service.__doc__,
    )

    yield group
