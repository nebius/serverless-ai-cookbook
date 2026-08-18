# BioNeMo Agent Workbench 3.3.3 on Nebius Serverless

This recipe packages a ready-to-start life-science agent environment for a
Nebius Serverless CPU endpoint. The image contains:

- a single-step, token-authenticated OpenClaw browser agent;
- Codex CLI `0.147.0` and Claude Code `2.1.228`, installed without auth caches;
- all 31 skills from NVIDIA's pinned BioNeMo Agent Toolkit plugin, 95
  redistributable ClawBio skill contracts, and a credential-free Tavily
  research skill;
- a source-pinned ClawBio CLI plus a local, demo-only three-tool MCP catalog
  shared by OpenClaw, Codex, and Claude;
- a source-pinned RDKit conformer preflight that prevents an unusable MolMIM
  candidate from being handed to OpenFold3;
- the public event BioNeMo MCP URL in all three clients;
- all 17 adapted MCP compute operations covering the 16-service event
  inventory, ten bounded hosted-NIM convenience adapters, seven composed
  research workflows, one sanitized read-only model-inventory tool, and a
  bundled interactive 3Dmol structure viewer;
- four image-baked, provider-neutral nbformat notebooks, including a fixed
  five-protein batch dataset and safe same-origin notebook previews; and
- eleven static, distinctly labelled OpenClaw example sessions whose reviewed
  prompts remain unsent until the user submits them; and
- optional Tavily MCP search.

The container may start without a model credential. In that case the browser
stays healthy and explains which key is missing. Credentials are injected only
at runtime; no key, token, CLI login, model weight, Docker daemon, or Nebius CLI
is stored in the image.

All examples are nonclinical and research-only. Structure, docking, sequence,
affinity, and design outputs are computational hypotheses that require expert
review and experimental validation.

## Runtime choices

`bionemo-agent openclaw` is the image default and starts the browser workbench.
`bionemo-agent codex` or `bionemo-agent claude` starts the corresponding CLI in
an interactive container or VM. `bionemo-agent doctor` reports versions and
credential-presence booleans without printing credential values.

Provider selection defaults to `AGENT_PROVIDER=auto`:

| Available credential | Reasoning provider | Default model |
|---|---|---|
| `NVIDIA_API_KEY` or `NGC_API_KEY` | NVIDIA Build | `nvidia/nemotron-3-super-120b-a12b` |
| `NEBIUS_API_KEY` | Nebius Token Factory | `nvidia/nemotron-3-super-120b-a12b` |
| `OPENAI_API_KEY` | OpenAI | `gpt-5.6` using the OpenClaw runtime |
| `ANTHROPIC_API_KEY` | Anthropic Claude | `claude-sonnet-5` |
| none | local setup-required responder | no external model |

The Token Factory picker exposes Nemotron 3 Super by default and GLM 5.2 as the
qualified alternative. Super uses a conservative 262,144-token OpenClaw
profile, `max_tokens`, string tool-result content, and template thinking
disabled. Those request compatibility settings apply to Super only. GLM 5.2
uses the ordinary Token Factory request contract and a rounded-down 90,000-token
profile after returning the exact sentinel with 90,025 prompt tokens. A stable
read-only MCP catalog alias avoids the repeated namespace that caused earlier
invalid catalog calls.

The current local screen covered all 29 Token Factory catalog entries, including
28 chat candidates, before shortlisted models were exercised through the real
OpenClaw examples. Super passed all six behavioral examples and all four
composed-workflow model calls; GLM 5.2 passed the same behavioral semantics and
four composed calls. The configured atomic call also completed correctly, with
its persisted step projection covered by an image-level regression test.

DeepSeek V4 Pro was removed after it made four forbidden file-read calls after
the required ClawBio calls. DeepSeek V4 Flash twice exhausted its output budget
without a terminal answer, Kimi K3 skipped the two required ClawBio tools, and
MiniMax M3 produced no visible final in all three bounded 90k prompt probes,
including a 2,048-token completion budget. None has a validated workbench
profile. Kimi K2.7 Code completed the tested examples
but was left out of the intentionally small picker because of its materially
worse latency/cost tradeoff; it remains available as an explicit custom
override. Nano, Lightning, Ultra, GPT-OSS, Qwen3, and GLM 5.1 retain their
previously documented workflow failures. Known failing IDs are rejected even
when supplied through `AGENT_MODEL`; other operator models remain available as
explicit custom overrides.

