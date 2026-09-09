# Nebius Scientific AI Agent

A scientific workspace built on pinned LibreChat. Dedicated GLM 5.3 is the
event default; dedicated Nemotron and tested public Nebius Token Factory models
remain selectable. The same scientific gateway, research skills and Tavily
search stay attached when you change models. Evo2, Boltz2, DiffDock and other
scientific models are tools, not chat-provider choices.

Six event-focused cards prepare editable prompts for the
[Stockholm Longevity × AI Hackathon](https://luma.com/5b82vwsa): Nebius
infrastructure preparation, aging/biomarkers, target/drug exploration,
communication/trust/policy, healthspan/clinical translation, and wildcard ideas.
Every signed-in participant sees the same starters. Clicking a card does not
switch the LLM, send a message, or submit compute.
Each card names models/tools and installed skills, and prepares a concrete
research, model-discovery or demo workflow. AltumAge and Clinical PhenoAge are
highlighted as the event models; other tracks introduce folding, docking,
genomics, molecule/protein design, imaging and Tavily research.

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
own email/password sign-in page reachable. Event deployments mount each team's
read-write Object Storage bucket at `/workspace`. Provision secrets separately; never
put real keys in commands, Git, image layers or chat prompts.

Never delete an existing endpoint without preserving `/data` and `/app/uploads`:
the self-contained image runs its own MongoDB. Shared gateway credentials do not
establish tenant isolation; multi-user acceptance needs separate customer keys.

## What is configured

- **Chat models:** Dedicated GLM 5.3 Flash is the default, with dedicated
  Nemotron and the tested public Token Factory allowlist available. The public
  allowlist is intersected with authenticated discovery at startup
  (configured-list fallback). Qwen models are excluded for this event.
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
  skill routes to ten installed official Nebius skills: cloud basics, compute
  inventory/provisioning, capacity/quotas, Serverless setup, jobs, endpoints,
  data/secrets, troubleshooting and recipes. Their reference files and assets
  are included. They prepare configurations and a participant-local MCP setup handoff with
  `SAFE_MODE=true`. No participant cloud account is connected to this hosted
  app. The public setup guide supports their local coding agent and CLI profile.
  The official skill bundle is pinned to
  `292c7e65a46d0c29994d2babfc19da129d16fa62`, with its Apache-2.0 license and file
  hashes retained in the image. The upstream repository requires access; its
  source files are fetched into an ignored build directory, not this public Git
  repository. Participants can use the installed guidance without repo access.
- **Limitations:** no compatible attachment-to-gateway upload bridge or GROMACS
  server. The viewer does not download scientific-batch artifact references or
  invent coordinates for sequences/SMILES. Inline inputs and finalized artifacts
  remain usable. Do not promise arbitrary attachment submission or fabricated
  output links. Catalog presence is not runtime readiness.
- **Pinned patches:** fail-fast client/server changes cover the picker, missing
  and expired key handling, new-chat subagent polling, deferred tool options, and
  bounded title fallback. Revalidate them when upgrading the base image.

## Verify

Prepare the official skills with the builder's existing authorized GitHub access
before building. This fetches only the pinned source; no GitHub credential is
copied into the build context or image.

```bash
bash templates/hcls-librechat/scripts/prepare-nebius-skills.sh
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
