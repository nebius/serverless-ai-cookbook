---
title: BioNeMo Agent on Nebius Serverless
category: life-sciences
type: endpoint
runtime: nebius-ai-endpoints
frameworks: [nvidia-nemo-agent-toolkit, bionemo, python]
keywords: [bionemo, agents, life-science, serverless-endpoints, tokenfactory]
difficulty: intermediate
---

# BioNeMo Agent on Nebius Serverless

This cookbook recipe packages a research-only BioNeMo assistant with the
[NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit) and runs it on Nebius
Serverless.

It has two paths:

1. **Serverless Endpoint:** run the interactive agent as a FastAPI service with `nat serve`.
2. **Serverless Job:** run a container smoke check or one-shot workflow without keeping an endpoint alive.

The example does not host a BioNeMo model inside the agent container. Instead, the agent routes life-science
requests to a curated set of BioNeMo-oriented capabilities and can optionally call a configured
BioNeMo-compatible HTTP service.

## Safety Scope

This is a nonclinical, research-only example. Do not send PHI, patient records, confidential customer data,
unpublished customer sequences, or proprietary molecule/protein inputs unless explicit approval exists. Do not
use the agent for diagnosis, treatment recommendations, triage, patient-specific interpretation, or clinical
decision support. Use synthetic examples, public benchmark inputs, public protein sequences, or approved event
datasets.

## What You Build

```
client
  -> Nebius Serverless CPU Endpoint
       -> NVIDIA NeMo Agent Toolkit ReAct workflow
            -> BioNeMo capability-routing tools
            -> optional BioNeMo-compatible HTTP API
       -> Nebius TokenFactory or another OpenAI-compatible LLM API
```

The agent container runs on CPU because it orchestrates tools and remote APIs. Use a GPU endpoint only if you
modify the image to host model inference locally.

## Prerequisites

- Nebius CLI installed and authenticated.
- Docker, `jq`, and `openssl` installed locally.
- Nebius Container Registry repository.
- Access to Nebius Serverless Endpoints and Jobs.
- `NEBIUS_API_KEY` for TokenFactory, or `NEBIUS_API_KEY_SECRET` pointing to a MysteryBox secret.
- Optional: `BIONEMO_BASE_URL` and `BIONEMO_API_KEY` or `BIONEMO_API_KEY_SECRET` for live BioNeMo service calls.

Run all commands from this recipe directory:

```bash
cd life-science/bionemo-agent
```

## 1. Validate Locally

Install dependencies and run a smoke check that does not need an LLM API key:

```bash
uv sync
uv run python -m bionemo_agent.smoke --query "protein sequence embedding"
```

Validate the NVIDIA NeMo Agent Toolkit workflow config:

```bash
NEBIUS_API_KEY=dummy PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  uv run nat validate --config_file configs/config.yml
```

If you have a TokenFactory key, run the interactive agent locally:

```bash
export NEBIUS_API_KEY="<tokenfactory-api-key>"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  uv run nat serve --config_file configs/config.yml --host 0.0.0.0 --port 8000
```

Then call it:

```bash
curl -sS http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "input_message": "Route a public protein sequence embedding demo to the right BioNeMo capability and Nebius Serverless shape."
  }' | jq
```

## 2. Build and Push the Image

Configure Docker for Nebius Container Registry:

```bash
nebius registry configure-helper
```

Set your image path and build:

```bash
export IMAGE="cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0"
scripts/build_image.sh
```

## 3. Run a Serverless Job Smoke Check

Use this path first to verify that the image pulls and starts on Nebius Serverless without keeping an endpoint
running:

```bash
export PARENT_ID="<project-id>"
export PLATFORM="cpu-d3"
export PRESET="4vcpu-16gb"
export SUBNET_ID="<subnet-id>" # optional if your project has a default

scripts/run_serverless_job_smoke.sh
```

Follow logs:

```bash
nebius ai logs <job-id> --follow --timestamps
```

Expected output:

```json
{
  "ok": true,
  "query": "protein sequence embedding",
  "recommended_slug": "facebook-esm-2-650m-protein-embedding",
  "dry_run_path": "/v1/example"
}
```

## 4. Create the Serverless Endpoint

For a quick demo, export a TokenFactory key:

```bash
export NEBIUS_API_KEY="<tokenfactory-api-key>"
```

For a shared or production-like setup, use a MysteryBox secret selector instead:

```bash
export NEBIUS_API_KEY_SECRET="<secret-id>@<version-id>"
unset NEBIUS_API_KEY
```