The NVIDIA Build profile uses Nemotron 3 Super with template thinking disabled.
Release acceptance produced one structured flat OpenFold2 call, five PDB
artifacts, and a completed post-tool response. Hosted Ultra had less reliable
tail latency in the same workbench, while the smaller NVIDIA-hosted Nano
returned raw tool-call JSON as assistant text in six of six direct probes
(including three with `tool_choice=required`). The NVIDIA provider keeps a
bounded 240-second idle timeout so a slow hosted response does not discard an
already completed BioNeMo NIM result.

OpenClaw reserves at least 20,000 tokens for compaction recovery. This keeps
long NVIDIA Super, Token Factory Super, and Token Factory GLM 5.2 tool sessions
out of the unrecoverable low-buffer state identified by OpenClaw's compaction
warning.

Override the reasoning choice with `AGENT_PROVIDER=nvidia|nebius|openai|anthropic|claude|setup`, the
model with `AGENT_MODEL`, and the OpenAI-compatible endpoint with
`AGENT_BASE_URL`.

All four external providers remain visible in the model selector when their
credentials are absent. An unavailable selection is routed to the local setup
responder, which explains the exact environment key to add instead of sending
an unauthorized request upstream. The image-owned Control UI opens the
canonical BioNeMo session before the first authenticated connection, so the
complete provider and model catalog is populated without a reload or a visit
to the debug page. Explicit session links and non-chat routes are preserved.
`auto` prefers NVIDIA, then Token Factory, OpenAI, and Claude in that order.

The four backend-neutral BioNeMo workflows use `BIONEMO_BACKEND=auto`:

- `BIONEMO_MCP_API_KEY` selects the configured MCP server;
- otherwise an NVIDIA key selects the direct hosted-NIM adapters; and
- otherwise those workflows report that model access is unavailable.

The sanitized `bionemo_models_list` inventory requires the configured MCP
credential. When MCP is the scientific backend, OpenClaw also materializes the
image-local schema adapter as `bionemo_models`. It exposes all 17 compute
operations covering the 16 inventory services, using product-neutral browser
names such as `bionemo_models__esm2_embed` and
`bionemo_models__alphagenome_predict`. The scVI/scANVI inventory service has two
operations: `scvi_fit_transform` and `scanvi_fit_transform`.

The adapter flattens the upstream request envelopes, requires every declared
research acknowledgement, derives per-turn idempotency keys, and privately
maps clean operation names back to the compatibility API. OpenClaw also gets
the bounded `models_list`, `model_describe`, upload, `job_status`, and
`model_fetch` helpers needed to use those models. Cross-job `jobs_list` and
host-local path staging are deliberately not browser tools. The upstream
credential and `clawbio_*` compatibility names never reach the model-facing
surface.

The existing `bionemo_molmim`, `bionemo_openfold2`, and `bionemo_openfold3`
atomics and the four composed demos remain bounded convenience wrappers over
the configured NVIDIA or MCP backend. Other image-owned `bionemo_*` wrappers
retain their fixed NVIDIA routes, but all corresponding cluster models are
still callable through the adapted `bionemo_models__*` MCP operations.
Codex and Claude use the same loopback adapter under the server key
`bionemo_models`.

The default MCP endpoint is:

```text
https://clawbio-mcp.89-169-122-161.sslip.io/mcp
```

This is the authenticated, externally reachable Kubernetes event gateway. The
image stores this endpoint URL but no bearer value. Inject
`BIONEMO_MCP_API_KEY` at runtime; generated Codex and Claude configuration uses
only an environment-variable placeholder. Set `BIONEMO_MCP_URL` to use another
deployment. HTTPS is required unless a trusted private HTTP deployment is
explicitly enabled with `BIONEMO_ALLOW_INSECURE_MCP=true`. `CLAWBIO_API_KEY`
remains a compatibility alias for `BIONEMO_MCP_API_KEY`.

Set `TAVILY_API_KEY` to enable the Tavily remote MCP server. The default search
parameters use basic depth, at most five results, and omit raw content and
images. The same `tavily-research` skill is available to OpenClaw, Codex, and
Claude; credentials remain runtime-only and are never part of the skill.

The image also packages ClawBio from immutable upstream commit
`794dd1f5aacc1af308694c9b2f7966d0e396916e`. Codex and Claude can discover all
95 redistributed skill contracts directly. OpenClaw gets a small
`clawbio-catalog` router and three local MCP tools to search the catalog, read a
contract, or run an explicitly requested qualified demo. The browser MCP
surface deliberately has no input/output-path parameters, cannot read patient
or customer files, and marks demo readiness separately from upstream CLI
registration. Two upstream proprietary clinical-report skills are excluded;
MIT, Apache-2.0, and GPL-3.0 license texts ship in the image.

