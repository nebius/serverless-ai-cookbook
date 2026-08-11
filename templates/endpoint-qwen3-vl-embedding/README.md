# Qwen3-VL-Embedding-8B

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-VL-Embedding-8B%20--runner%20pooling%20--trust-remote-code%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500Gi&amp;shmSize=16Gi&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Qwen3-VL-Embedding-8B is a state-of-the-art Apache-2.0 multimodal embedding model that maps text, images, and video into a shared vector space, served OpenAI-compatibly via vLLM on a preemptible H100.

**License:** [Apache-2.0](https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B)

<!-- /factory:intro -->

## What you get

An OpenAI-compatible `/v1/embeddings` endpoint. Send text, an image, a video, or
a mix of them and get back a single dense vector per input — the recall stage for
retrieval, clustering, and auto-labeling pipelines. Vectors are 4096-dim (the 2B
variant is 2048-dim); the model supports Matryoshka truncation if you need shorter
vectors, and inputs up to ~32k tokens.

The 8B needs `--runner pooling` (embedding mode) and `--trust-remote-code` (the
model ships custom processing code). It requires vLLM ≥ 0.14.0.

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often several minutes on an 8B multimodal model). Wait until
`/v1/models` returns JSON before sending embedding requests.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

### curl — text embedding

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/embeddings" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-VL-Embedding-8B","input":"a photo of a golden retriever on a beach"}' \
  | python3 -c 'import json,sys; v=json.load(sys.stdin)["data"][0]["embedding"]; print(f"dim={len(v)} first={v[:4]}")'
```

### curl — image / video embedding

Multimodal inputs use the chat-style `messages` content list on the same
`/v1/embeddings` route (vLLM's multimodal embedding format). Swap `image_url`
for `video_url` to embed a clip.

```bash
curl -sS -X POST "$BASE_URL/v1/embeddings" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "Qwen/Qwen3-VL-Embedding-8B",
        "encoding_format": "float",
        "messages": [
          {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "https://raw.githubusercontent.com/vllm-project/vllm/main/docs/assets/logos/vllm-logo-text-light.png"}},
            {"type": "text", "text": "a software logo"}
          ]}
        ]
      }' \
  | python3 -c 'import json,sys; v=json.load(sys.stdin)["data"][0]["embedding"]; print(f"dim={len(v)} first={v[:4]}")'
```

### Python — cosine similarity across modalities

```python
import json
import os
import time
import urllib.error
import urllib.request

base = os.environ["BASE_URL"].rstrip("/")

# Wait until the API is up (not just Nebius RUNNING)
for _ in range(80):  # up to ~20 min for an 8B multimodal pull
    try:
        with urllib.request.urlopen(f"{base}/v1/models", timeout=30) as resp:
            if resp.status == 200:
                break
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
    print("waiting for /v1/models…")
    time.sleep(15)
else:
    raise SystemExit("timed out waiting for /v1/models")


def embed(payload):
    req = urllib.request.Request(
        f"{base}/v1/embeddings",
        data=json.dumps({"model": "Qwen/Qwen3-VL-Embedding-8B", **payload}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["data"][0]["embedding"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb)


text = embed({"input": "a golden retriever on a beach"})
image = embed({
    "encoding_format": "float",
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/9/93/Golden_Retriever_Carlos_%2810581910556%29.jpg"}},
    ]}],
})
print(f"text dim={len(text)} image dim={len(image)}")
print(f"text↔image cosine similarity: {cosine(text, image):.3f}")
```

For production, enable token auth when creating the endpoint and send
`Authorization: Bearer <token>` — see
[How to call an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-call-an-endpoint).

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

```bash
nebius ai endpoint create \
  --image vllm/vllm-openai:v0.19.1 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --container-command bash \
  --args '-c python3 -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-VL-Embedding-8B --runner pooling --trust-remote-code --host 0.0.0.0 --port 8000'
```

Cheaper variant — the **2B** on a single L40S:

```bash
nebius ai endpoint create \
  --image vllm/vllm-openai:v0.19.1 \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --container-command bash \
  --args '-c python3 -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-VL-Embedding-2B --runner pooling --trust-remote-code --host 0.0.0.0 --port 8000'
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **`--runner pooling` not recognized** — older vLLM builds use `--task embed` instead. This template targets vLLM ≥ 0.14.0 (the pinned `vllm/vllm-openai:v0.19.1` satisfies it).
- **Model fails to load with a trust/remote-code error** — Qwen3-VL-Embedding ships custom code; `--trust-remote-code` must stay in the command.
- **Very slow first pull** — the 8B multimodal weights are large; add optional env `HF_TOKEN` in the console and keep the 500 Gi disk so Hub throughput is higher.
- **Only text works, image/video rejected** — confirm the request uses the `messages` content-list format (not `input`) for multimodal, and that the vLLM version serves Qwen3-VL-Embedding's vision path.
- **Wrong image or port** — `vllm/vllm-openai:v0.19.1` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible).
