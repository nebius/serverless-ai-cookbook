# Nebius Scientific AI Agent

Nebius Scientific AI Agent is a self-contained LibreChat Serverless endpoint.
It combines GLM 5.3 Flash, a live scientific-model API and MCP gateway, and the
bounded GROMACS GPU MCP service. The startup page provides six guided templates:
protein folding, molecular docking and design, molecular dynamics, biomedical
imaging, genomics and biological age, and audio-transcription readiness.

The image contains no model or MCP credential. One non-admin gateway key is used
for both the model API and MCP service. Store it in MysteryBox under the payload
key `SCIENTIFIC_MODELS_API_KEY` and map it only as a secret environment variable.

## Deploy

```bash
nebius mysterybox secret create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name nebius-scientific-model-gateway \
  --description 'Scientific-model API and MCP credential' \
  --secret-version-payload '[{"key":"SCIENTIFIC_MODELS_API_KEY","string_value":"<key>"}]'

export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR='nebius-scientific-model-gateway'
export TOKEN_FACTORY_SECRET_SELECTOR='<secret selector with NEBIUS_API_KEY>'
export IMAGE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/nebius-scientific-ai-agent:<release-tag>'

./templates/hcls-librechat/scripts/deploy.sh
```

The script creates a public CPU D3 endpoint on port `3080`; LibreChat keeps its
own email/password sign-in page reachable while all service credentials remain
server-managed. `GROMACS_MCP_URL` defaults to the retained GROMACS endpoint. Set
it to another endpoint's full `/mcp` URL when required, and map its `AUTH_TOKEN`
using `GROMACS_AUTH_TOKEN_SECRET_SELECTOR`.

## What is configured

- **Nebius Token Factory:** GLM 5.3 Flash is the default chat model.
- **Nebius Scientific Models:** the live scientific model catalog is available in
  the provider selector and through the scientific model gateway MCP server.
- **Branding:** application title, logo, welcome copy, and theme use Nebius
  Scientific AI Agent identity.
- **Tutorials:** model-grouped startup cards expose only the relevant MCP tools.
  Audio remains a readiness tutorial until an audio model appears in the catalog.

## Verify

```bash
curl -fsS 'https://<librechat-host>/health'
nebius ai endpoint logs <endpoint-id> --tail 200
```

The logs should report that Nebius Scientific AI Agent tutorials are ready and
that both scientific-model and GROMACS MCP servers initialized. Open **Protein
Folding & Structure** and ask for the live model list before running a workflow.
