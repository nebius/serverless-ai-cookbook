# Chatterbox

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fchatterbox-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Chatterbox is a MIT expressive English TTS model with bundled preset voices and an OpenAI-compatible speech API on preemptible H100.

**License:** [MIT](https://github.com/resemble-ai/chatterbox/blob/master/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/ResembleAI/chatterbox)

<!-- /factory:intro -->

---

title: Chatterbox
category: inference
type: endpoint
runtime: gpu-h100-sxm
frameworks: [chatterbox-tts]
keywords: [tts, text-to-speech, voice-clone, chatterbox, openai-speech, h100]
difficulty: intermediate

---

Expressive English text-to-speech endpoint serving [Chatterbox](https://huggingface.co/ResembleAI/chatterbox)
(Resemble AI) on a single preemptible H100. ~500M parameters, MIT license, and an
OpenAI-shaped speech API on port 8000.

Pair with [Kokoro-82M](../endpoint-kokoro-82m/README.md) for a lighter “simple TTS”
demo on L40S; Chatterbox targets expressive synthesis and zero-shot voice cloning
from bundled preset reference clips.

## Run

Synthesize speech with the bundled preset voice (`Emily.wav`):

```bash
curl -sS -X POST "$BASE_URL/v1/audio/speech" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Hello from Chatterbox on Nebius serverless.", "voice": "Emily.wav", "response_format": "wav"}' \
  -o chatterbox-sample.wav
```

Optional fields: `voice` (bundled `*.wav` preset under `/app/voices`), `response_format`
(`wav` or `mp3`). Use `voice: "default"` to skip reference audio and use Chatterbox's
built-in speaker.

## Expected output

- `GET /v1/models` with a valid token returns HTTP 200 and lists model id `tts-1`.
- `POST /v1/audio/speech` returns HTTP 200 with a non-empty audio body (`audio/wav`
  or `audio/mpeg`).
- First boot downloads ~2–3 GB of weights; cold start on H100 typically reaches READY
  within a few minutes. The server binds only after the model loads and warms the
  default preset voice.

## Architecture

```text
Client (curl / OpenAI SDK)
  │  Authorization: Bearer <endpoint token>
  ▼
FastAPI (serve.py)  :8000
  │  GET /v1/models
  │  POST /v1/audio/speech  →  ChatterboxTTS.generate()
  ▼
GPU (H100)  —  ResembleAI/chatterbox weights (HF Hub cache on disk)
  │
  └── /app/voices/*.wav  —  bundled reference clips for preset voices
```

The endpoint token is enforced by Nebius serverless; the container does not validate
API keys itself. One synthesis runs at a time (`threading.Lock`) because Chatterbox
is not safe for concurrent GPU generation on a single device.

## Voices

v1 smoke uses **bundled preset voices only** — pass a filename like `Emily.wav` in
the `voice` field. The default image ships `Emily.wav` (downloaded at build time from
the [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server)
voice pack). Add more `*.wav` files under `/app/voices` in a custom image build.

Upload-your-own reference audio for live cloning is a follow-up; this template does
not expose a multipart upload route.

## Env

`ux_case: one_click` — nothing is required. Defaults are baked into the image because
Deploy URLs cannot carry env vars; override only to retune:

| Var             | Default                 | Meaning                                                |
| --------------- | ----------------------- | ------------------------------------------------------ |
| `MODEL_ID`      | `ResembleAI/chatterbox` | Hugging Face repo (informational)                      |
| `DEFAULT_VOICE` | `Emily.wav`             | preset reference clip when `voice` is omitted          |
| `CFG_WEIGHT`    | `0.5`                   | classifier-free guidance (expressiveness vs stability) |
| `EXAGGERATION`  | `0.5`                   | prosody exaggeration (higher → more dramatic delivery) |
| `VOICES_DIR`    | `/app/voices`           | directory of bundled preset reference WAV files        |

## Build the image yourself

The endpoint runs a small [chatterbox-tts](https://github.com/resemble-ai/chatterbox)
server defined by this folder's `Dockerfile` and `serve.py`. To reproduce or modify
it, build and push to a registry you control, then deploy that ref:

```bash
cd templates/endpoint-chatterbox
docker build -t <your-registry>/chatterbox-serve:1 .
docker push <your-registry>/chatterbox-serve:1
```

Run it locally on a CUDA host to check before deploying:

```bash
docker run --rm --gpus all -p 8000:8000 <your-registry>/chatterbox-serve:1
curl -sS localhost:8000/v1/models
```

## Failure modes

| Symptom                                      | Likely cause                                                                         |
| -------------------------------------------- | ------------------------------------------------------------------------------------ |
| 502 / connection refused for several minutes | Weights still downloading; uvicorn has not bound yet                                 |
| `no CUDA device` in logs                     | Deployed on a CPU platform/preset                                                    |
| `unknown voice` HTTP 400                     | `voice` must match a `*.wav` under `/app/voices`                                     |
| OOM during load                              | Chatterbox 500M needs H100-class VRAM; do not downsize preset without testing        |
| Garbled or accented output                   | Reference clip language/accent mismatches the input text; pick a matching preset     |
| Slow first synthesis after READY             | First request for a new preset voice re-encodes conditionals from the reference clip |

## Toward production

- **Voice cloning uploads:** Add authenticated multipart storage (S3 / volume) and pass
  `audio_prompt_path` from uploaded clips instead of bundled presets only.
- **Turbo / multilingual:** Swap `ChatterboxTTS` for `ChatterboxTurboTTS` or
  `ChatterboxMultilingualTTS` in `serve.py` when latency or locale coverage matters
  more than the original English CFG controls.
- **Concurrency:** Scale out replicas rather than parallelizing synthesis on one GPU;
  Chatterbox generation is not thread-safe on a single device.
- **Observability:** Stream synthesis latency and VRAM in logs; alert on repeated 503
  during weight download.

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000. Wait until `/v1/models` returns JSON before synthesizing.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console
curl -sS "$BASE_URL/v1/models"
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
  --image cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/chatterbox-serve:d315ae1 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi
```

<!-- /factory:cli -->

## Troubleshooting

| Symptom                                                            | Cause                                                                                                                                                |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Quota limit exceeded` / `vpc.ipv4-address.public.count` on create | Tenant public IPv4 quota is full — delete STOPPED or ERROR endpoints (they still hold addresses until removed) or raise the VPC quota                |
| Smoke returns 502 for the first few minutes                        | Weights download at startup; wait for `ready in …s` in logs                                                                                          |
| Empty or failed MP3                                                | `ffmpeg` missing or synthesis error — check endpoint logs                                                                                            |
| `speed is not supported`                                           | OpenAI `speed` is accepted in the schema but Chatterbox has no speed knob in v1                                                                      |
| `502 failed to connect to local service`                           | Tunnel up but port 8000 not bound yet — poll `/v1/models`; RUNNING ≠ API ready                                                                       |
| Slow first pull                                                    | Add optional `HF_TOKEN`; disk throughput scales with size — template asks for 500 Gi                                                                 |
| Wrong image or port                                                | `cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/chatterbox-serve:d315ae1` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible) |
