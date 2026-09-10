# Serverless AI Cookbook

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

Run GPU workloads on [Nebius Serverless](https://nebius.com/services/serverless) — no infrastructure management, per-second billing, GPU in minutes.

This repo contains runnable code samples for **Serverless AI Jobs** (batch workloads that auto-terminate) and **Endpoints** (persistent HTTP-accessible services), plus **1-click templates** that open the Nebius Console with fields pre-filled. Examples cover model training, fine-tuning, inference serving, AI agents, and scientific simulations.

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

Pick the section that matches your goal — each links to runnable examples:

- 🚀 [**Quickstarts**](#-quickstarts) — lowest-friction first runs.
- 📦 [**Templates**](#-templates) — 1-click Console deploy (pre-filled create forms).
- 🏋️ [**Training**](#️-training) — model training and fine-tuning workloads.
- ⚡ [**Inference**](#-inference) — endpoint serving and batch inference workloads.
- 🤖 [**Agents**](#-agents) — AI gateway and agent deployments.
- 🧬 [**Life Science**](#-life-science) — domain-specific simulation and analysis workloads.
- 🦾 [**Robotics**](#-robotics) — simulation, dataset generation, and robotics workflows.

### 🚀 Quickstarts

Lowest-friction first runs.

- [`first-job`](./quickstarts/first-job.md) — run `nvidia-smi` in a Serverless AI job
- [`first-endpoint`](./quickstarts/first-endpoint.md) — deploy a quick `nginx` endpoint

### 📦 Templates

1-click deploy into the Nebius Console — fields pre-filled; adjust before create if needed.

| Template                                                                    | Deploy                                                                                                                                                                                                                                                                                                                                                                        | Modality       |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| [Qwen3-0.6B](./templates/endpoint-vllm-qwen3-0-6b/README.md)                | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-0.6B%20--host%200.0.0.0%20--port%208000&targetPort=8000&platform=gpu-l40s-a&preset=1gpu-8vcpu-32gb&diskSize=500GiB&preemptible=true) | LLM            |
| [Qwen3-VL-Embedding-8B](./templates/endpoint-qwen3-vl-embedding/README.md) | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-VL-Embedding-8B%20--runner%20pooling%20--trust-remote-code%20--host%200.0.0.0%20--port%208000&targetPort=8000&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&diskSize=500GiB&preemptible=true) | Embeddings |
| [Sana](./templates/endpoint-sana/README.md)                                 | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fsana-serve%3Ad315ae1&targetPort=8000&platform=gpu-l40s-a&preset=1gpu-8vcpu-32gb&diskSize=500GiB&preemptible=true)                                                                                   | Text-to-image  |
| [Qwen-Image-Edit-2511](./templates/endpoint-qwen-image-edit-2511/README.md) | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&command=vllm%20serve%20Qwen%2FQwen-Image-Edit-2511%20--omni%20--host%200.0.0.0%20--port%208000&targetPort=8000&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&diskSize=500GiB&preemptible=true)                           | Image-to-image |
| [Wan2.1-T2V-1.3B](./templates/endpoint-wan21-t2v-1-3b/README.md)            | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&command=vllm%20serve%20Wan-AI%2FWan2.1-T2V-1.3B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&targetPort=8000&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&diskSize=500GiB&preemptible=true)                    | Text-to-video  |
| [Wan2.2-I2V-A14B](./templates/endpoint-wan22-i2v-a14b/README.md)            | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&command=vllm%20serve%20Wan-AI%2FWan2.2-I2V-A14B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&targetPort=8000&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&diskSize=500GiB&preemptible=true)                    | Image-to-video |
| [Kokoro-82M](./templates/endpoint-kokoro-82m/README.md)                     | [![Create Endpoint](./templates/assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fkokoro-serve%3Ad315ae1&targetPort=8000&platform=gpu-l40s-a&preset=1gpu-8vcpu-32gb&diskSize=500GiB&preemptible=true)                                                                                 | Text-to-speech |

→ Full catalog (music, fine-tuning jobs, more): [templates/README.md](./templates/README.md)

### 🏋️ Training

Model training and fine-tuning workloads.

- [`axolotl-finetuning`](./training/axolotl-finetuning/README.md) — get started fine-tuning with Axolotl
- [`image-classifier-finetuning`](./training/image-classifier-finetuning/README.md) — fine-tune an image classifier on a HuggingFace dataset in a serverless GPU job
- [`train-and-serve`](./training/train-and-serve/README.md) — fine-tune TinyLlama in a Job and serve it with a vLLM Endpoint

### ⚡ Inference

Endpoint serving and batch inference workloads.

- [`vllm-endpoint`](./inference/vllm-endpoint/README.md) — serve Qwen with an OpenAI-compatible vLLM endpoint
- [`nim-endpoint`](./inference/nim-endpoint/README.md) — deploy an NVIDIA NIM as an endpoint, including the large-image Container Registry workaround
- [`flux2-klein-lora`](./inference/flux2-klein-lora/README.md) — build and serve a verified FLUX.2 Klein base 4B LoRA image endpoint

### 🤖 Agents

AI gateway and agent deployments.

- [`openclaw`](./agents/openclaw/README.md) — deploy OpenClaw AI gateway on a CPU endpoint, connected to TokenFactory

### 🧬 Life Science

Domain-specific simulation and analysis workloads.

- [`bionemo-agent`](./life-science/bionemo-agent/README.md) — deploy an NVIDIA NeMo Agent Toolkit BioNeMo research assistant with a GPU BioNeMo-compatible service
- [`openmm-simulation`](./life-science/openmm-simulation/README.md) — run GPU-backed molecular dynamics simulations with OpenMM
- [`parabricks-deepvariant`](./life-science/parabricks-deepvariant/README.md) — run NVIDIA Parabricks DeepVariant genomics workflows with Nebius AI Jobs

### 🦾 Robotics

Robotics and physical-AI experiment loops.

- [`lerobot-finetune-job`](./robotics/lerobot-finetune-job/README.md) — fine-tune a LeRobot ACT or Diffusion policy on a robotics dataset in a serverless GPU job
- [`smolva-ft-norma-core`](./robotics/smolva-ft-norma-core/README.md) — fine-tune SmolVLA for SO-101 with bundled trajectories

---

## Awesome Community Projects

External examples and writeups from the community running serverless workloads on Nebius. Got something to add? Open a PR.

### Robotics

- 🤖 **Positronic + Nebius serverless workflows** — Convert datasets, train ACT/SmolVLA, and serve checkpoints as endpoints — all serverless on Nebius. — _by vertix_ · [💻 code](https://github.com/vertix/positronic-open/tree/add-nebius-workflows/workflows/nebius)
- 🦾 **norma-core SmolVLA — Nebius fine-tune recipe** — Upstream recipe the [`robotics/smolva-ft-norma-core`](./robotics/smolva-ft-norma-core/) example mirrors. — _by norma-core_ · [💻 code](https://github.com/norma-core/norma-core/blob/main/software/ai/smolvla_py/nebius.md)

### MLOps / Pipelines

- 🎬 **Video transcription pipeline with Prefect + Nebius** — Prefect flows orchestrating S3 + ffmpeg (CPU job) + Whisper (GPU job) on Nebius. — _by Darko Mesaros_ · [💻 code](https://github.com/darko-mesaros/video-transcriber-prefect) · [📝 post](https://rup12.net/posts/video-transcription-pipeline-with-prefect-and-nebius/)

### Finance / Market Surveillance

- 📈 **LOB Arena — Adversarial market-surveillance evaluation** — Governed historical + synthetic order-book validation platform for benchmarking surveillance detectors, with Nebius Serverless AI Jobs and Endpoints for scalable evaluation and AI-assisted investigation. — _by Alexey Khabalov_ · [💻 code](https://github.com/khab40/lob-arena) · [📝 post](https://www.linkedin.com/pulse/building-lob-arena-adversarial-market-surveillance-nebius-khabalov-eqilf/)

---

## Repository structure

```
serverless-cookbook/
├── quickstarts/          # Lowest-friction first runs
├── templates/            # 1-click Console deploy templates
├── training/             # Model training and fine-tuning
├── inference/            # Endpoint serving and batch inference
├── agents/               # AI gateway and agent deployments
├── life-science/         # Domain-specific simulations
├── robotics/             # Robotics and physical-AI workflows
├── CONTRIBUTING.md
└── DEVELOPER_GUIDE.md
```

## Resources

- [Nebius Console](https://console.nebius.com)
- [Serverless AI docs](https://docs.nebius.com/serverless/overview)
- [CLI reference](https://docs.nebius.com/cli/reference/ai/)
- [Contributing guide](./CONTRIBUTING.md)
- [Developer guide](./DEVELOPER_GUIDE.md)

## Acknowledgements

This repository is based on [mnrozhkov/serverless-cookbook](https://github.com/mnrozhkov/serverless-cookbook). Thanks to the original contributors: [Mikhail Rozhkov](https://github.com/mnrozhkov), [Gleb Berjoskin](https://github.com/GlebBerjoskin), [Aleksandr Dzhumurat](https://github.com/aleksandr-dzhumurat), and [Re Alvarez Parmar](https://github.com/realvz).

See [CONTRIBUTORS.md](./CONTRIBUTORS.md) for the full list.

## License

Copyright 2026 Nebius B.V.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
<http://www.apache.org/licenses/LICENSE-2.0>

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

_Apache and the Apache logo are either registered trademarks or trademarks of The Apache Software Foundation in the United States and/or other countries._

---

> **Note:** This repository is maintained by Nebius engineers as a community resource — not official product documentation. APIs and behavior may evolve. For authoritative reference, see [docs.nebius.com/serverless](https://docs.nebius.com/serverless).
