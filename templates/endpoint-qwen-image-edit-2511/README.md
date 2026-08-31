# Qwen-Image-Edit-2511

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Qwen%2FQwen-Image-Edit-2511%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Qwen-Image-Edit-2511 is an Apache-2.0 image-to-image editor for instruction-based edits, served on preemptible H100 via vLLM-Omni.

**License:** [Apache-2.0](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) · **Source:** [Hugging Face](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)

<!-- /factory:intro -->

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often several minutes). Wait until `/v1/models` returns
JSON before calling `/v1/images/edits`.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

Edit is multipart `POST /v1/images/edits` (image file + prompt) — not JSON
`/v1/images/generations`. Run the curl from this package directory so
`samples/image.png` resolves (or pass an absolute path).

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/images/edits" \
  -F "model=Qwen/Qwen-Image-Edit-2511" \
  -F "image=@samples/image.png" \
  -F "prompt=make the sky a dramatic sunset" \
  -F "size=1024x1024" \
  -F "output_format=png" \
  -F "num_inference_steps=20" \
  -F "seed=42" \
  | python3 -c 'import base64,json,sys; p="qwen-edit.png"; open(p,"wb").write(base64.b64decode(json.load(sys.stdin)["data"][0]["b64_json"])); print(f"wrote {p}")'
```

### Python

```python
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

base = os.environ["BASE_URL"].rstrip("/")
image_path = Path("samples/image.png")

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

print("ok /v1/models — use the curl multipart example for /v1/images/edits")
print("image:", image_path.resolve())
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
  --args '-c vllm serve Qwen/Qwen-Image-Edit-2511 --omni --host 0.0.0.0 --port 8000'
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **Very slow first pull** — add optional env `HF_TOKEN` in the console; prefer a larger disk (template asks for 500 Gi) so Hub throughput is higher.
- **Wrong field names** — send the input file as form field `image` with a text `prompt`.
- **Wrong image or port** — `vllm/vllm-omni:v0.24.0` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible).
