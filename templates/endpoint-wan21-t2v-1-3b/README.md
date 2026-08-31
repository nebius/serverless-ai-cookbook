# Wan2.1-T2V-1.3B

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Wan-AI%2FWan2.1-T2V-1.3B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Wan2.1-T2V-1.3B is a compact Apache-2.0 text-to-video Diffusers checkpoint for short clips on preemptible H100 via vLLM-Omni.

**License:** [Apache-2.0](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers) · **Source:** [Hugging Face](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers)

<!-- /factory:intro -->

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often several minutes). Wait until `/v1/models` returns
JSON before calling `/v1/videos/sync`.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

Use the **Diffusers** repo id (`Wan-AI/Wan2.1-T2V-1.3B-Diffusers`). Sync
`POST /v1/videos/sync` returns a raw MP4 body. Wan2.1 needs `flow_shift=3.0` and
`boundary_ratio=0.0` on each request.

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS \
  -F "model=Wan-AI/Wan2.1-T2V-1.3B-Diffusers" \
  -F "prompt=A cat walking on a sunny sidewalk, cinematic, smooth camera motion" \
  -F "size=832x480" \
  -F "num_frames=17" \
  -F "fps=16" \
  -F "num_inference_steps=20" \
  -F "guidance_scale=5.0" \
  -F "flow_shift=3.0" \
  -F "boundary_ratio=0.0" \
  -F "seed=42" \
  "$BASE_URL/v1/videos/sync" \
  -o wan21-sample.mp4
echo "wrote wan21-sample.mp4 ($(wc -c < wan21-sample.mp4 | tr -d ' ') bytes)"
```

### Python

```python
import os
import time
import urllib.error
import urllib.request

base = os.environ["BASE_URL"].rstrip("/")

# Wait until the API is up (not just Nebius RUNNING)
for _ in range(60):  # up to ~15 min
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

print("ok /v1/models — use the curl multipart example for /v1/videos/sync (raw MP4)")
```

For longer clips, raise `num_frames` and use async `POST /v1/videos` plus polling
instead of `/v1/videos/sync`.

For production, enable token auth when creating the endpoint and send
`Authorization: Bearer <token>` — see
[How to call an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-call-an-endpoint).

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

```bash
nebius ai endpoint create \
  --image vllm/vllm-omni:v0.24.0 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --container-command bash \
  --args '-c vllm serve Wan-AI/Wan2.1-T2V-1.3B-Diffusers --omni --host 0.0.0.0 --port 8000'
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **Very slow first pull** — add optional env `HF_TOKEN` in the console; prefer a larger disk (template asks for 500 Gi) so Hub throughput is higher.
- **Garbled or static video** — set `flow_shift=3.0` and `boundary_ratio=0.0`.
- **Timeout on `/v1/videos/sync`** — clip too long for sync; use async `POST /v1/videos` + poll.
- **Wrong image or port** — `vllm/vllm-omni:v0.24.0` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible).
