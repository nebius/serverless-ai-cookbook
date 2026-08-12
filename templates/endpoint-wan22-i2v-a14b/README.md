# Wan2.2-I2V-A14B

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Wan-AI%2FWan2.2-I2V-A14B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500Gi&amp;shmSize=16Gi&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Wan2.2-I2V-A14B is a flagship Apache-2.0 image-to-video model (~35GB) for 480p clips on preemptible H100 via vLLM-Omni.

**License:** [Apache-2.0](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B-Diffusers) · **Source:** [Hugging Face](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B-Diffusers)

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

Use the **Diffusers** repo id (`Wan-AI/Wan2.2-I2V-A14B-Diffusers`). Upload the
source frame as multipart field `input_reference` (not `image`). Wan2.2 I2V at
480p needs `flow_shift=12.0`, `boundary_ratio=0.875`, and
`guidance_scale` / `guidance_scale_2` = `1.0`. Run the curl from this package
directory so `samples/image.png` resolves (or pass an absolute path).

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS \
  -F "model=Wan-AI/Wan2.2-I2V-A14B-Diffusers" \
  -F "input_reference=@samples/image.png" \
  -F "prompt=Camera slowly pushes in, smooth cinematic motion" \
  -F "size=832x480" \
  -F "num_frames=17" \
  -F "fps=16" \
  -F "num_inference_steps=20" \
  -F "guidance_scale=1.0" \
  -F "guidance_scale_2=1.0" \
  -F "flow_shift=12.0" \
  -F "boundary_ratio=0.875" \
  -F "seed=42" \
  "$BASE_URL/v1/videos/sync" \
  -o wan22-i2v-sample.mp4
echo "wrote wan22-i2v-sample.mp4 ($(wc -c < wan22-i2v-sample.mp4 | tr -d ' ') bytes)"
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

For longer clips, prefer async `POST /v1/videos` with polling.

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
  --args '-c vllm serve Wan-AI/Wan2.2-I2V-A14B-Diffusers --omni --host 0.0.0.0 --port 8000'
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **Very slow first pull** — add optional env `HF_TOKEN` in the console; prefer a larger disk (template asks for 500 Gi) so Hub throughput is higher.
- **Bad motion / artifacts** — confirm Wan2.2 480p params (`flow_shift=12.0`, `boundary_ratio=0.875`, guidance 1.0).
- **Wrong upload field** — use `input_reference`, not `image`.
- **Wrong image or port** — `vllm/vllm-omni:v0.24.0` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible).
