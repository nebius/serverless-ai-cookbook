# BioNeMo Agent Workbench 3.3.0 on Nebius Serverless

This recipe packages a ready-to-start life-science agent environment for a
Nebius Serverless CPU endpoint. The image contains:

- a single-step, token-authenticated OpenClaw browser agent;
- Codex CLI `0.147.0` and Claude Code `2.1.228`, installed without auth caches;
- all 31 skills from NVIDIA's pinned BioNeMo Agent Toolkit plugin plus a
  credential-free Tavily research skill;
- the public Cerebrium BioNeMo MCP URL in all three clients;
- ten bounded hosted-NIM adapters, seven composed research workflows, and a bundled interactive 3Dmol structure viewer;
- four image-baked, provider-neutral nbformat notebooks, including a fixed
  five-protein batch dataset and safe same-origin notebook previews; and
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
| `NEBIUS_API_KEY` | Nebius Token Factory | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| `OPENAI_API_KEY` | OpenAI | `gpt-5.6` using the OpenClaw runtime |
| `ANTHROPIC_API_KEY` | Anthropic Claude | `claude-sonnet-5` |
| none | local setup-required responder | no external model |

The Token Factory picker exposes the four models that passed the workbench's
structured-tool, native-JSON, consent, and presentation gates: Nemotron 3 Nano,
Nemotron 3 Super, GLM 5.1, and DeepSeek V4 Pro. Nano remains the default because
its 262K context window is the safest fit for the workbench's tool schemas. The
live service accepts a 262,144-token context for Super even though the model
catalog currently under-reports it as 8K. The image supplies that independently
verified limit and sends `max_tokens` specifically for Super, whose route
rejects `max_completion_tokens`.

The same gate tested all eight previously exposed models. Lightning was removed
for invalid nullable-object types and false consent attempts, GPT-OSS for
missing-consent attempts, Qwen3 for provider-visible reasoning tags, and Ultra
for an unrelated response in clean endpoint acceptance. Those known-failing
IDs are rejected even when supplied through `AGENT_MODEL`; arbitrary operator
models remain available as explicit custom overrides.

The NVIDIA Build profile uses Nemotron 3 Super with template thinking disabled.
Release acceptance produced one structured flat OpenFold2 call, five PDB
artifacts, and a completed post-tool response. Hosted Ultra had less reliable
tail latency in the same workbench, while the smaller NVIDIA-hosted Nano
returned raw tool-call JSON as assistant text in six of six direct probes
(including three with `tool_choice=required`). The NVIDIA provider keeps a
bounded 240-second idle timeout so a slow hosted response does not discard an
already completed BioNeMo NIM result.

OpenClaw reserves at least 20,000 tokens for compaction recovery. This keeps
long Super, Nano, GLM, and DeepSeek tool sessions out of the unrecoverable
low-buffer state identified by OpenClaw's compaction warning.

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

BioNeMo model tools use `BIONEMO_BACKEND=auto`:

- `BIONEMO_MCP_API_KEY` selects the configured MCP server;
- otherwise an NVIDIA key selects the direct hosted-NIM adapters; and
- otherwise tools report that model access is unavailable.

Only the selected BioNeMo backend is exposed to the reasoning model. In MCP
mode, a loopback schema adapter flattens Cerebrium's transport envelope and
hides the duplicate direct tools; in NVIDIA mode, the direct tools remain
visible and the Cerebrium catalog is absent. This keeps one unambiguous tool
contract per operation for the browser workbench. The bundled Codex and Claude
clients remain available for separately authenticated interactive use.

The default MCP endpoint is:

```text
https://api.cerebrium.ai/v4/p-12ff482a/clawbio-models-mcp-public/mcp
```

Set `BIONEMO_MCP_URL` to use a private Kubernetes MCP deployment. HTTPS is
required unless a trusted private HTTP deployment is explicitly enabled with
`BIONEMO_ALLOW_INSECURE_MCP=true`. `CLAWBIO_API_KEY` remains a compatibility
alias for `BIONEMO_MCP_API_KEY`.

Set `TAVILY_API_KEY` to enable the Tavily remote MCP server. The default search
parameters use basic depth, at most five results, and omit raw content and
images. The same `tavily-research` skill is available to OpenClaw, Codex, and
Claude; credentials remain runtime-only and are never part of the skill.

The BioNeMo dashboard opens with four visible guided notebooks. They are real,
clean nbformat 4 files baked under `/workspace/agent/notebooks`, available as a
safe read-only preview, an exact `.ipynb` download, and a one-click launch into
the canonical `agent:bionemo:main` chat. They do not contain credentials,
executed output, or a Python kernel:

1. an optional Tavily-first EGFR/gefitinib research workflow using OpenFold2,
   MolMIM, and OpenFold3;
2. a side-by-side Crambin OpenFold2/OpenFold3 structure comparison;
3. bounded MolMIM ligand optimization followed by OpenFold3 complex modeling;
4. a bulk workflow that reads the bundled, reviewed five-protein FASTA and
   invokes OpenFold2 once per record, sequentially.