The BioNeMo dashboard opens with four visible guided notebooks. They are real,
clean nbformat 4 files baked under `/workspace/agent/notebooks`, available as a
safe read-only preview, an exact `.ipynb` download, and a one-click launch into
its own ready example chat. At startup, OpenClaw's native session lifecycle
creates and pins eleven stable, distinctly labelled starter-only sessions in the
Sessions sidebar. Each contains one visible static user template labelled
`STATIC STARTER — NOT EXECUTED`, while its reviewed prompt is also loaded as an
unsent draft. Opening the page or a session never sends a model request, starts
a tool, or runs scientific compute. They do not contain credentials, fake
assistant output, executed output, or a Python kernel.

Four notebook-backed sessions demonstrate the composed BioNeMo workflows:

1. an optional Tavily-first EGFR/gefitinib research workflow using OpenFold2,
   MolMIM, and OpenFold3;
2. a side-by-side Crambin OpenFold2/OpenFold3 structure comparison;
3. bounded MolMIM ligand optimization followed by OpenFold3 complex modeling;
4. a bulk workflow that reads the bundled, reviewed five-protein FASTA and
   invokes OpenFold2 once per record, sequentially.

Seven additional source-owned session starters demonstrate the surrounding
OpenClaw workbench without pretending they are notebooks or precomputed runs:

5. a no-tool tour of the browser agent, its complete adapted BioNeMo MCP model
   surface, sanitized inventory, notebooks, and artifacts;
6. a no-tool explanation of native OpenClaw skills versus the broader ClawBio
   contracts available to terminal Codex and Claude clients;
7. one read-only ClawBio catalog search followed by one contract description;
8. one readiness-gated, image-qualified local `gwas-lookup` demo with no
   hosted model compute; and
9. one bounded Tavily search that returns cited public sources, or reports the
   safe availability/authentication category and stops without substitution;
   and
10. one sanitized, read-only BioNeMo model inventory call that reports model
    families and readiness without launching scientific compute; and
11. one direct, bounded MolMIM call through the configured backend, with two
    explicit research acknowledgements and no OpenFold3 or job/status fallback.

Each notebook calls one low-arity, backend-neutral `bionemo_*` wrapper. The
wrapper selects direct NVIDIA or the configured MCP backend, owns all model
handoffs, prevents duplicate same-turn execution, and stores artifacts and 3D
viewer links. Tavily is optional: `use_tavily=true` runs the bounded research
step when configured, while `use_tavily=false` runs the same scientific model
pipeline without search or a Tavily credential.

The two ligand workflows evaluate both returned MolMIM candidates with a
deterministic local RDKit conformer preflight. They select the highest-scoring
candidate that can be represented in 3D, report the compatibility result for
both candidates, and make exactly one OpenFold3 handoff. This avoids treating a
candidate-specific conformer failure as a general model-service outage.

## Immutable pins

| Component | Pin |
|---|---|
| NVIDIA BioNeMo Agent Toolkit | `23d483511e0b42221bdafd7259ff43c05220ee86` |
| ClawBio | `794dd1f5aacc1af308694c9b2f7966d0e396916e` (source archive SHA-256 `207978ebea5d940242f8f0e2708ef768ac976bf04e161e68c6556c91f215e5a0`) |
| RDKit | `2025.9.6` (`cp311` manylinux x86-64 wheel SHA-256 `3f4fc084890efb29b51ea4679bb07d28b276b6e73e3381e678a5ba057b4c4222`) |
| OpenClaw image | `2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac` |
| Cloudflared | `2026.7.3` with pinned Linux amd64 SHA-256 |
| Codex CLI | `0.147.0` |
| Claude Code | `2.1.228` |
| 3Dmol.js | `2.5.5` |
| Workbench | `3.3.3` |

The canonical NVIDIA plugin is vendored under
`vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit`. Its 31 skill
directories, the 95 sanitized ClawBio directories, and the image-owned
`tavily-research` skill are copied to `/etc/codex/skills` and
`~/.claude/skills` (127 direct skills per CLI). OpenClaw keeps its bounded
native catalog at 15 skills and reaches the wider ClawBio catalog through the
local hardened MCP server. Runtime client files contain only endpoint URLs,
local executable paths, and environment-variable placeholders.

## Security boundaries

The browser gateway requires `AUTH_TOKEN` with at least 24 characters. The
token is passed to OpenClaw in memory as `OPENCLAW_GATEWAY_TOKEN`; it is not
written into the generated configuration. The public readiness routes reveal
only capability presence. The event-workbench default disables OpenClaw's
additional per-browser device approval, so entering the gateway token is the
only interactive login step. Set `BIONEMO_REQUIRE_DEVICE_PAIRING=true` for a
private deployment that should require both the token and explicit one-time
approval of every browser.

