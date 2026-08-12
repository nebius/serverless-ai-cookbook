# Z-Image-Turbo

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Tongyi-MAI%2FZ-Image-Turbo%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500Gi&amp;shmSize=16Gi&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Z-Image-Turbo is a 6B Apache-2.0 text-to-image model distilled for 8-step generation, served on preemptible H100 via vLLM-Omni.

**License:** [Apache-2.0](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) · **Source:** [Hugging Face](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)

<!-- /factory:intro -->

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often several minutes). Wait until `/v1/models` returns
JSON before calling `/v1/images/generations`.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

Z-Image-Turbo is distilled for eight steps — use `num_inference_steps: 9`
(eight DiT forwards) and `guidance_scale: 0`.

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/images/generations" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a red fox in a snowy pine forest at golden hour", "size": "1024x1024", "num_inference_steps": 9, "guidance_scale": 0, "seed": 42}' \
  | python3 -c 'import base64,json,sys; p="z-image.png"; open(p,"wb").write(base64.b64decode(json.load(sys.stdin)["data"][0]["b64_json"])); print(f"wrote {p}")'
```

### Python

```python
import base64
import json
import os
import time
import urllib.error
import urllib.request

base = os.environ["BASE_URL"].rstrip("/")
out_path = "z-image.png"

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

body = json.dumps(
    {
        "prompt": "a red fox in a snowy pine forest at golden hour",
        "size": "1024x1024",
        "num_inference_steps": 9,
        "guidance_scale": 0,
        "seed": 42,
    }
).encode()
req = urllib.request.Request(
    f"{base}/v1/images/generations",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=300) as resp:
    payload = json.load(resp)

png = base64.b64decode(payload["data"][0]["b64_json"])
open(out_path, "wb").write(png)
print(f"wrote {out_path} ({len(png)} bytes)")
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
  --image vllm/vllm-omni:v0.24.0 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --container-command bash \
  --args '-c vllm serve Tongyi-MAI/Z-Image-Turbo --omni --host 0.0.0.0 --port 8000'
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **Very slow first pull** — add optional env `HF_TOKEN` in the console; prefer a larger disk (template asks for 500 Gi) so Hub throughput is higher.
- **Blurry / odd output with high step count** — do not raise `num_inference_steps` into the twenties; keep ~9 and `guidance_scale: 0`.
- **Wrong image or port** — `vllm/vllm-omni:v0.24.0` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible).
