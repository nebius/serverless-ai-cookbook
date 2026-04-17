# Serverless AI Cookbook

Run GPU workloads on [Nebius Serverless](https://nebius.com/services/serverless) — no infrastructure management, per-second billing, GPU in minutes.

This repo contains runnable code samples for **Serverless AI Jobs** (batch workloads that auto-terminate) and **Endpoints** (persistent HTTP-accessible services). Examples cover model training, fine-tuning, inference serving, AI agents, and scientific simulations.

## Quickstart (30 seconds)

Spin up a GPU job and verify your setup:

```bash
nebius ai job create \
  --name my-first-job \
  --image nvidia/cuda:13.1.1-runtime-ubuntu24.04 \
  --container-command bash \
  --args "-c nvidia-smi" \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --timeout 15m

# Get the job ID and stream logs
export JOB_ID=$(nebius ai job get-by-name --name my-first-job \
  --format jsonpath='{.metadata.id}')
nebius ai logs "$JOB_ID"
```

→ Full walkthrough: [first-job.md](./quickstarts/first-job.md)

## Prerequisites

0. [Create a Nebius account](https://console.nebius.com) and set up a project
1. [Install the Nebius CLI](https://docs.nebius.com/cli/install)
2. [Configure your CLI profile](https://docs.nebius.com/cli/configure)

## Example catalog

| Category | Example | What it does |
|---|---|---|
| **Quickstarts** | [first-job](./quickstarts/first-job.md) | Run `nvidia-smi` in a GPU job — fastest setup check |
| | [first-endpoint](./quickstarts/first-endpoint.md) | Deploy an `nginx` endpoint |
| **Training** | [axolotl-finetuning](./training/axolotl-finetuning/README.md) | Fine-tune an LLM with Axolotl |
| | [train-and-serve](./training/train-and-serve/README.md) | Fine-tune TinyLlama in a Job, then serve it via vLLM Endpoint |
| **Inference** | [vllm-endpoint](./inference/vllm-endpoint/README.md) | Serve Qwen with an OpenAI-compatible vLLM endpoint |
| **Agents** | [openclaw](./agents/openclaw/README.md) | Deploy OpenClaw AI gateway on a CPU endpoint, connected to TokenFactory |
| **Life Science** | [openmm-simulation](./life-science/openmm-simulation/README.md) | GPU-backed molecular dynamics simulation with OpenMM |

## Repository structure

```
serverless-cookbook/
├── quickstarts/          # Lowest-friction first runs
├── training/             # Model training and fine-tuning
├── inference/            # Endpoint serving and batch inference
├── agents/               # AI gateway and agent deployments
├── life-science/         # Domain-specific simulations
├── CONTRIBUTING.md
└── DEVELOPER_GUIDE.md
```

## Resources

- [Nebius Console](https://console.nebius.com)
- [Serverless AI docs](https://docs.nebius.com/serverless/overview)
- [CLI reference](https://docs.nebius.com/cli/reference/ai/)
- [Contributing guide](./CONTRIBUTING.md)
- [Developer guide](./DEVELOPER_GUIDE.md)

---

> **Note:** This repository is maintained by Nebius engineers as a community resource — not official product documentation. APIs and behavior may evolve. For authoritative reference, see [docs.nebius.com/serverless](https://docs.nebius.com/serverless).
