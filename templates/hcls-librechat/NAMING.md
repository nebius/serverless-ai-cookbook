# Scientific AI naming and compatibility

This client uses one customer-facing vocabulary across the website, workbench,
MCP connection, skills and platform documentation.

| Concept | Canonical name | Where it appears |
| --- | --- | --- |
| Product | **Nebius Scientific AI** | Page headers, handovers and product documentation |
| Hosted resource | **Scientific AI App** | Catalog entries, grants, runs and settings |
| MCP service | **Scientific AI MCP server** | Protocol and integration documentation |
| LibreChat MCP connection ID | `scientific-ai-apps` | `librechat.yaml`, generated tool suffixes and saved agents |
| MCP display title | **Nebius Scientific AI Apps** | MCP settings and protocol metadata |
| Customer assistant | **Nebius Scientific AI Agent** | LibreChat agent and model selector |
| NVIDIA ecosystem | **NVIDIA BioNeMo** | Only actual BioNeMo models, source lineage, badges and toolkit compatibility |
| Conversational model service | **Nebius Token Factory** | Chat-model provider, separate from Scientific AI Apps |

An App can be an NVIDIA BioNeMo model, another NVIDIA model, a community model,
an internally packaged runtime or a multi-step workflow. Therefore **BioNeMo is
never the name of the complete catalog or MCP server**.

## Compatibility boundary

Older LibreChat configurations used the local MCP connection ID
`bionemo-models`. It never identified a distinct backend endpoint. New images
use only `scientific-ai-apps`; this changes LibreChat-generated tool suffixes
from `_mcp_bionemo-models` to `_mcp_scientific-ai-apps`. The seeded agent is
updated as one unit so its server name and tool allowlist cannot diverge.

Do not configure both names simultaneously: that would expose duplicate tools
for the same endpoint. Historical chats and evidence may retain the old tool ID
as provenance. A migration must preserve those records while using the canonical
name for new calls.

The environment variables `SCIENTIFIC_MODELS_MCP_URL`,
`SCIENTIFIC_MODELS_API_BASE_URL` and `SCIENTIFIC_MODELS_API_KEY` remain stable
deployment interfaces. They describe model/App access and contain no BioNeMo
product claim. Internal paths such as `/opt/bionemo`, package names such as
`fs2_serve`, Kubernetes labels and versioned `fs2-serve.nebius.ai` schemas are
implementation identifiers, not customer-facing product names; changing them
requires a separate compatibility migration.

The source directory `life-science/bionemo-librechat` is retained for repository
history and image-build compatibility. The maintained image consumes only its
shared agent-instruction and viewer assets; those assets use the canonical
Scientific AI vocabulary. The directory's old standalone config and README are
historical templates, not the maintained customer deployment.

## Review rule

Use “BioNeMo” only when removing it would make a statement less accurate—for
example NVIDIA BioNeMo Agent Toolkit compatibility or a BioNeMo source
repository. Use “Scientific AI App,” “Scientific AI MCP server,” or “Nebius
Scientific AI” for shared platform behavior.
