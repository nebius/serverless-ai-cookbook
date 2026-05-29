---
title: Deploy an NVIDIA NIM on a Serverless Endpoint
category: inference
type: endpoint
runtime: gpu
frameworks:
  - nvidia-nim
keywords:
  - nim
  - nvidia
  - inference
  - openai-compatible
  - image-generation
  - container-registry
difficulty: intermediate
---

# Deploy an NVIDIA NIM on a Serverless Endpoint

Use this example to serve an [NVIDIA NIM](https://build.nvidia.com/) microservice (LLM, embedding, or image-generation) as a Serverless AI Endpoint with an OpenAI-compatible API.

Keywords: NVIDIA NIM, nvcr.io, OpenAI-compatible API, GPU serving, Container Registry mirror

## What this example does

Deploys a NIM container (e.g. `meta/llama-3.2-1b-instruct` or `black-forest-labs/flux.2-klein-4b`) as a public, token-authenticated endpoint on port `8000`, then calls it with `curl`.

It also shows the **one non-obvious step** for NIMs on serverless: NIM images are large (10–25 GB+), and pulling them from `nvcr.io` at deploy time can exceed the endpoint cold-start window — the endpoint fails to start **with no container logs**. The fix is to mirror the image into your in-region Nebius **Container Registry** first and deploy from there.

> **Heads-up (known limitation):** Deploying a large NIM **directly** from `nvcr.io` often fails because the image pull doesn't finish inside the cold-start window (the endpoint goes to `ERROR` in ~2–3 min with no container logs). The mirror-to-Container-Registry step below is the reliable workaround today. A first-class fix (so you can point an endpoint straight at a NIM image without manual mirroring) is being worked on with the Nebius product team — once it lands, the mirror step becomes optional.

### Why this is useful

NIMs ship optimized, production-ready inference (TensorRT-LLM / SGLang backends, OpenAI-compatible routes). This gives you that on Nebius Serverless without managing VM lifecycle — and a registry-mirror pattern you can reuse for any large container.

### Requirements

- Nebius CLI installed and authenticated, with the profile pointed at your project
- An **NGC API key** with access to the NIM (`nvapi-...`, from <https://org.ngc.nvidia.com/setup/api-keys>)
- `docker` (to mirror the image) and `jq`
- GPU endpoint quota, a Container Registry, and a subnet in your project/region

### Runtime / compute

Pick a GPU that satisfies the model's [NIM support matrix](https://docs.nvidia.com/nim/). Validated here:

| NIM | Image size | Platform / preset | API |
|---|---|---|---|
| `meta/llama-3.2-1b-instruct:1.8.6` | ~17 GB | `gpu-rtx6000` / `1gpu-24vcpu-218gb` | `/v1/chat/completions` |
| `black-forest-labs/flux.2-klein-4b:1.0.1-variant` | ~24 GB | `gpu-h200-sxm` / `1gpu-16vcpu-200gb` (needs ≥48 GB VRAM) | `/v1/images/generations` |

Cold start is ~8–12 min the first time (internal image pull + one-time model-weight download from NGC + engine build/warmup).

## Run

### 0. Pick the NIM and set variables

```bash
# --- choose ONE NIM ---
export NIM_IMAGE="nvcr.io/nim/meta/llama-3.2-1b-instruct:1.8.6"   # LLM example
# export NIM_IMAGE="nvcr.io/nim/black-forest-labs/flux.2-klein-4b:1.0.1-variant"  # image-gen example

export NIM_NAME="$(basename "${NIM_IMAGE%%:*}")"                  # e.g. llama-3.2-1b-instruct
export NIM_TAG="${NIM_IMAGE##*:}"
export PLATFORM="gpu-rtx6000"          # use gpu-h200-sxm for flux (needs >=48GB VRAM)
export PRESET="1gpu-24vcpu-218gb"      # use 1gpu-16vcpu-200gb for gpu-h200-sxm
export REGION="us-central1"            # your project's region
export PROJECT_ID="<your-project-id>"  # project-...
export NGC_API_KEY="<your-nvapi-key>"  # nvapi-...
export AUTH_TOKEN="$(openssl rand -hex 16)"
```

### 1. Mirror the NIM image into your in-region Container Registry

This is the workaround for the large-image cold-start problem. Internal pulls are fast, and a same-project registry needs no pull credentials on the endpoint.

```bash
# Create (or reuse) a registry; REGISTRY_PATH is the registry ID without the "registry-" prefix
export REGISTRY_PATH=$(nebius registry create --name nim-mirror --parent-id "$PROJECT_ID" \
  --format json | jq -r '.metadata.id' | cut -d- -f2)
export REGISTRY="cr.${REGION}.nebius.cloud/${REGISTRY_PATH}"

# Authenticate docker for both registries
nebius registry configure-helper                                   # Nebius CR
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin

# Pull from NGC, then push to your CR (this is the only slow upload, and only once)
docker pull "$NIM_IMAGE"
docker tag  "$NIM_IMAGE" "${REGISTRY}/${NIM_NAME}:${NIM_TAG}"
docker push "${REGISTRY}/${NIM_NAME}:${NIM_TAG}"
```

> `scripts/deploy-nim.sh` runs steps 1–2 for you.

### 2. Create the endpoint (from your Container Registry)

```bash
export SUBNET_ID=$(nebius vpc subnet list --parent-id "$PROJECT_ID" \
  --format json | jq -r '.items[0].metadata.id')

nebius ai endpoint create \
  --parent-id "$PROJECT_ID" \
  --name "${NIM_NAME}" \
  --image "${REGISTRY}/${NIM_NAME}:${NIM_TAG}" \
  --container-port 8000 \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --disk-size 150Gi \
  --subnet-id "$SUBNET_ID" \
  --env NGC_API_KEY="$NGC_API_KEY" \
  --public \
  --auth token \
  --token "$AUTH_TOKEN"
```

`NGC_API_KEY` is still required at runtime: the NIM downloads model weights from NGC on first boot. For production, store it in a [MysteryBox secret](https://docs.nebius.com/serverless/endpoints/manage) and pass `--env-secret NGC_API_KEY=<secret>` instead of `--env`.

### 3. Wait until the model is ready

`RUNNING` means the container is up — the NIM may still be downloading weights / building its engine. Poll the health route:

```bash
export ENDPOINT_ID=$(nebius ai endpoint get-by-name --parent-id "$PROJECT_ID" \
  --name "$NIM_NAME" --format jsonpath='{.metadata.id}')
export ENDPOINT_IP=$(nebius ai endpoint get "$ENDPOINT_ID" \
  --format json | jq -r '.status.public_endpoints[0]')
export URL="http://${ENDPOINT_IP}"

# repeat until it returns {"status":"ready"} (a few minutes on first boot)
curl -s "$URL/v1/health/ready" -H "Authorization: Bearer $AUTH_TOKEN"
```

## Expected output

**LLM (`/v1/chat/completions`):**

```bash
MODEL=$(curl -s "$URL/v1/models" -H "Authorization: Bearer $AUTH_TOKEN" | jq -r '.data[0].id')
curl -s "$URL/v1/chat/completions" \
  -H "Authorization: Bearer $AUTH_TOKEN" -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"In one sentence, what is the capital of France?\"}],\"max_tokens\":60}" \
  | jq -r '.choices[0].message.content'
```

```
The capital of France is Paris.
```

**Image generation (`/v1/images/generations`, flux):** klein is a few-step model — `steps` is 1–4 and `cfg_scale` is fixed at `1.0`.

```bash
curl -s "$URL/v1/images/generations" \
  -H "Authorization: Bearer $AUTH_TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt":"a serene mountain lake at sunrise, photorealistic","size":"1024x1024","steps":4,"seed":42,"response_format":"b64_json"}' \
  | jq -r '.data[0].b64_json' | base64 -d > out.jpg
file out.jpg
```

```
out.jpg: JPEG image data, JFIF standard 1.01, 1024x1024   # ~3.9 s on one H200
```

A request **without** a valid token returns `401`; while the model is still warming up the proxy returns `502`.

## How to adapt

- **Any NIM:** change `NIM_IMAGE` (browse <https://build.nvidia.com/>), then set `PLATFORM`/`PRESET` to a GPU that meets its support matrix.
- **Cheaper/bigger GPU:** `gpu-rtx6000` (48 GB) is the cheapest GPU here; use `gpu-h200-sxm`/`gpu-b200-sxm` for larger models. List options with `nebius compute platform list`.
- **Private by default:** drop `--public` to keep the endpoint on the VPC only; reach it from `status.private_endpoints[0]`.
- **Secrets:** use `--env-secret` / `--registry-secret` (MysteryBox) instead of plaintext for anything sensitive.

## Troubleshooting

- **Endpoint → `ERROR` in ~2–3 min with no logs:** the image was too large to pull from `nvcr.io` inside the cold-start window. Mirror it to your in-region Container Registry (step 1) and deploy from there. See also [Endpoint stuck in STARTING](../../DEVELOPER_GUIDE.md#endpoint-stuck-in-starting).
- **`docker push` → `repository name not known to registry`:** `REGISTRY_PATH` is the registry ID **without** the `registry-` prefix (`... | cut -d- -f2`).
- **`502 Bad Gateway` with a valid token:** the NIM is still warming up — keep polling `/v1/health/ready` until `{"status":"ready"}`.
- **`401 Authorization Required`:** missing/wrong `Authorization: Bearer $AUTH_TOKEN`.
- **Stuck in `STARTING` > 30 min:** check `nebius ai endpoint logs "$ENDPOINT_ID" --follow`; verify the GPU meets the model's VRAM requirement and that `NGC_API_KEY` is set (needed for the weight download).

## Cleanup

```bash
nebius ai endpoint delete "$ENDPOINT_ID"
# the mirrored image stays in your Container Registry for fast future deploys
```
