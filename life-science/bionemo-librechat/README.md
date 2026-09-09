# BioNeMo LibreChat workbench

This is the LibreChat replacement for the public OpenClaw BioNeMo workbench.
It is deployed as a separate Serverless endpoint and never updates the existing
`ba:latest` image or `bionemo-3` endpoint.

The image bundles the BioNeMo skills, grouped newcomer tutorials, a Token
Factory provider, the BioNeMo model MCP, Tavily search MCP, owner-authorized
workspace/file/shell tools, and an embedded 3Dmol protein viewer.

## Onboarding

The welcome screen names the four tutorial groups: Protein Folding, Docking and
Design, Sequence and MSA, and Genomics and Cell Biology. The
`bionemo-workbench-tutorials` deployment skill provides model lists, example
workflows, and fair benchmark instructions for each group.

## Build and validation

Build from this directory with:

```bash
docker build -t bionemo-librechat:local -f Dockerfile .
```

At runtime, inspect the Serverless logs for all of the following:

- `Custom config file loaded`
- `Loaded 16 deployment skill(s)`
- `MCP[bionemo-models] ... Initialized`
- `Server listening on all interfaces at port 3080`

Use immutable registry tags or image digests for every deployment. Supply the
Token Factory, BioNeMo MCP, and Tavily credentials through MysteryBox secret
environment mappings; do not put secret values in this repository or ordinary
endpoint environment values.
