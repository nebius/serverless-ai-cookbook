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
Serverless. It also includes a self-hosted BioNeMo-compatible GPU service endpoint for the
agent's default model-backed skills.

It has three paths:

1. **Full stack:** run the BioNeMo-compatible model service on a GPU endpoint, then run the agent against it.
2. **Agent-only endpoint:** run the interactive agent as a FastAPI service with `nat serve`.
3. **Serverless Job:** run a container smoke check or one-shot workflow without keeping an endpoint alive.

The included self-hosted service has two modes:

- `demo`: deterministic, nonclinical handlers that prove the agent-to-service wiring.
- `real`: strict proxy mode. Every required model backend must be configured and pass `/health/models`.

Use `real` mode for any claim that the endpoint is serving actual BioNeMo/NIM/model runtimes.

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
- [Hardware Notes from Vendor Docs](#hardware-notes-from-vendor-docs)
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
       -> Nebius Serverless GPU BioNeMo-compatible Model Service Endpoint
            -> protein embeddings, structure prediction, retrieval,
               molecular dynamics, chat
       -> Nebius TokenFactory or another OpenAI-compatible LLM API
```

The agent container can run on CPU because it orchestrates tools and remote APIs. The model service is the
GPU-backed endpoint. Carbon genomics generation stays catalog-visible but optional because the B200 probe used
most of a single GPU's memory, so it is not part of the default multi-model service.

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
export BIONEMO_MODEL_SERVICE_MODE="demo"

scripts/run_self_hosted_bionemo_job_smoke.sh
```

The smoke job exercises the required B200-default service skills and should print `ok: true` in the job logs.
For a real deployment, set `BIONEMO_MODEL_SERVICE_MODE=real` and provide the required backend URLs before
running the smoke job:

```bash
export BIONEMO_MODEL_SERVICE_MODE="real"
export BIONEMO_MODEL_CHAT_URL="<biomedlm-compatible-url>"
export BIONEMO_MODEL_LITERATURE_RETRIEVAL_URL="<nv-embedqa-compatible-url>"
export BIONEMO_MODEL_STRUCTURE_PREDICTION_URL="<boltz2-compatible-url>"
export BIONEMO_MODEL_PROTEIN_EMBEDDING_URL="<esm2-compatible-url>"
export BIONEMO_MODEL_MOLECULAR_DYNAMICS_URL="<openmm-compatible-url>"
```

Create a token-protected GPU endpoint:

```bash
export PLATFORM="gpu-b200-sxm-a"
export PRESET="1gpu-20vcpu-224gb"
export SUBNET_ID="<subnet-id>" # optional
export BIONEMO_ENDPOINT_NAME="self-hosted-bionemo-demo"
export AUTH_TOKEN="$(openssl rand -hex 32)"
export BIONEMO_MODEL_SERVICE_MODE="demo"

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

scripts/check_bionemo_model_service.sh

curl -sS "$BIONEMO_BASE_URL/v1/embeddings/protein" \
  -H "Authorization: Bearer $BIONEMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sequence":"MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP"}' | jq
```

The service exposes these named skills for the agent:

| Skill | Path | Default service health | Model family |
|---|---|---|---|
| `capabilities` | `/v1/capabilities` | Metadata only | Catalog metadata |
| `chat` | `/v1/chat/completions` | Required | BioMedLM-style educational text |
| `protein_embedding` | `/v1/embeddings/protein` | Required | ESM-2-style protein embeddings |
| `structure_prediction` | `/v1/structure/boltz2` | Required | Boltz2-style structure prediction |
| `literature_retrieval` | `/v1/retrieval/literature` | Required | NV-EmbedQA-style retrieval |
| `molecular_dynamics` | `/v1/md/openmm` | Required | OpenMM-style MD metadata |
| `genomics_generation` | `/v1/genomics/carbon` | Optional, not B200 default | Carbon-style DNA/RNA generation |

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
export BIONEMO_BASE_URL="<self-hosted-service-url>" # from step 4
export BIONEMO_API_KEY="<self-hosted-service-token>" # from step 4

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
| `BIONEMO_MODEL_SERVICE_MODE` | Service only | `demo` for deterministic handlers, `real` to require configured model backends. |
| `BIONEMO_REQUIRE_GPU` | Service only | Defaults to `true`; `/health` is unhealthy without visible NVIDIA GPUs. |
| `BIONEMO_HEALTH_STRICT` | Service only | Defaults to `true`; unhealthy `/health` returns HTTP 503. |
| `BIONEMO_MODEL_<SKILL>_URL` | Real service only | HTTP endpoint for each required real backend, for example `BIONEMO_MODEL_STRUCTURE_PREDICTION_URL`. |
| `BIONEMO_MODEL_<SKILL>_API_KEY` | Real service only | Optional bearer token for a specific real backend. |
| `TIMEOUT` | Job only | Job timeout, defaults to `20m` for smoke checks. |
| `PREEMPTIBLE` | Job only | Set to `true` to request preemptible GPU capacity for smoke checks. |
| `NEBIUS_API_KEY` | Endpoint only | TokenFactory or OpenAI-compatible LLM API key for quick demos. |
| `NEBIUS_API_KEY_SECRET` | Endpoint only | MysteryBox secret selector for the LLM API key. |
| `AUTH_TOKEN` | Endpoint only | Bearer token for quick endpoint authentication. |
| `AUTH_TOKEN_SECRET` | Endpoint only | MysteryBox secret selector with payload key `AUTH_TOKEN`. |
| `AGENT_LLM_BASE_URL` | No | Defaults to `https://api.tokenfactory.us-central1.nebius.com/v1`. |
| `AGENT_MODEL_NAME` | No | Defaults to `zai-org/GLM-5`. |
| `BIONEMO_BASE_URL` | Endpoint only | Required BioNeMo-compatible model service URL for the full-stack agent endpoint. |
| `BIONEMO_API_KEY` | Endpoint only | Required bearer token for `BIONEMO_BASE_URL`, unless using `BIONEMO_API_KEY_SECRET`. |
| `BIONEMO_API_KEY_SECRET` | Endpoint only | MysteryBox secret selector for the BioNeMo bearer token, used instead of `BIONEMO_API_KEY`. |

## Replacing the Demo Service with Real BioNeMo

The deployed full-stack endpoint expects a BioNeMo-compatible model service. Local dry-run routing still works
without `BIONEMO_BASE_URL`, but `scripts/run_serverless_endpoint.sh` requires the service URL and token.

Common real backend sources are:

- A self-hosted NVIDIA BioNeMo Framework or NVIDIA NIM service running in your own environment. In this case,
  `BIONEMO_BASE_URL` is the URL of that service.
- NVIDIA-hosted NIM APIs from the NVIDIA API Catalog. In this case, use the API endpoint and API key for the
  specific model or service you selected.

To make the included model service strict, set `BIONEMO_MODEL_SERVICE_MODE=real` and configure every required
`BIONEMO_MODEL_<SKILL>_URL`. The service checks these paths through `/health/models`; if any required backend
is missing or unhealthy, the smoke job and strict `/health` fail. Real BioNeMo Framework or NIM containers
usually require NVIDIA NGC or API Catalog access and the license terms for the selected model.

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

## Hardware Notes from Vendor Docs

Use these as minimum/reference requirements, not as proof that the bundled service image has loaded every real
model. The real proof for this recipe is `BIONEMO_MODEL_SERVICE_MODE=real` plus a passing `/health/models` check.

| Capability | Source docs | Listed hardware requirement |
|---|---|---|
| Boltz2 NIM | <https://docs.nvidia.com/nim/bionemo/boltz2/latest/support-matrix.html> | 12 CPU cores, 64 GB RAM, 80 GB NVMe, and one or more supported NVIDIA GPUs. NVIDIA lists B200 180 GB among tested GPUs and says the NIM needs at least 48 GB GPU memory. |
| OpenFold3 NIM | <https://docs.nvidia.com/nim/bionemo/openfold3/latest/support-matrix.html> | Single GPU. NVIDIA lists B200 180 GB, H200 141 GB, B300 288 GB, L40S 48 GB, and others; docs also list 80 GB disk, at least 64 GB RAM, and at least 8 CPU cores. |
| NV-EmbedQA E5 v5 | <https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/support-matrix.html> | NeMo Retriever Embedding NIM requires an x86 processor with at least 8 cores. The docs list `nvidia/nv-embedqa-e5-v5` and show compute capability 12.0 FP16 support with about 0.87 GiB approximate GPU memory. |
| BioMedLM 2.7B | <https://huggingface.co/stanford-crfm/BioMedLM> | The model card documents training on 128 A100-40GB GPUs and provides vLLM/SGLang serving examples, but it does not define a B200 serving minimum. Treat Forge probe results as the serving hardware source. |
| ESM-2 650M | <https://docs.nvidia.com/bionemo-framework/2.1/models/esm2/> | BioNeMo Framework docs describe the 650M and 3B converted checkpoints, but the page is model documentation rather than a Serverless serving hardware matrix. Treat Forge probe results as the serving hardware source. |
| OpenMM | <https://docs.openmm.org/latest/userguide/application/01_getting_started.html> | OpenMM installs CUDA automatically with the package when using an NVIDIA GPU, but OpenMM docs do not define a B200-specific serving minimum for this wrapper. Treat Forge probe results as the serving hardware source. |
| Carbon 3B | <https://huggingface.co/HuggingFaceBio/Carbon-3B> plus Forge probe evidence | The model card describes vLLM compatibility and reports single-H100 throughput, but it does not list a B200 serving minimum. A B200 real-runtime probe passed, using about 146 GB VRAM, so it is optional and should be deployed as a dedicated service rather than in the default multi-model bundle. |

## Tested Configuration

This recipe was validated on Nebius Serverless with the following known-good configuration:

| Item | Value |
|---|---|
| Region | `us-central1` |
| GPU platform / preset | `gpu-b200-sxm-a` / `1gpu-20vcpu-224gb` |
| Agent platform / preset | `cpu-d3` / `4vcpu-16gb` |
| Agent LLM | `zai-org/GLM-5` via Nebius TokenFactory |
| Python | 3.11 |

What was verified:

- `uv run pytest` (unit tests), `uv run ruff check .`, and `nat validate` all pass.
- The self-hosted service GPU smoke job ran on a real **NVIDIA B200** in demo mode and exercised the five
  required B200-default service skills, printing a clean `ok: true` JSON document to the job logs.
- The agent Serverless Job smoke check routed `protein sequence embedding` to
  `facebook-esm-2-650m-protein-embedding`.
- The full stack (service container + served agent + GLM-5) handled a `/generate` request whose
  ReAct loop called the live, token-protected `protein_embedding` skill and returned a nonclinical
  summary. Reproduce this locally with `scripts/run_local_fullstack.sh`.
- Real-mode model co-residency is intentionally not claimed until each required backend URL is configured and
  `/health/models` passes against actual model services.

GPU availability, preset names, and model identifiers vary by project and region; adjust
`PLATFORM`, `PRESET`, and `AGENT_MODEL_NAME` to match your tenant.

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