Token-only mode is a deliberate security/usability tradeoff for the bounded
event image. Keep the token secret: anyone who has it can use the Control UI.
Terminal, exec, general filesystem/network tools, subagents, and unbounded
OpenClaw capabilities remain disabled.

The local ClawBio MCP server is the sole bounded exception for ClawBio demos:
it exposes list, describe, and demo-run operations, accepts no arbitrary local
paths or extra command arguments, and runs only the image-qualified demo
allowlist. Its catalog and demos are research/education aids, not clinical
decision support.

OpenClaw uses the minimal tool profile. General runtime, filesystem, arbitrary
network, browser, automation, session, node, agent, messaging, and media tool
groups are denied. Exec, elevated mode, the browser terminal, and gateway tools
are disabled. The ten direct NVIDIA adapters accept bounded schemas and fixed
NVIDIA HTTPS routes, reject redirects and arbitrary paths, cap responses, and
redact credentials.

Generated artifacts live under the agent workspace so OpenClaw can attach
them without broad filesystem access. PDB and CIF results also get an
unguessable, per-run viewer link. The link is a bearer capability for only
that run's structure files, loads the image-bundled 3Dmol.js asset, carries no
gateway or provider key, uses no external CDN, and is not persisted in run
manifests.

## Build and publish

From this directory:

```bash
export IMAGE="cr.eu-north1.nebius.cloud/<registry-id>/models/bionemo-agent:3.3.3"
./scripts/build_image.sh
```

The script builds and pushes the version tag, resolves its digest, writes an
SPDX SBOM and Grype/Trivy reports under `.task-output/image`, and blocks the
release on fixable Critical findings or detected image secrets. Deploy the printed digest or a unique,
digest-derived short alias when Serverless label limits make the full digest
reference too long.

## Deploy a Serverless endpoint

The deployment interface has one positional choice and two required selectors:

- `nvidia` or `tokenfactory` selects the complete, tested role;
- `AUTH_TOKEN_SECRET` points to a MysteryBox secret containing `AUTH_TOKEN`;
- `MODEL_CREDENTIALS_SECRET` points to a secret containing `NVIDIA_API_KEY`
  for NVIDIA, or both `NEBIUS_API_KEY` and `BIONEMO_MCP_API_KEY` for Token
  Factory plus the BioNeMo MCP gateway.

Tavily is optional. Set `TAVILY_SECRET` to a selector containing
`TAVILY_API_KEY` to enable the research step; without it, the same notebook
records that research was skipped and continues the scientific workflow.

```bash
export AUTH_TOKEN_SECRET="<selector-with-AUTH_TOKEN>"
export MODEL_CREDENTIALS_SECRET="<selector-for-this-backend>"
export TAVILY_SECRET="<optional-selector-with-TAVILY_API_KEY>"

./scripts/run_serverless_endpoint.sh nvidia
# or
./scripts/run_serverless_endpoint.sh tokenfactory
```

The script defaults to the public `ba:latest` image and resolves it to an
immutable digest before creating the endpoint. `IMAGE`, `ENDPOINT_NAME`, and
`SUBNET_ID` remain optional escape hatches; normally none is needed. Without a
subnet, the active Nebius CLI profile supplies the project. When `SUBNET_ID` is
set, the script reads the subnet metadata and explicitly creates the endpoint
in that subnet's project, so a stale profile default cannot select a different
project. A MysteryBox selector may be a secret name, secret ID, version ID, or
`SECRET_ID@VERSION_ID`.

The release fixes the non-choice settings in the script: native Nebius HTTPS,
no public VM IP, no device pairing, no Cloudflare process, the production MCP
URL, `cpu-d3` / `4vcpu-16gb`, a 30 GiB disk, and container port `18789`. This
keeps stale shell variables from silently changing the deployment. Open the
HTTPS URL managed by Nebius Serverless directly, and never put secret values in
plain `--env` arguments or URLs.

Nebius assigns the browser URL only after the endpoint is created, so it cannot
be put in OpenClaw's static origin allowlist at image startup, and the
Serverless edge presents an internal Host header to the container. In the
standard event-oriented deployment, the Control UI accepts the managed browser
origin while the rate-limited OpenClaw `AUTH_TOKEN` remains mandatory. A custom
operator may use `BIONEMO_PUBLIC_ORIGIN` with the raw image, but the simplified
Serverless interface deliberately does not expose it.

