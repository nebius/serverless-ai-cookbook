---
title: Two models on one endpoint
category: inference
type: endpoint
runtime: gpu
frameworks:
  - vllm
keywords:
  - llm
  - inference
  - openai-compatible
  - multi-model
  - multi-port
  - tensor-parallel
difficulty: intermediate
---

# Two models on one endpoint

Use this example when you want two models to share one multi-GPU machine, each with its
own URL, instead of paying for two machines.

Keywords: two models one GPU host, CUDA_VISIBLE_DEVICES, multiple container ports, vLLM tensor parallel

## What this example does

Runs two independent vLLM servers inside a single endpoint. Each server gets its own
half of the GPUs through `CUDA_VISIBLE_DEVICES`, its own container port, and its own
managed HTTPS URL. Clients call them like two separate OpenAI-compatible APIs.

### Why this is useful

An endpoint is one container on one VM, so two endpoints always mean two VMs. That
matters when a platform has no preset for half a machine. On `gpu-b300-sxm` the only
presets are:

| Preset | GPUs |
| --- | --- |
| `1gpu-24vcpu-346gb` | 1 |
| `8gpu-192vcpu-2768gb` | 8 |

There is no 4-GPU preset, so you cannot buy two half-size endpoints and split an 8-GPU
box that way. Running both servers inside one endpoint is how you get 4+4. The same
pattern applies to `gpu-h100-sxm` and `gpu-h200-sxm`, which also jump from 1 GPU to 8.

Check what your platform offers before assuming you need this:

```bash
nebius compute platform list --parent-id "$NEBIUS_PROJECT_ID"
```

If your platform does have a half-size preset, prefer two ordinary endpoints. They scale,
restart and get preempted independently, which this pattern gives up.

### Requirements

- Nebius CLI installed and authenticated
- GPU endpoint quota for the 8-GPU preset, and a subnet
- Enough GPU memory for both models at the tensor-parallel sizes you choose

### Runtime / compute

- image: `vllm/vllm-openai:v0.29.0`
- platform and preset: `gpu-b300-sxm` with `8gpu-192vcpu-2768gb`
- split: GPUs 0-3 serve the first model, GPUs 4-7 serve the second, tensor parallel 4 each

## Quickstart

Each `--container-port` is exposed separately, so two ports give two managed URLs.

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export AUTH_TOKEN="$(openssl rand -hex 32)"

SERVE_BOTH='set -e
nvidia-smi --query-gpu=index,name --format=csv,noheader
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve Qwen/Qwen3-8B --tensor-parallel-size 4 \
  --served-model-name model-a --host 0.0.0.0 --port 8000 &
CUDA_VISIBLE_DEVICES=4,5,6,7 vllm serve Qwen/Qwen3-4B --tensor-parallel-size 4 \
  --served-model-name model-b --host 0.0.0.0 --port 8001 &
wait -n'

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name two-models-one-endpoint \
  --image vllm/vllm-openai:v0.29.0 \
  --platform gpu-b300-sxm \
  --preset 8gpu-192vcpu-2768gb \
  --preemptible \
  --follows-spot-price \
  --container-port 8000 \
  --container-port 8001 \
  --disk-size 500Gi \
  --shm-size 32Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --public \
  --auth token \
  --token "$AUTH_TOKEN" \
  --container-command /bin/bash \
  --args "-lc \"$SERVE_BOTH\""
```

`wait -n` returns as soon as either server exits, so the container stops instead of
serving half the models. `--follows-spot-price` accepts the current spot price with no
cap; drop it and `--preemptible` for retained capacity, or cap the price with
`--spot-pricing-policy-id`.

Both URLs come from the endpoint itself:

```bash
nebius ai endpoint get --id "$ENDPOINT_ID" --format json \
  | jq -r '.status.public_endpoints[] | select(startswith("https"))'
```

## Expected output

Two URLs that differ only by port prefix, on the same host:

```text
https://port8000-<id>.tunnel.applications.<region>.nebius.cloud
https://port8001-<id>.tunnel.applications.<region>.nebius.cloud
```

Each answers only for its own model, and the endpoint's token protects both:

```bash
curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$URL_8000/v1/models" | jq -r '.data[].id'
# model-a

curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H 'Content-Type: application/json' \
  -d '{"model":"model-b","messages":[{"role":"user","content":"Hello"}],"max_tokens":24}' \
  "$URL_8001/v1/chat/completions" | jq -r '.choices[0].message.content'
```

A request without the token returns `401` on both ports.

In the validation run on 8×B300 in `eu-west2` the container saw all eight GPUs, and each
server reported `265.86/267.69 GiB` free on its own devices at startup, which is what
confirms the two processes did not share GPUs. Both servers answered about 145 seconds
after the endpoint reached `RUNNING`, following the image pull and weight download. That
run wrote each server's output to its own file instead of using `wait -n`; the `wait -n`
form above was then confirmed separately, with the container staying up and both ports
serving.

## How to adapt it

- **Uneven split.** Give one model more GPUs, for example `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5`
  with `--tensor-parallel-size 6` and the rest to the second. Tensor parallel size must
  equal the number of visible devices.
- **More than two models.** Add more ports and more `CUDA_VISIBLE_DEVICES` groups. Every
  port needs its own `--container-port`.
- **One URL instead of two.** Put a small proxy on a single port that reads the `model`
  field from the request body and forwards to the right local server. Only that port is
  then exposed.
- **Other platforms.** `gpu-h100-sxm` and `gpu-h200-sxm` use `8gpu-128vcpu-1600gb` and the
  same 1-or-8 choice.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Only one URL returned | Only one `--container-port` was passed; each port needs its own flag. |
| Second server fails with out-of-memory | Both servers default to a large share of each GPU. They are on separate GPUs here, so check the split is actually disjoint, then lower `--gpu-memory-utilization`. |
| `ValueError` about tensor parallel size | `--tensor-parallel-size` must equal the count in `CUDA_VISIBLE_DEVICES`. |
| Endpoint restarts after one model crashes | Expected with `wait -n`: the container exits so the platform restarts it, rather than serving half the models. |
| Endpoint went `STOPPED` on its own | Preemptible capacity was reclaimed. Start it again with `nebius ai endpoint start`, or use retained capacity. |
| Both models slow under load | They share the host's CPU, memory bandwidth and network. Independent endpoints isolate noisy neighbours; this pattern does not. |
