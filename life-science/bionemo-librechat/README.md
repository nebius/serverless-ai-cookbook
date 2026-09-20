# BioNeMo LibreChat workbench

This is the historical workbench template. New deployments use
[`templates/hcls-librechat`](../../templates/hcls-librechat), and all maintained
customer skills live in [`skills/scientific-ai`](../../skills/scientific-ai).
The historical artifact adapter below is not the current hosted file workflow.

This is the LibreChat replacement for the public OpenClaw BioNeMo workbench.
It is deployed as a separate Serverless endpoint and never updates the existing
`ba:latest` image or `bionemo-3` endpoint.

The image bundles the BioNeMo skills, grouped newcomer tutorials, a Token
Factory provider, the BioNeMo model MCP, Tavily search MCP, owner-authorized
workspace/file/shell tools, and an embedded 3Dmol protein viewer.

## fs2 typed-MCP handover

The shared gateway skill and seeded agent instructions are updated for flat
typed model tools, `get_model_schema`, durable operation polling and dynamic
per-user tool discovery. Before deploying this workbench to multiple customers,
apply the [LibreChat handover](https://github.com/rene-tech/nebius-solutions-library/blob/main/k8s-inference/integrations/librechat/HANDOVER.md): the current
`librechat.yaml` still uses one shared gateway key, and `artifact-mcp.py` still
implements the older ClawBio upload protocol. Replace those pieces before
claiming per-user billing attribution or fs2 file/artifact workflows.

## Onboarding

The welcome screen names the four tutorial groups: Protein Folding, Docking and
Design, Sequence and MSA, and Genomics and Cell Biology. The
`scientific-agent-tutorials` deployment skill provides model lists, example
workflows, and fair benchmark instructions for each group.

## Build and validation

For this historical template only, build from the **repository root** with:

```bash
docker build -t bionemo-librechat:local -f life-science/bionemo-librechat/Dockerfile .
```

At runtime, inspect the Serverless logs for all of the following:

- `Custom config file loaded`
- `Loaded 31 deployment skill(s)` for the current public bundle
- `MCP[bionemo-models] ... Initialized`
- `Server listening on all interfaces at port 3080`

Use immutable registry tags or image digests for every deployment. Supply the
Token Factory, BioNeMo MCP, and Tavily credentials through MysteryBox secret
environment mappings; do not put secret values in this repository or ordinary
endpoint environment values.
