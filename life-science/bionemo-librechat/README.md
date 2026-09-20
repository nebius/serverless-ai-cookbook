# Scientific AI Platform recording workbench

This image provides a general Scientific AI Platform LibreChat for demos and recordings.
Deploy it as a separate Serverless endpoint so recordings use a clean local
conversation database and a dedicated immutable image.

The image bundles Scientific AI skills, grouped visual demos, a Token Factory
provider, the Scientific AI model MCP, Tavily search MCP, owner-authorized
workspace/file/shell tools, and an embedded 3Dmol protein viewer.

## Integrations

The seeded agent uses flat typed model tools, `get_model_schema`, durable
operation polling, and dynamic caller-scoped discovery. Credentials for Token
Factory, Tavily, and the Scientific AI gateway are supplied at deployment time.
The mounted Object Storage bucket is the durable workspace.

## Onboarding

The welcome screen opens model discovery, protein folding, molecular docking,
and visual-workflow demos. The prompt library also includes imaging and
segmentation, generative media and physical AI, and speech transcription.

## Build and validation

Build from the **repository root** with:

```bash
docker build -t bionemo-librechat:local -f life-science/bionemo-librechat/Dockerfile .
```

At runtime, inspect the Serverless logs for all of the following:

- `Custom config file loaded`
- `Loaded 31 deployment skill(s)` for the current public bundle
- `MCP[bionemo-models] ... Initialized`
- `Server listening on all interfaces at port 3080`

Use immutable registry tags or image digests for every deployment. Supply the
Token Factory, Scientific AI MCP, and Tavily credentials through MysteryBox secret
environment mappings; do not put secret values in this repository or ordinary
endpoint environment values.