Each notebook calls one low-arity, backend-neutral `bionemo_*` wrapper. The
wrapper selects direct NVIDIA or the Cerebrium MCP backend, owns all model
handoffs, prevents duplicate same-turn execution, and stores artifacts and 3D
viewer links. Tavily is optional: `use_tavily=true` runs the bounded research
step when configured, while `use_tavily=false` runs the same scientific model
pipeline without search or a Tavily credential.

## Immutable pins

| Component | Pin |
|---|---|
| NVIDIA BioNeMo Agent Toolkit | `23d483511e0b42221bdafd7259ff43c05220ee86` |
| OpenClaw image | `2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac` |
| Cloudflared | `2026.7.3` with pinned Linux amd64 SHA-256 |
| Codex CLI | `0.147.0` |
| Claude Code | `2.1.228` |
| 3Dmol.js | `2.5.5` |
| Workbench | `3.3.0` |

The canonical NVIDIA plugin is vendored under
`vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit`. Its 31 skill
directories and the image-owned `tavily-research` skill are copied to
`/etc/codex/skills` and `~/.claude/skills`. Runtime client files contain only
endpoint URLs and environment-variable placeholders.

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
export IMAGE="cr.eu-north1.nebius.cloud/<registry-id>/models/bionemo-agent:3.3.0"
./scripts/build_image.sh
```

The script builds and pushes the version tag, resolves its digest, writes an
SPDX SBOM and Grype/Trivy reports under `.task-output/image`, and blocks the
release on fixable Critical findings. Deploy the printed digest or a unique,
digest-derived short alias when Serverless label limits make the full digest
reference too long.

## Deploy one Serverless endpoint

`AUTH_TOKEN_SECRET` is the only required application selector. Every model or
search credential is optional. A selector may be a MysteryBox secret name,
secret ID, version ID, or another selector accepted by the Nebius CLI; its
payload key must match the environment variable name.

```bash
export PROFILE=sandbox
export PARENT_ID=project-e00z6b02t8ddk96c49
export SUBNET_ID=vpcsubnet-e00p701fa30cj5f7wq
export IMAGE="cr.eu-north1.nebius.cloud/<registry-id>/ba:3.3.0-<digest8>"
export AUTH_TOKEN_SECRET="<selector-with-AUTH_TOKEN>"

# Any combination is optional. Set only one of the NVIDIA alternatives.
export NVIDIA_API_KEY_SECRET="<selector-with-NVIDIA_API_KEY>"
# export NGC_API_KEY_SECRET="<selector-with-NGC_API_KEY>"
# export NEBIUS_API_KEY_SECRET="<selector-with-NEBIUS_API_KEY>"
# export OPENAI_API_KEY_SECRET="<selector-with-OPENAI_API_KEY>"
# export ANTHROPIC_API_KEY_SECRET="<selector-with-ANTHROPIC_API_KEY>"
# export BIONEMO_MCP_API_KEY_SECRET="<selector-with-BIONEMO_MCP_API_KEY>"
# export TAVILY_API_KEY_SECRET="<selector-with-TAVILY_API_KEY>"

export ENDPOINT_NAME="bionemo-agent-workbench-3"
./scripts/run_serverless_endpoint.sh
```

The defaults create a regular `cpu-d3` / `4vcpu-16gb` endpoint with a 30 GiB
disk and container port `18789`. Open the HTTPS URL managed by Nebius
Serverless directly; there is no Cloudflare hop or custom reverse proxy.
Do not put secret values in plain `--env` arguments or URLs.

Nebius assigns the browser URL only after the endpoint is created, so it cannot
be put in OpenClaw's static origin allowlist at image startup, and the
Serverless edge presents an internal Host header to the container. In the
default event-oriented mode, the Control UI accepts any browser origin while
the rate-limited OpenClaw `AUTH_TOKEN` remains mandatory. If an exact origin is
known in advance, set it as `BIONEMO_PUBLIC_ORIGIN`; the launcher then uses that
static allowlist instead.

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

For compatibility, `BIONEMO_HTTPS_MODE=cloudflare` explicitly enables the
older Cloudflare quick-tunnel path and Serverless token authentication.

## Environment-variable reference

| Variable | Secret | Required | Purpose |
|---|---:|---:|---|
| `AUTH_TOKEN` | yes | yes | OpenClaw browser authentication; also Serverless authentication in Cloudflare mode |
| `NVIDIA_API_KEY` | yes | no | NVIDIA reasoning and direct hosted NIMs |
| `NGC_API_KEY` | yes | no | Compatibility alternative to `NVIDIA_API_KEY` |
| `NEBIUS_API_KEY` | yes | no | Nebius Token Factory reasoning |
| `OPENAI_API_KEY` | yes | no | OpenAI reasoning |
| `ANTHROPIC_API_KEY` | yes | no | Anthropic Claude reasoning |
| `BIONEMO_MCP_API_KEY` | yes | no | Cerebrium or private BioNeMo MCP bearer |
| `TAVILY_API_KEY` | yes | no | Tavily MCP search |
| `BIONEMO_MCP_URL` | no | no | Override the default live Cerebrium gateway |
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
docker build -t bionemo-agent:3.3.0-test .
docker run --rm bionemo-agent:3.3.0-test doctor
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
broader 31-skill NVIDIA bundle remains available to Codex and Claude for
authenticated interactive use.

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
