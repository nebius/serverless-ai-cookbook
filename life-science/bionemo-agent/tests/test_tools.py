import json

import pytest

from bionemo_agent.tools import (
    BioNeMoResearchToolsConfig,
    BioNeMoServiceRequest,
    bionemo_research_tools,
    call_bionemo_service,
    list_capabilities,
    route_request,
)


def test_list_capabilities_filters_for_protein_embeddings():
    result = json.loads(list_capabilities("protein sequence embedding"))
    slugs = [capability["slug"] for capability in result["capabilities"]]

    assert "facebook-esm-2-650m-protein-embedding" in slugs
    assert "Research-only" in result["safety_notice"]


def test_route_request_recommends_job_for_molecular_dynamics():
    result = json.loads(route_request("run a short OpenMM molecular dynamics simulation"))

    assert result["recommended_capability"]["slug"] == "openmm-md-8-5-1-wrapper"
    assert "Job" in result["recommended_capability"]["serverless_fit"]


@pytest.mark.asyncio
async def test_call_bionemo_service_returns_dry_run_when_unconfigured():
    config = BioNeMoResearchToolsConfig()
    service_request = BioNeMoServiceRequest(path="/v1/example", payload={"sequence": "MKTAYIAK"})

    result = json.loads(await call_bionemo_service(config=config, service_request=service_request))

    assert result["configured"] is False
    assert result["request"]["path"] == "/v1/example"
    assert result["request"]["payload"] == {"sequence": "MKTAYIAK"}


@pytest.mark.asyncio
async def test_call_bionemo_service_rejects_absolute_paths():
    config = BioNeMoResearchToolsConfig(bionemo_base_url="https://example.test")
    service_request = BioNeMoServiceRequest(path="https://malicious.example/v1/example", payload={})

    with pytest.raises(ValueError, match="relative"):
        await call_bionemo_service(config=config, service_request=service_request)


@pytest.mark.asyncio
async def test_function_group_builds_registered_tools():
    async with bionemo_research_tools(BioNeMoResearchToolsConfig(), None) as group:
        assert group is not None
