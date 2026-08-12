# BioNeMo Agent Workbench 3.0 on Nebius Serverless

This recipe packages a ready-to-start life-science agent environment for a
Nebius Serverless CPU endpoint. The image contains:

- an authenticated OpenClaw browser agent;
- Codex CLI `0.147.0` and Claude Code `2.1.228`, installed without auth caches;
- all 31 skills from NVIDIA's pinned BioNeMo Agent Toolkit plugin;
- the public Cerebrium BioNeMo MCP URL in all three clients;
- ten bounded hosted-NIM adapters and three composed research workflows; and
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
| `NVIDIA_API_KEY` or `NGC_API_KEY` | NVIDIA Build | `nvidia/nemotron-3-nano-30b-a3b` |
| `NEBIUS_API_KEY` | Nebius Token Factory | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| none | local setup-required responder | no external model |

Override the reasoning choice with `AGENT_PROVIDER=nvidia|nebius|setup`, the
model with `AGENT_MODEL`, and the OpenAI-compatible endpoint with
`AGENT_BASE_URL`.

BioNeMo model tools use `BIONEMO_BACKEND=auto`:

- `BIONEMO_MCP_API_KEY` selects the configured MCP server;
- otherwise an NVIDIA key selects the direct hosted-NIM adapters; and
- otherwise tools report that model access is unavailable.

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
images.

## Immutable pins

| Component | Pin |
|---|---|
| NVIDIA BioNeMo Agent Toolkit | `23d483511e0b42221bdafd7259ff43c05220ee86` |
| OpenClaw image | `2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac` |
| Cloudflared | `2026.7.3` with pinned Linux amd64 SHA-256 |
| Codex CLI | `0.147.0` |
| Claude Code | `2.1.228` |
| Workbench | `3.0.0` |

The canonical NVIDIA plugin is vendored under
`vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit`. Its 31 skill
directories are copied to `/etc/codex/skills` and `~/.claude/skills`. Runtime
client files contain only endpoint URLs and environment-variable placeholders.

## Security boundaries

The browser gateway requires `AUTH_TOKEN` with at least 24 characters. The
token is passed to OpenClaw in memory as `OPENCLAW_GATEWAY_TOKEN`; it is not
written into the generated configuration. The public readiness routes reveal
only capability presence.

OpenClaw uses the minimal tool profile. General runtime, filesystem, arbitrary
network, browser, automation, session, node, agent, messaging, and media tool
groups are denied. Exec, elevated mode, the browser terminal, and gateway tools
are disabled. The ten direct NVIDIA adapters accept bounded schemas and fixed
NVIDIA HTTPS routes, reject redirects and arbitrary paths, cap responses, and
redact credentials.

## Build and publish

From this directory:

```bash
export IMAGE="cr.eu-north1.nebius.cloud/<registry-id>/models/bionemo-agent:3.0.0"
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
export IMAGE="cr.eu-north1.nebius.cloud/<registry-id>/ba:3.0.0-<digest8>"
export AUTH_TOKEN_SECRET="<selector-with-AUTH_TOKEN>"

# Any combination is optional. Set only one of the NVIDIA alternatives.
export NVIDIA_API_KEY_SECRET="<selector-with-NVIDIA_API_KEY>"
# export NGC_API_KEY_SECRET="<selector-with-NGC_API_KEY>"
# export NEBIUS_API_KEY_SECRET="<selector-with-NEBIUS_API_KEY>"
# export BIONEMO_MCP_API_KEY_SECRET="<selector-with-BIONEMO_MCP_API_KEY>"
# export TAVILY_API_KEY_SECRET="<selector-with-TAVILY_API_KEY>"

export ENDPOINT_NAME="bionemo-agent-workbench-3"
./scripts/run_serverless_endpoint.sh
```

The defaults create a regular public `cpu-d3` / `4vcpu-16gb` endpoint with a
30 GiB disk and container port `18789`. Serverless token authentication and the
OpenClaw gateway both use the same `AUTH_TOKEN` MysteryBox payload. Do not put
secret values in plain `--env` arguments or URLs.

The launcher starts a supervised Cloudflare quick tunnel by default and prints
an `https://*.trycloudflare.com` browser URL to endpoint logs. Quick tunnels are
best-effort and route demo traffic through Cloudflare. For a managed ingress,
set `BIONEMO_PUBLIC_ORIGIN=https://agent.example` and
`BIONEMO_ENABLE_HTTPS_TUNNEL=false`.

## Environment-variable reference

| Variable | Secret | Required | Purpose |
|---|---:|---:|---|
| `AUTH_TOKEN` | yes | yes | Serverless and OpenClaw browser authentication |
| `NVIDIA_API_KEY` | yes | no | NVIDIA reasoning and direct hosted NIMs |
| `NGC_API_KEY` | yes | no | Compatibility alternative to `NVIDIA_API_KEY` |
| `NEBIUS_API_KEY` | yes | no | Nebius Token Factory reasoning |
| `BIONEMO_MCP_API_KEY` | yes | no | Cerebrium or private BioNeMo MCP bearer |
| `TAVILY_API_KEY` | yes | no | Tavily MCP search |
| `BIONEMO_MCP_URL` | no | no | Override the default live Cerebrium gateway |
| `AGENT_PROVIDER` | no | no | `auto`, `nvidia`, `nebius`, or `setup` |
| `AGENT_MODEL` | no | no | Override the selected provider's model ID |
| `AGENT_BASE_URL` | no | no | Override the selected provider's API base |
| `BIONEMO_BACKEND` | no | no | `auto`, `mcp`, or `nvidia` |

## Verification

Run source tests and a local keyless smoke test:

```bash
npm test
docker build -t bionemo-agent:3.0.0-test .
docker run --rm bionemo-agent:3.0.0-test doctor
```

For a running endpoint, get the tunnel URL from logs and check:

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
includes bounded drug-discovery, MSA-to-structure, and protein-binder-design
workflows. The broader 31-skill NVIDIA bundle remains available to Codex and
Claude for authenticated interactive use.

## Cleanup

The deployed endpoint is billable while it runs. Stop or delete it explicitly:

```bash
nebius --profile "$PROFILE" ai endpoint stop "$ENDPOINT_ID"
# Or, when no longer needed:
nebius --profile "$PROFILE" ai endpoint delete "$ENDPOINT_ID"
```
