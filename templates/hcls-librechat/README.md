# Nebius Scientific AI Agent

A scientific workspace built on pinned LibreChat. Choose a chat LLM from Nebius
Token Factory, OpenAI or Claude; the same scientific gateway, research skills and
Tavily search stay attached when you change models. Evo2, Boltz2, DiffDock and
other scientific models are tools, not chat-provider choices.

Six goal-oriented cards prepare editable prompts: find a model, fold a protein,
explore molecular design, study sequences/aging, investigate biomedical images,
and research literature. Clicking a card does not switch the LLM, send a message,
or submit compute. Planning prompts explain inputs and limitations before a run.

The image contains no model or MCP credential. One non-admin gateway key is used
for both the model API and MCP service. Store it in MysteryBox under the payload
key `SCIENTIFIC_MODELS_API_KEY` and map it only as a secret environment variable.

## Deploy

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR='nebius-scientific-model-gateway'
export TOKEN_FACTORY_SECRET_SELECTOR='<secret selector with NEBIUS_API_KEY>'
export TAVILY_SECRET_SELECTOR='<secret selector with TAVILY_API_KEY>'
export IMAGE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/nebius-scientific-ai-agent:<release-tag>'

./templates/hcls-librechat/scripts/deploy.sh
```

The script creates a public CPU D3 endpoint on port `3080`; LibreChat keeps its
own email/password sign-in page reachable. Provision secrets separately; never
put real keys in commands, Git, image layers or chat prompts. Optional
`OPENAI_SECRET_SELECTOR` and `ANTHROPIC_SECRET_SELECTOR` provide deployment-managed
chat keys. Without them, these providers use LibreChat's per-user key setup.

Never delete an existing endpoint without preserving `/data` and `/app/uploads`:
the self-contained image runs its own MongoDB. Shared gateway credentials do not
establish tenant isolation; multi-user acceptance needs separate customer keys.

## What is configured

- **Chat models:** GLM 5.3 Flash is the default. The Token Factory chat allowlist
  is intersected with authenticated discovery at startup (configured-list fallback).
  Embedding and dedicated endpoints are excluded. OpenAI and Claude require their
  own provider key: select a model, then choose **Provider key**. Visibility does
  not establish entitlement or successful inference.
- **Scientific models:** available only through the gateway tools. Model-specific
  schemas load on demand with `tool_search`; discovery and durable operation tools
  stay ready. Gateway authorization, validation and execution are unchanged.
- **Branding:** application title, logo, welcome copy, and theme use Nebius
  Scientific AI Agent identity.
- **Workflows:** six goal-oriented prompts; saved tutorial agents remain for legacy
  conversations but are hidden from the primary picker.
- **Limitations:** no compatible attachment-to-gateway file bridge, structure
  viewer, or GROMACS server. Inline inputs and caller-owned finalized artifacts
  remain usable. Do not promise arbitrary attachment submission or fabricated
  output links. Catalog presence is not runtime readiness.
- **Pinned patches:** fail-fast client/server changes cover the picker, missing
  and expired key handling, new-chat subagent polling, deferred tool options, and
  bounded title fallback. Revalidate them when upgrading the base image.

## Verify

```bash
curl -fsS 'https://<librechat-host>/health'
python -m pytest templates/hcls-librechat/tests.py -q
docker build --target scientific-client -t scientific-client-check \
  -f templates/hcls-librechat/Dockerfile .
docker run --rm --entrypoint /app/node_modules/.bin/tsc \
  scientific-client-check --noEmit -p /app/client/tsconfig.json
```

Verify login, all six cards, chat-model switching, provider-key setup, scientific
discovery, one small run, literature search, mobile/dark layout and console errors.
OpenAI/Claude inference requires valid credentials: testing setup UI alone is not
an inference acceptance test. See [the review record](UX-REVIEW-20260909.md).
