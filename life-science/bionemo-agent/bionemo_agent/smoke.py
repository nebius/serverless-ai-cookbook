"""Container smoke checks that do not require an LLM API key."""

from __future__ import annotations

import argparse
import asyncio
import json

from bionemo_agent.tools import (
    BioNeMoResearchToolsConfig,
    BioNeMoServiceRequest,
    call_bionemo_service,
    list_capabilities,
    route_request,
)


async def _run(query: str) -> None:
    capabilities = json.loads(list_capabilities(query))
    route = json.loads(route_request(query))
    dry_run = json.loads(
        await call_bionemo_service(
            BioNeMoResearchToolsConfig(),
            BioNeMoServiceRequest(path="/v1/example", payload={"query": query}),
        )
    )

    if not capabilities["capabilities"]:
        raise RuntimeError("capability catalog is empty")
    if not route["recommended_capability"]["slug"]:
        raise RuntimeError("route recommendation is empty")
    if dry_run["configured"] is not False:
        raise RuntimeError("dry-run service call did not report configured=false")

    print(
        json.dumps(
            {
                "ok": True,
                "query": query,
                "recommended_slug": route["recommended_capability"]["slug"],
                "dry_run_path": dry_run["request"]["path"],
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a BioNeMo agent container smoke check.")
    parser.add_argument(
        "--query",
        default="protein sequence embedding",
        help="Research-only query to route through the local capability catalog.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.query))


if __name__ == "__main__":
    main()