Expose only the Nebius-managed HTTPS endpoint: omit `--public`
so the container has no directly reachable public IP. Also omit Serverless
endpoint token authentication, because a normal browser navigation cannot add
its Bearer header; the separate OpenClaw `AUTH_TOKEN` remains required. The
script deliberately omits both `--public` and Serverless `--auth token`. Do not
add either back: a public IP makes caller-controlled Host
traffic reach the container directly, while Serverless bearer authentication
cannot be completed by an ordinary browser navigation. The managed HTTPS edge
remains the only network path and OpenClaw's rate-limited token authentication
remains active.

## Advanced image runtime reference

These are image-level controls for custom operators. The standard Serverless
deployment script derives or fixes them and does not require them from users.

| Variable | Secret | Required | Purpose |
|---|---:|---:|---|
| `AUTH_TOKEN` | yes | yes | OpenClaw browser authentication; also Serverless authentication in Cloudflare mode |
| `NVIDIA_API_KEY` | yes | no | NVIDIA reasoning and direct hosted NIMs |
| `NGC_API_KEY` | yes | no | Compatibility alternative to `NVIDIA_API_KEY` |
| `NEBIUS_API_KEY` | yes | no | Nebius Token Factory reasoning |
| `OPENAI_API_KEY` | yes | no | OpenAI reasoning |
| `ANTHROPIC_API_KEY` | yes | no | Anthropic Claude reasoning |
| `BIONEMO_MCP_API_KEY` | yes | no | BioNeMo MCP bearer, injected only at runtime |
| `TAVILY_API_KEY` | yes | no | Tavily MCP search |
| `BIONEMO_MCP_URL` | no | no | Override the default public event gateway |
| `AGENT_PROVIDER` | no | no | `auto`, `nvidia`, `nebius`, `openai`, `anthropic`/`claude`, or `setup` |
| `AGENT_MODEL` | no | no | Override the selected provider's model ID |
| `AGENT_BASE_URL` | no | no | Override the selected provider's API base |
| `BIONEMO_BACKEND` | no | no | `auto`, `mcp`, or `nvidia` |
| `BIONEMO_REQUIRE_DEVICE_PAIRING` | no | no | `false` for token-only event login; `true` adds browser approval |
| `BIONEMO_HTTPS_MODE` | no | no | `nebius` (Serverless script default), `cloudflare`, `external`, or `local`; the generic image stays local unless selected |
| `BIONEMO_PUBLIC_ORIGIN` | no | no | Exact HTTPS origin for `external`, or optional known managed origin for `nebius` |
| `BIONEMO_ENABLE_HTTPS_TUNNEL` | no | no | Legacy Cloudflare boolean used only when `BIONEMO_HTTPS_MODE` is unset |

## Verification

Run source tests and a local keyless smoke test:

```bash
npm test
docker build --platform linux/amd64 -t bionemo-agent:3.3.3-test .
docker run --rm bionemo-agent:3.3.3-test doctor
```

For a running endpoint, obtain its managed URL from `status.public_endpoints`
and check:

```bash
curl -fsS "${BROWSER_URL}/healthz"
curl -fsS "${BROWSER_URL}/readyz"
curl -fsS "${BROWSER_URL}/plugins/bionemo/readiness"
```

The endpoint must remain healthy in keyless setup mode. With a provider key,
readiness additionally reports the selected reasoning provider and BioNeMo
backend, but never the credential value.

## Supported direct hosted NIM tools

The hardened browser plugin exposes Boltz2, DiffDock, Evo2 40B, GenMol,
MolMIM, MSA Search, OpenFold2, OpenFold3, ProteinMPNN, and RFdiffusion. It also
includes four backend-neutral notebook workflows plus the bounded direct
drug-discovery, MSA-to-structure, and protein-binder-design workflows. The
broader 31-skill NVIDIA bundle and 95 redistributable ClawBio contracts remain
available to Codex and Claude for authenticated interactive use.

Direct MolMIM requests send explicit hosted defaults of 10 output molecules
and 20 particles when omitted, and reject a particle population smaller than
the effective output count before contacting NVIDIA. Direct ProteinMPNN calls
must select exactly one backbone source: the bundled `egfr_kinase_public`
sample or an inline PDB.

DiffDock is kept to one bounded hosted request. A generic hosted HTTP 500 is
reported as an upstream NVIDIA failure without inventing a result or
automatically resubmitting compute; a retry must be a fresh, explicit user
action.

## Cleanup

The deployed endpoint is billable while it runs. Stop or delete it explicitly:

```bash
nebius --profile "$PROFILE" ai endpoint stop "$ENDPOINT_ID"
# Or, when no longer needed:
nebius --profile "$PROFILE" ai endpoint delete "$ENDPOINT_ID"
```
