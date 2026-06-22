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
Serverless. It also includes a self-hosted BioNeMo-compatible GPU service that exposes every
life-science model skill the agent advertises.

It has three paths:

1. **Full stack:** run the BioNeMo-compatible model service on a GPU endpoint, then run the agent against it.
2. **Agent-only endpoint:** run the interactive agent as a FastAPI service with `nat serve`.
3. **Serverless Job:** run a container smoke check or one-shot workflow without keeping an endpoint alive.

The included self-hosted service is a GPU-deployable integration harness with deterministic, nonclinical demo
handlers for the agent's BioNeMo-oriented skills. It is intentionally small so users can start quickly and then
replace individual handlers with real NVIDIA BioNeMo Framework or NIM backends when they have model access.

## Contents

- [Safety Scope](#safety-scope)
- [What You Build](#what-you-build)
- [Prerequisites](#prerequisites)
- [1. Validate Locally](#1-validate-locally)
- [2. Test the Full Stack Locally](#2-test-the-full-stack-locally)
- [3. Build and Push the Image](#3-build-and-push-the-image)
- [4. Build and Run the Self-hosted BioNeMo-compatible GPU Service](#4-build-and-run-the-self-hosted-bionemo-compatible-gpu-service)
- [5. Run a Serverless Job Smoke Check](#5-run-a-serverless-job-smoke-check)
- [6. Create the Agent Serverless Endpoint](#6-create-the-agent-serverless-endpoint)
- [7. Call the Agent Endpoint](#7-call-the-agent-endpoint)
- [Configuration](#configuration)
- [Replacing the Demo Service with Real BioNeMo](#replacing-the-demo-service-with-real-bionemo)
- [Project Structure](#project-structure)
- [Tested Configuration](#tested-configuration)
- [Troubleshooting](#troubleshooting)
- [Cleanup](#cleanup)

## Safety Scope

This is a nonclinical, research-only example. Do not send PHI, patient records, confidential customer data,
unpublished customer sequences, or proprietary molecule/protein inputs unless explicit approval exists. Do not
use the agent for diagnosis, treatment recommendations, triage, patient-specific interpretation, or clinical
decision support. Use synthetic examples, public benchmark inputs, public protein sequences, or approved event
datasets.

## What You Build

```
client
  -> Nebius Serverless GPU or CPU Agent Endpoint
       -> NVIDIA NeMo Agent Toolkit ReAct workflow
            -> BioNeMo capability-routing tools
            -> call_bionemo_skill / call_bionemo_service
       -> Nebius Serverless GPU BioNeMo-compatible Service Endpoint
            -> protein embeddings, structure prediction, retrieval,
               molecular dynamics, genomics generation, chat
       -> Nebius TokenFactory or another OpenAI-compatible LLM API
```

The agent container can run on CPU because it orchestrates tools and remote APIs. For this full-stack demo,
both the agent and the BioNeMo-compatible service can also run on GPU Serverless endpoints.

## Prerequisites

- Nebius CLI installed and authenticated.
- Docker, `jq`, and `openssl` installed locally.
- Nebius Container Registry repository.
- Access to Nebius Serverless Endpoints and Jobs.
- `NEBIUS_API_KEY` for TokenFactory, or `NEBIUS_API_KEY_SECRET` pointing to a MysteryBox secret.
- Optional for real model replacement: NVIDIA NGC or API Catalog access for the BioNeMo/NIM model containers
  you want to host.

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

## 2. Test the Full Stack Locally

Before creating any GPU endpoint, you can run the entire stack on your machine with no Nebius
resources: the self-hosted service runs in a container (it starts on CPU; `nvidia-smi` simply
reports unavailable) and the agent is served against it with a real LLM key.

```bash
export NEBIUS_API_KEY="<tokenfactory-api-key>"
scripts/run_local_fullstack.sh
```

The script builds the service image, starts it with a generated bearer token, serves the agent,
sends one research-only `/generate` request, prints the agent's answer and the service access log,
then tears everything down. A successful run shows a `POST /v1/embeddings/protein ... 200` line,
which confirms the agent's ReAct loop called the live service skill end to end.

## 3. Build and Push the Image

Configure Docker for Nebius Container Registry:

```bash
nebius registry configure-helper
```

Set your image path and build:

```bash
export IMAGE="cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0"
scripts/build_image.sh
```

## 4. Build and Run the Self-hosted BioNeMo-compatible GPU Service

Build the BioNeMo-compatible service image:

```bash
export BIONEMO_SERVICE_IMAGE="cr.<region>.nebius.cloud/<registry-path>/bionemo-service:0.1.0"
scripts/build_bionemo_service_image.sh
```

Run a GPU smoke job before creating an always-on endpoint:

```bash
export PARENT_ID="<project-id>"
export PLATFORM="gpu-b200-sxm-a"
export PRESET="1gpu-20vcpu-224gb"
export PREEMPTIBLE="true" # optional, useful for quick validation
export SUBNET_ID="<subnet-id>" # optional

scripts/run_self_hosted_bionemo_job_smoke.sh
```

The smoke job exercises all named service skills and should print `ok: true` in the job logs.

Create a token-protected GPU endpoint:

```bash
export PLATFORM="gpu-b200-sxm-a"
export PRESET="1gpu-20vcpu-224gb"
export SUBNET_ID="<subnet-id>" # optional
export BIONEMO_ENDPOINT_NAME="self-hosted-bionemo-demo"
export AUTH_TOKEN="$(openssl rand -hex 32)"

scripts/run_self_hosted_bionemo_endpoint.sh
```

Keep this token for the agent:

```bash
export BIONEMO_API_KEY="$AUTH_TOKEN"
```

When the service endpoint reaches `RUNNING`, set `BIONEMO_BASE_URL`:

```bash
export BIONEMO_ENDPOINT_ID=$(nebius ai endpoint get-by-name --name "$BIONEMO_ENDPOINT_NAME" \
  --format jsonpath='{.metadata.id}')

export BIONEMO_BASE_URL="http://$(nebius ai endpoint get "$BIONEMO_ENDPOINT_ID" \
  --format json | jq -r '.status.public_endpoints[0]')"
```

Check the service:

```bash
curl -sS "$BIONEMO_BASE_URL/health" \
  -H "Authorization: Bearer $BIONEMO_API_KEY" | jq

curl -sS "$BIONEMO_BASE_URL/v1/embeddings/protein" \
  -H "Authorization: Bearer $BIONEMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sequence":"MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP"}' | jq
```

The service exposes these named skills for the agent:

| Skill | Path | Demo model family |
|---|---|---|
| `capabilities` | `/v1/capabilities` | Catalog metadata |
| `chat` | `/v1/chat/completions` | BioMedLM-style educational text |
| `protein_embedding` | `/v1/embeddings/protein` | ESM-2-style protein embeddings |
| `structure_prediction` | `/v1/structure/boltz2` | Boltz2-style structure prediction |
| `literature_retrieval` | `/v1/retrieval/literature` | NV-EmbedQA-style retrieval |
| `molecular_dynamics` | `/v1/md/openmm` | OpenMM-style MD metadata |
| `genomics_generation` | `/v1/genomics/carbon` | Carbon-style DNA/RNA generation |

## 5. Run a Serverless Job Smoke Check

Use this path to verify that the agent image pulls and starts on Nebius Serverless without keeping an endpoint
running. For the full-stack GPU demo, use the same B200 platform as the self-hosted service:

```bash
export PARENT_ID="<project-id>"
export PLATFORM="gpu-b200-sxm-a"
export PRESET="1gpu-20vcpu-224gb"
export PREEMPTIBLE="true" # optional, useful for quick validation
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

## 6. Create the Agent Serverless Endpoint

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
export PLATFORM="gpu-b200-sxm-a" # or cpu-d3 for agent-only orchestration
export PRESET="1gpu-20vcpu-224gb" # or 4vcpu-16gb with cpu-d3
export SUBNET_ID="<subnet-id>" # optional
export ENDPOINT_NAME="bionemo-agent"
export AUTH_TOKEN="$(openssl rand -hex 16)"
export BIONEMO_BASE_URL="<self-hosted-service-url>" # optional, from step 4
export BIONEMO_API_KEY="<self-hosted-service-token>" # optional, from step 4

scripts/run_serverless_endpoint.sh
```

Keep `AUTH_TOKEN` secret and leave it in your shell for the test request.

For shared environments, store the endpoint token in MysteryBox with payload key `AUTH_TOKEN` and export:

```bash
export AUTH_TOKEN_SECRET="<secret-id>@<version-id>"
unset AUTH_TOKEN
```

If you use MysteryBox for the self-hosted service token, create a payload key named `BIONEMO_API_KEY` and set:

```bash
export BIONEMO_API_KEY_SECRET="<secret-id>@<version-id>"
unset BIONEMO_API_KEY
```

## 7. Call the Agent Endpoint

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
    "input_message": "Use the BioNeMo protein_embedding skill on public sequence MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP and summarize the nonclinical result."
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
| `BIONEMO_SERVICE_IMAGE` | Service only | Container image for the self-hosted BioNeMo-compatible service. |
| `BIONEMO_ENDPOINT_NAME` | Service only | Service endpoint name, defaults to `self-hosted-bionemo-demo`. |
| `TIMEOUT` | Job only | Job timeout, defaults to `20m` for smoke checks. |
| `PREEMPTIBLE` | Job only | Set to `true` to request preemptible GPU capacity for smoke checks. |
| `NEBIUS_API_KEY` | Endpoint only | TokenFactory or OpenAI-compatible LLM API key for quick demos. |
| `NEBIUS_API_KEY_SECRET` | Endpoint only | MysteryBox secret selector for the LLM API key. |
| `AUTH_TOKEN` | Endpoint only | Bearer token for quick endpoint authentication. |
| `AUTH_TOKEN_SECRET` | Endpoint only | MysteryBox secret selector with payload key `AUTH_TOKEN`. |
| `AGENT_LLM_BASE_URL` | No | Defaults to `https://api.tokenfactory.us-central1.nebius.com/v1`. |
| `AGENT_MODEL_NAME` | No | Defaults to `zai-org/GLM-5`. |
| `BIONEMO_BASE_URL` | No | Optional BioNeMo-compatible service URL. |
| `BIONEMO_API_KEY` | No | Optional bearer token for `BIONEMO_BASE_URL`. |
| `BIONEMO_API_KEY_SECRET` | No | MysteryBox secret selector for the BioNeMo bearer token. |

## Replacing the Demo Service with Real BioNeMo

You do not need a BioNeMo service URL or key for the default routing assistant. Without `BIONEMO_BASE_URL`,
`call_bionemo_skill` and `call_bionemo_service` return dry-run payloads and the agent still routes requests to
BioNeMo-oriented capabilities.

Set `BIONEMO_BASE_URL` when you have a BioNeMo-compatible HTTP service to call. Common sources are:

- A self-hosted NVIDIA BioNeMo Framework or NVIDIA NIM service running in your own environment. In this case,
  `BIONEMO_BASE_URL` is the URL of that service.
- NVIDIA-hosted NIM APIs from the NVIDIA API Catalog. In this case, use the API endpoint and API key for the
  specific model or service you selected.

To replace this demo service with real model backends, keep the same endpoint paths or update `SERVICE_PATHS`
in `bionemo_agent/catalog.py`. Real BioNeMo Framework or NIM containers usually require NVIDIA NGC or API
Catalog access and the license terms for the selected model.

## Project Structure

```text
life-science/bionemo-agent/
├── bionemo_agent/          # NeMo Agent Toolkit component and smoke check
├── configs/config.yml      # ReAct workflow served by nat
├── self-hosted-bionemo/    # GPU service image for BioNeMo-compatible skills
├── scripts/                # local build, job, and endpoint helpers
├── tests/                  # unit tests for routing and dry-run behavior
├── Dockerfile
└── pyproject.toml
```

## Tested Configuration

This recipe was validated on Nebius Serverless with the following known-good configuration:

| Item | Value |
|---|---|
| Region | `me-west1` |
| GPU platform / preset | `gpu-b200-sxm-a` / `1gpu-20vcpu-224gb` (preemptible) |
| Agent platform / preset | `cpu-d3` / `4vcpu-16gb` |
| Agent LLM | `zai-org/GLM-5` via Nebius TokenFactory |
| Python | 3.11 |

What was verified:

- `uv run pytest` (unit tests), `uv run ruff check .`, and `nat validate` all pass.
- The self-hosted service GPU smoke job ran on a real **NVIDIA B200** and exercised all six skills,
  printing a clean `ok: true` JSON document to the job logs.
- The agent Serverless Job smoke check routed `protein sequence embedding` to
  `facebook-esm-2-650m-protein-embedding`.
- The full stack (service container + served agent + GLM-5) handled a `/generate` request whose
  ReAct loop called the live, token-protected `protein_embedding` skill and returned a nonclinical
  summary. Reproduce this locally with `scripts/run_local_fullstack.sh`.

GPU availability, preset names, and model identifiers vary by project and region; adjust
`PLATFORM`, `PRESET`, and `AGENT_MODEL_NAME` to match your tenant.

### GPU compatibility (verified)

The self-hosted service container is a CUDA-runtime FastAPI app: it reads the GPU through
`nvidia-smi` and serves all six skill endpoints, so it has no GPU-architecture-specific code
path. To confirm this empirically, the service source plus the shipped `service_smoke` check were
run as real GPU pods on every NVIDIA GPU type in the Nebius fleet. Each run confirmed the GPU was
visible to the container and all six skill endpoints returned `ok: true`.

| GPU | Reported by `nvidia-smi` | GPU memory | Driver | Result |
|---|---|---|---|---|
| H100   | `NVIDIA H100 80GB HBM3`                          | 81,559 MiB  | 580.126.09 | all 6 skills `ok` |
| H200   | `NVIDIA H200`                                    | 143,771 MiB | 580.126.09 | all 6 skills `ok` |
| L40S   | `NVIDIA L40S`                                    | 46,068 MiB  | 580.126.09 | all 6 skills `ok` |
| B200   | `NVIDIA B200`                                    | 183,359 MiB | 580.126.09 | all 6 skills `ok` |
| B300   | `NVIDIA B300 SXM6 AC`                            | 275,040 MiB | 580.126.09 | all 6 skills `ok` |
| RTX6000| `NVIDIA RTX PRO 6000 Blackwell Server Edition`  | 97,887 MiB  | 580.126.09 | all 6 skills `ok` |

The demo service runs on any of these GPUs (and on CPU). When you swap in **real** BioNeMo assets
(see [Replacing the Demo Service with Real BioNeMo](#replacing-the-demo-service-with-real-bionemo)),
the limiting factor becomes per-model GPU memory and architecture support, not this service layer —
size the GPU to the model (for example ESM-2-3B or Boltz2 need materially more VRAM than the demo).

## Troubleshooting

- **`nat validate` cannot find `bionemo_research_tools`:** run `uv sync` from this recipe directory so the local package entry point is installed.
- **OpenTelemetry/protobuf import error during `nat` startup:** set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`. The Dockerfile and `scripts/run_local.sh` already set this for served runs.
- **Endpoint reaches `RUNNING` but `/generate` fails:** check `NEBIUS_API_KEY` or `NEBIUS_API_KEY_SECRET`; the server can start before the first LLM call.
- **`call_bionemo_service` returns `configured=false`:** set `BIONEMO_BASE_URL` and, if needed, `BIONEMO_API_KEY` or `BIONEMO_API_KEY_SECRET`.
- **Self-hosted service returns 401:** use the same token from the service endpoint as `BIONEMO_API_KEY`, or create a MysteryBox secret with payload key `BIONEMO_API_KEY`.
- **Image pull or cold start is slow:** keep this agent on CPU, use a small preset first, and move heavy model inference to a separate endpoint or job.
- **`multiple subnets found, specify subnet using --subnet-id flag`:** your project has more than one subnet, so set `SUBNET_ID`. List subnets with `nebius vpc subnet list --format json | jq -r '.items[] | [.metadata.id, .metadata.name] | @tsv'` and export the one you want.

## Cleanup

Delete the endpoint when finished:

```bash
nebius ai endpoint delete "$ENDPOINT_ID"
```

Delete the self-hosted service endpoint too:

```bash
nebius ai endpoint delete "$BIONEMO_ENDPOINT_ID"
```

Jobs stop automatically after completion. Delete old job records if you no longer need them:

```bash
nebius ai job delete <job-id>
```
