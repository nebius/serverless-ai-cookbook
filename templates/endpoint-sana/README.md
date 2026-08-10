# Sana

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fsana-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500Gi&amp;shmSize=16Gi&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Sana 1.6B is a fast Apache-2.0 1024px text-to-image model (~9GB weights) for single-L40S Diffusers serving.

**License:** [Apache-2.0](https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px_diffusers/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px_diffusers)

<!-- /factory:intro -->

Text-to-image endpoint serving [Sana 1.6B](https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px_diffusers)
with Diffusers on a single L40S. 1024px images in ~20 steps; no gated weights.

Defaults are baked into the image (Deploy URLs cannot carry env vars). Optional
overrides: `MODEL_ID`, `MODEL_VARIANT`, `IMAGE_SIZE`, `INFERENCE_STEPS`,
`GUIDANCE_SCALE`. Changing `MODEL_ID` can change the license (BF16 / Sana-Sprint
are NVIDIA Open Model License).

## Build the image yourself

```bash
cd templates/endpoint-sana
docker build -t <your-registry>/sana-serve:1 .
docker push <your-registry>/sana-serve:1
```

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000. Wait until `/v1/models` returns JSON before generating.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/images/generations" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a red fox in a snowy pine forest at golden hour", "size": "1024x1024", "seed": 42}' \
  | python3 -c 'import base64,json,sys; p="sana.png"; open(p,"wb").write(base64.b64decode(json.load(sys.stdin)["data"][0]["b64_json"])); print(f"wrote {p}")'
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
out_path = "sana.png"

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
  --image cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/sana-serve:d315ae1 \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but port 8000 is not bound yet (weight download / load). Poll `/v1/models` until JSON; RUNNING ≠ API ready.
- **Very slow first pull** — add optional env `HF_TOKEN`; prefer 500 Gi disk for Hub throughput.
- **`no CUDA device`** — deployed on a CPU platform/preset.
- **Black or empty images** — keep text encoder / VAE in bf16; transformer stays fp16.
- **Wrong image or port** — `cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/sana-serve:d315ae1` on container port `8000` (`gpu-l40s-a` / `1gpu-8vcpu-32gb`, preemptible).
