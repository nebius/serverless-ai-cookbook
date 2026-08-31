# Kokoro-82M

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fkokoro-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Kokoro-82M is an 82M-parameter Apache-2.0 text-to-speech model with an OpenAI-compatible speech API on a single L40S.

**License:** [Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/hexgrad/Kokoro-82M)

<!-- /factory:intro -->

Text-to-speech endpoint serving [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
(~82M params, ~1 GB weights) on a preemptible L40S with an OpenAI-shaped speech API.

Default voice: **`af_bella`**. Common picks: `af_heart`, `af_nicole`, `am_adam`,
`bf_emma`, `bm_george`. Full list: [VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md).
This image ships English G2P only.

Optional env overrides: `MODEL_ID`, `DEFAULT_VOICE`, `LANG_CODE`.

## Build the image yourself

```bash
cd templates/endpoint-kokoro-82m
docker build -t <your-registry>/kokoro-serve:1 .
docker push <your-registry>/kokoro-serve:1
```

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000. Wait until `/v1/models` returns JSON before synthesizing.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model": "kokoro", "input": "Hello from Kokoro on Nebius serverless.", "voice": "af_bella", "response_format": "mp3"}' \
  -o kokoro-sample.mp3
echo "wrote kokoro-sample.mp3 ($(wc -c < kokoro-sample.mp3 | tr -d ' ') bytes)"
```

### Python

```python
import json
import os
import time
import urllib.error
import urllib.request

base = os.environ["BASE_URL"].rstrip("/")
out_path = "kokoro-sample.mp3"

for _ in range(40):  # up to ~10 min
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
        "model": "kokoro",
        "input": "Hello from Kokoro on Nebius serverless.",
        "voice": "af_bella",
        "response_format": "mp3",
    }
).encode()
req = urllib.request.Request(
    f"{base}/v1/audio/speech",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    audio = resp.read()

open(out_path, "wb").write(audio)
print(f"wrote {out_path} ({len(audio)} bytes)")
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
  --image cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/kokoro-serve:d315ae1 \
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

- **`502 failed to connect to local service`** — tunnel is up but port 8000 is not bound yet. Poll `/v1/models`; RUNNING ≠ API ready.
- **`espeak-ng not found`** — image build skipped `espeak-ng` (required for English G2P fallback).
- **Empty or failed MP3** — `ffmpeg` missing or synthesis error; check endpoint logs.
- **Wrong voice locale** — voice prefix must match G2P locale (e.g. `bf_*` needs British English).
- **Wrong image or port** — `cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/kokoro-serve:d315ae1` on port `8000` (`gpu-l40s-a` / `1gpu-8vcpu-32gb`).
