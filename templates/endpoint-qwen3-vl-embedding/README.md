# Qwen3-VL-Embedding-8B

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-VL-Embedding-8B%20--runner%20pooling%20--trust-remote-code%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500Gi&amp;shmSize=16Gi&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Qwen3-VL-Embedding-8B is an Apache-2.0 multimodal embedding model that maps text, images, and video into one shared vector space, served OpenAI-compatibly via vLLM on preemptible H100.

**License:** [Apache-2.0](https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B)

<!-- /factory:intro -->

## What you get

An OpenAI-compatible `POST /v1/embeddings` endpoint. Send **text**, an **image**, a
**video**, or a mix, and get back one 4096-dim vector per input — the recall stage
for retrieval, clustering, semantic dedup, and auto-labeling pipelines. The model
supports Matryoshka truncation (shorter vectors) and inputs up to ~32k tokens.

Served with `--runner pooling` (embedding mode) and `--trust-remote-code` (the
model ships custom processing code). Requires vLLM ≥ 0.14.0; `vllm/vllm-openai:v0.19.1`
satisfies it. The 2B variant (`Qwen/Qwen3-VL-Embedding-2B`, 2048-dim) runs on a
single L40S — see [CLI alternative](#cli-alternative).

## Test request

Copy the endpoint's public URL from the console (**Public endpoints**) into `BASE_URL`.

> **Auth.** Like the other templates, this one deploys with **authentication off**
> by default so you can try it quickly — meaning the endpoint is publicly callable
> by anyone with the URL, so delete it when you're done. For production, create it
> with `--auth token` and set `TOKEN` below; the commands add
> `Authorization: Bearer $TOKEN` only when `TOKEN` is set.

> **URL note.** The examples below use the `IP:port` form. Nebius is moving public
> access to a managed HTTPS FQDN
> (`https://port8000-<id>.tunnel.applications.<region>.nebius.cloud`) and retiring
> raw-IP access — once your endpoint's FQDN responds, prefer it and set
> `BASE_URL` to it (drop the `http://`, it's already `https://`).

```bash
export BASE_URL='http://<IP>:8000'                 # from console → Public endpoints
export TOKEN='<endpoint-auth-token>'               # if you created it with --auth token
AUTH=(-H "Authorization: Bearer $TOKEN")           # omit if the endpoint is --auth none
```

**First boot:** Nebius may report RUNNING while the 8B weights are still loading.
Poll until the API answers before sending real requests:

```bash
until curl -sf "${AUTH[@]}" "$BASE_URL/v1/models" >/dev/null; do echo "waiting…"; sleep 15; done
```

### Text embedding

```bash
curl -sS -X POST "$BASE_URL/v1/embeddings" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-VL-Embedding-8B","input":"a car driving on a road"}' \
  | python3 -c 'import json,sys; v=json.load(sys.stdin)["data"][0]["embedding"]; print(f"dim={len(v)} first4={[round(x,4) for x in v[:4]]}")'
```

### Image embedding

Multimodal inputs use the chat-style `messages` content list on the same
`/v1/embeddings` route.

```bash
curl -sS -X POST "$BASE_URL/v1/embeddings" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "Qwen/Qwen3-VL-Embedding-8B",
        "encoding_format": "float",
        "messages": [{"role":"user","content":[
          {"type":"image_url","image_url":{"url":"https://images.pexels.com/photos/170811/pexels-photo-170811.jpeg?auto=compress&cs=tinysrgb&w=640"}}
        ]}]
      }' \
  | python3 -c 'import json,sys; v=json.load(sys.stdin)["data"][0]["embedding"]; print(f"dim={len(v)}")'
```

### Video embedding

Swap `image_url` for `video_url` to embed a clip (the model samples frames across
the video). Example uses a public dashcam driving clip:

```bash
curl -sS -X POST "$BASE_URL/v1/embeddings" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "Qwen/Qwen3-VL-Embedding-8B",
        "encoding_format": "float",
        "messages": [{"role":"user","content":[
          {"type":"video_url","video_url":{"url":"https://assets.mixkit.co/videos/42039/42039-720.mp4"}}
        ]}]
      }' \
  | python3 -c 'import json,sys; v=json.load(sys.stdin)["data"][0]["embedding"]; print(f"dim={len(v)}")'
```

### Cross-modal similarity (Python)

Embeds one text query, one image, and one video, then scores them. A car-related
query scores higher against both the car image and the driving video than an
unrelated query does — the basis for retrieval and auto-labeling.

```python
import json, math, os, urllib.request

BASE = os.environ["BASE_URL"].rstrip("/")
TOKEN = os.environ.get("TOKEN")
HEADERS = {"Content-Type": "application/json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

CAR_IMAGE = "https://images.pexels.com/photos/170811/pexels-photo-170811.jpeg?auto=compress&cs=tinysrgb&w=640"
DRIVE_VIDEO = "https://assets.mixkit.co/videos/42039/42039-720.mp4"


def embed(payload):
    body = json.dumps({"model": "Qwen/Qwen3-VL-Embedding-8B", **payload}).encode()
    req = urllib.request.Request(f"{BASE}/v1/embeddings", data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["data"][0]["embedding"]


def media(kind, url):
    key = {"image": "image_url", "video": "video_url"}[kind]
    return {"encoding_format": "float", "messages": [{"role": "user", "content": [{"type": key, key: {"url": url}}]}]}


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b)))


q_car = embed({"input": "a car driving on a road"})
q_food = embed({"input": "a plate of food on a table"})
image = embed(media("image", CAR_IMAGE))
video = embed(media("video", DRIVE_VIDEO))

print(f"dims: text={len(q_car)} image={len(image)} video={len(video)}")
print(f"video  vs 'car driving' : {cosine(video, q_car):.3f}   vs 'food' : {cosine(video, q_food):.3f}")
print(f"image  vs 'car driving' : {cosine(image, q_car):.3f}   vs 'food' : {cosine(image, q_food):.3f}")
```

Expected shape (exact values vary by GPU/version):

```text
dims: text=4096 image=4096 video=4096
video  vs 'car driving' : 0.125   vs 'food' : 0.061
image  vs 'car driving' : 0.088   vs 'food' : 0.040
```

For production, keep token auth on and send `Authorization: Bearer <token>` — see
[How to call an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-call-an-endpoint).

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

The image entrypoint is `vllm`, so pass the full server command as the container
command. `--args` is split on spaces into container args.

```bash
nebius ai endpoint create \
  --name qwen3-vl-embedding \
  --image vllm/vllm-openai:v0.19.1 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --auth token --token "$(openssl rand -hex 32)" \
  --container-command python3 \
  --args "-m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-VL-Embedding-8B --runner pooling --trust-remote-code --host 0.0.0.0 --port 8000"
```

Cheaper variant — the **2B** on a single L40S (change `--model` to
`Qwen/Qwen3-VL-Embedding-2B`, `--platform gpu-l40s-a`, `--preset 1gpu-8vcpu-32gb`).

<!-- /factory:cli -->

## Troubleshooting

- **404 `Not Found` (plain text) on every path** — you are hitting a URL the public gateway does not route yet. Use the `IP:port` from **Public endpoints**; if only a managed FQDN is shown and it 404s, the tunnel route may still be provisioning.
- **`502 failed to connect to local service`** — tunnel/ingress is up but the container has not bound port 8000 yet (weight download/load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as "API ready".
- **`unrecognized arguments` / module errors at start** — pass the real vLLM command, not a hand-split list. Use `--container-command python3` + `--args "-m vllm.entrypoints.openai.api_server --model … --runner pooling …"` exactly as above.
- **`--runner pooling` not recognized** — older vLLM builds use `--task embed`. This template targets vLLM ≥ 0.14.0 (the pinned `vllm/vllm-openai:v0.19.1` satisfies it).
- **Trust/remote-code error at load** — `--trust-remote-code` must stay in the command; Qwen3-VL-Embedding ships custom code.
- **Image/video rejected while text works** — use the `messages` content-list format (not `input`) for multimodal, and a directly fetchable media URL (the server downloads it; Wikimedia thumbnail URLs are often rejected — use a direct image/video URL).
- **Slow first pull** — the 8B multimodal weights are large; add optional env `HF_TOKEN` in the console and keep the 500 Gi disk.