Create the endpoint:

```bash
export PARENT_ID="<project-id>"
export IMAGE="cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0"
export PLATFORM="cpu-d3"
export PRESET="4vcpu-16gb"
export SUBNET_ID="<subnet-id>" # optional
export ENDPOINT_NAME="bionemo-agent"
export AUTH_TOKEN="$(openssl rand -hex 16)"

scripts/run_serverless_endpoint.sh
```

Keep `AUTH_TOKEN` secret and leave it in your shell for the test request.

For shared environments, store the endpoint token in MysteryBox with payload key `AUTH_TOKEN` and export:

```bash
export AUTH_TOKEN_SECRET="<secret-id>@<version-id>"
unset AUTH_TOKEN
```

## 5. Call the Endpoint

Wait until the endpoint reaches `RUNNING`:

```bash
export ENDPOINT_ID=$(nebius ai endpoint get-by-name --name "$ENDPOINT_NAME" \
  --format jsonpath='{.metadata.id}')

nebius ai endpoint get "$ENDPOINT_ID" --format json | jq '.status.state'
```

Get the endpoint IP:

```bash
export ENDPOINT_IP=$(nebius ai endpoint get "$ENDPOINT_ID" \
  --format json | jq -r '.status.public_endpoints[0]')
export ENDPOINT_URL="http://${ENDPOINT_IP}"
```

Send a request:

```bash
curl -sS "$ENDPOINT_URL/generate" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_message": "Recommend a safe public benchmark flow for biomedical literature retrieval."
  }' | jq
```

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `IMAGE` | Yes | Container image pushed to a registry Nebius can pull. |
| `PARENT_ID` | Recommended | Nebius project ID. |
| `SUBNET_ID` | Optional | Subnet ID for projects without a usable default subnet. |
| `PLATFORM` | No | Defaults to `cpu-d3`. |
| `PRESET` | No | Defaults to `4vcpu-16gb`. |
| `NEBIUS_API_KEY` | Endpoint only | TokenFactory or OpenAI-compatible LLM API key for quick demos. |
| `NEBIUS_API_KEY_SECRET` | Endpoint only | MysteryBox secret selector for the LLM API key. |
| `AUTH_TOKEN` | Endpoint only | Bearer token for quick endpoint authentication. |
| `AUTH_TOKEN_SECRET` | Endpoint only | MysteryBox secret selector with payload key `AUTH_TOKEN`. |
| `AGENT_LLM_BASE_URL` | No | Defaults to `https://api.tokenfactory.us-central1.nebius.com/v1`. |
| `AGENT_MODEL_NAME` | No | Defaults to `zai-org/GLM-5`. |
| `BIONEMO_BASE_URL` | No | Optional BioNeMo-compatible service URL. |
| `BIONEMO_API_KEY` | No | Optional bearer token for `BIONEMO_BASE_URL`. |
| `BIONEMO_API_KEY_SECRET` | No | MysteryBox secret selector for the BioNeMo bearer token. |

## Project Structure

```text
life-science/bionemo-agent/
├── bionemo_agent/          # NeMo Agent Toolkit component and smoke check
├── configs/config.yml      # ReAct workflow served by nat
├── scripts/                # local build, job, and endpoint helpers
├── tests/                  # unit tests for routing and dry-run behavior
├── Dockerfile
└── pyproject.toml
```

## Troubleshooting

- **`nat validate` cannot find `bionemo_research_tools`:** run `uv sync` from this recipe directory so the local package entry point is installed.
- **OpenTelemetry/protobuf import error during `nat` startup:** set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`. The Dockerfile and `scripts/run_local.sh` already set this for served runs.
- **Endpoint reaches `RUNNING` but `/generate` fails:** check `NEBIUS_API_KEY` or `NEBIUS_API_KEY_SECRET`; the server can start before the first LLM call.
- **`call_bionemo_service` returns `configured=false`:** set `BIONEMO_BASE_URL` and, if needed, `BIONEMO_API_KEY` or `BIONEMO_API_KEY_SECRET`.
- **Image pull or cold start is slow:** keep this agent on CPU, use a small preset first, and move heavy model inference to a separate endpoint or job.

## Cleanup

Delete the endpoint when finished:

```bash
nebius ai endpoint delete "$ENDPOINT_ID"
```

Jobs stop automatically after completion. Delete old job records if you no longer need them:

```bash
nebius ai job delete <job-id>
```
