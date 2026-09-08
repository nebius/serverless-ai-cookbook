# Kopra Scientific AI

Kopra Scientific AI is a self-contained LibreChat Serverless endpoint. It connects
the Kopra OpenAI-compatible model API and Streamable HTTP MCP gateway, plus the
existing bounded GROMACS GPU MCP service. The startup page contains six guided
templates: protein folding, molecular docking and design, molecular dynamics,
biomedical imaging, genomics and biological age, and a real-time transcription
readiness tutorial.

The image contains no model or MCP credential. `KOPRA_API_KEY` is one non-admin
key used for both `https://89.169.99.188/v1` and `https://89.169.99.188/mcp`.
Store it in MysteryBox under the payload key `KOPRA_API_KEY` and map it to the
endpoint as a secret environment variable. Do not put it in image tags, source,
or ordinary environment variables.

## Deploy

Create the secret once:

```bash
nebius mysterybox secret create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name kopra-scientific-inference-mcp \
  --description 'Kopra non-admin inference and MCP credential' \
  --secret-version-payload '[{"key":"KOPRA_API_KEY","string_value":"<key>"}]'
```

Then create a new endpoint from an immutable image tag. This does not modify the
public BioNeMo or GROMACS LibreChat releases.

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export KOPRA_API_KEY_SECRET_SELECTOR='kopra-scientific-inference-mcp'
export TOKEN_FACTORY_SECRET_SELECTOR='<secret selector with NEBIUS_API_KEY>'
export IMAGE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/kopra-scientific-ai:<release-tag>'

./templates/hcls-librechat/scripts/deploy.sh
```

The script creates a public CPU D3 endpoint on port `3080`, with Serverless
authentication set to `none` so the LibreChat sign-in page remains reachable.
LibreChat registration and passwords are managed by its embedded database. The
Kopra key stays server-managed, so users can use the full authorized model catalog
and MCP tools without receiving that key.

`GROMACS_MCP_URL` defaults to the retained GROMACS endpoint. To use another
deployment, set it to its full `/mcp` URL and optionally map the endpoint's
`AUTH_TOKEN` secret using `GROMACS_AUTH_TOKEN_SECRET_SELECTOR`.

## What is configured

- **Providers:** `Nebius Token Factory` supplies the default `GLM 5.3 Flash` chat
  model. `Kopra Scientific Models` fetches the live `/v1/models` catalog.
- **MCP:** `Kopra Scientific Model Gateway` uses the same non-admin bearer key and
  exposes the live catalog, scientific operations, artifacts, folding, docking,
  imaging, genomics, and generation tools.
- **Design:** the application title, logo, landing welcome, and theme are branded
  as Kopra Scientific AI.
- **Templates:** each startup card has model-grouped prompts and an agent with only
  the relevant MCP tools. The audio card remains a tutorial until an audio model is
  present in the live catalog.

## Verify

```bash
curl -fsS 'https://<librechat-host>/health'
nebius ai endpoint logs <endpoint-id> --tail 200
```

The logs should report `Kopra Scientific AI tutorials are ready` and initialized
Kopra and GROMACS MCP servers. Open the landing page, select **Protein Folding &
Structure**, and ask it to list the live models. It should call `list_models` or
`list_scientific_models` before proposing any scientific run.
