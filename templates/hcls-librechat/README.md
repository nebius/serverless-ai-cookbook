# Nebius Scientific AI Agent

A scientific workspace built on pinned LibreChat. Choose a chat LLM from Nebius
Token Factory, OpenAI or Claude; the same scientific gateway, research skills and
Tavily search stay attached when you change models. Evo2, Boltz2, DiffDock and
other scientific models are tools, not chat-provider choices.

Six event-focused cards prepare editable prompts for the
[Stockholm Longevity × AI Hackathon](https://luma.com/5b82vwsa): Nebius
infrastructure preparation, aging/biomarkers, target/drug exploration,
communication/trust/policy, healthspan/clinical translation, and wildcard ideas.
Every signed-in participant sees the same starters. Clicking a card does not
switch the LLM, send a message, or submit compute.

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
  Scientific AI Agent identity. The chat picker uses the official colored Token
  Factory mark, bundled locally, for its group, models and selected-chat icon.
  The footer pairs NVIDIA's green symbol/black wordmark with Nebius, using
  balanced sizing and a light NVIDIA backing that works in dark mode.
- **Workflows:** six goal-oriented prompts; saved tutorial agents remain for legacy
  conversations but are hidden from the primary picker.
- **Structure viewer:** `visualize_structure` reads completed operation results
  with the configured gateway key and sends real PDB/mmCIF/SDF coordinates into
  a sandboxed in-chat 3Dmol viewer. Spin, drag, zoom, fullscreen, reset, structure
  selection and representations work without sending the HTML/coordinates back
  through the LLM. The UI resource is stored with the chat and survives reload.
  Results are limited to 4 MiB and 20 structures; small user-provided inline
  structures are limited to 64 KiB. No arbitrary URL or filesystem access.
- **Infrastructure preparation:** the bundled `nebius-infrastructure-prep`
  skill and card prepare a participant-local MCP setup handoff with
  `SAFE_MODE=true`. No participant cloud account is connected to this hosted
  app. The public setup guide supports their local coding agent and CLI profile.
  `nebius/skills` was private at review time; its contents are not bundled or
  redistributed pending authorization. Its link explicitly warns about access.
- **Limitations:** no compatible attachment-to-gateway upload bridge or GROMACS
  server. The viewer does not download scientific-batch artifact references or
  invent coordinates for sequences/SMILES. Inline inputs and finalized artifacts
  remain usable. Do not promise arbitrary attachment submission or fabricated
  output links. Catalog presence is not runtime readiness.
- **Pinned patches:** fail-fast client/server changes cover the picker, missing
  and expired key handling, new-chat subagent polling, deferred tool options, and
  bounded title fallback. Revalidate them when upgrading the base image.

## Verify

```bash
curl -fsS 'https://<librechat-host>/health'
python -m pytest templates/hcls-librechat/tests.py templates/hcls-librechat/test_structure_viewer.py -q
docker build --target scientific-client -t scientific-client-check \
  -f templates/hcls-librechat/Dockerfile .
docker run --rm --entrypoint /app/node_modules/.bin/tsc \
  scientific-client-check --noEmit -p /app/client/tsconfig.json
```

Verify login, all six cards, chat-model switching, provider-key setup, scientific
discovery, one small run, literature search, mobile/dark layout and console errors.
OpenAI/Claude inference requires valid credentials: testing setup UI alone is not
an inference acceptance test. Browser CLI checks are in `scripts/browser-smoke.js`
and `scripts/viewer-browser-smoke.js`; the latter requires an existing chat
containing a real viewer result and does not submit compute.
See [the original review](UX-REVIEW-20260909.md) and
[the event/viewer follow-up](EVENT-REVIEW-20260909.md).
