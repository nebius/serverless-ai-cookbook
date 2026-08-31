# ACE-Step 1.5

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Facestep-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

ACE-Step 1.5 is an MIT text-to-audio (music) model with a sync OpenAI-shaped generation API on preemptible H100.

**License:** [MIT](https://huggingface.co/ACE-Step/Ace-Step1.5/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/ACE-Step/Ace-Step1.5)

<!-- /factory:intro -->

---

title: Ace-Step 1.5
category: inference
type: endpoint
runtime: gpu-h100-sxm
frameworks: [ace-step]
keywords: [t2a, text-to-audio, music-generation, ace-step, openai-audio, h100]
difficulty: intermediate

---

Text-to-audio (music) endpoint serving [ACE-Step 1.5](https://huggingface.co/ACE-Step/Ace-Step1.5)
(ACE-Step) on a single preemptible H100. MIT license, no gated weights, and a
catalog-friendly synchronous API on port 8000.

Upstream ACE-Step ships an async FastAPI server (`POST /release_task` +
`POST /query_result`). This template wraps it with `POST /v1/audio/generations`
that blocks until audio is ready — similar to vLLM-Omni `/v1/videos/sync`.

## Run

Generate a short instrumental clip (DiT-only, no LM “thinking” — faster smoke):

```bash
curl -sS -X POST "$BASE_URL/v1/audio/generations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ACE-Step/Ace-Step1.5",
    "prompt": "upbeat lo-fi drums with warm bass, instrumental",
    "task_type": "text2music",
    "thinking": false,
    "audio_duration": 8,
    "inference_steps": 8,
    "audio_format": "mp3"
  }' \
  -o ace-step-sample.mp3
```

Optional fields: `lyrics`, `thinking` (set `true` for LM-enhanced quality),
`audio_duration`, `inference_steps`, `audio_format` (`mp3` or `wav`), `bpm`,
`key_scale`, `time_signature`. For longer clips or batch jobs, call upstream
`POST /release_task` on the internal acestep-api port directly from a sidecar or
custom client.

## Expected output

- `GET /v1/models` with a valid token returns HTTP 200 and lists model id
  `ACE-Step/Ace-Step1.5`.
- `POST /v1/audio/generations` returns HTTP 200 with a non-empty audio body
  (`audio/mpeg` for MP3 or `audio/wav` for WAV).
- First boot downloads several GB of DiT + LM weights; cold start on H100 typically
  reaches READY within tens of minutes. The wrapper binds port 8000 only after
  upstream `/health` succeeds.

## Architecture

```text
Client (curl / OpenAI SDK)
  │  Authorization: Bearer <endpoint token>
  ▼
FastAPI wrapper (serve.py)  :8000
  │  GET /v1/models
  │  POST /v1/audio/generations
  │      → POST /release_task
  │      → poll POST /query_result
  │      → GET /v1/audio?path=…
  ▼
acestep-api (upstream)  :8001  —  ACE-Step 1.5 task queue + DiT/LM workers
  ▼
GPU (H100)  —  acestep-v15-turbo DiT + acestep-5Hz-lm-0.6B (HF Hub cache on disk)
```

The Nebius endpoint token is enforced at the platform edge; the container does not
validate API keys itself. One generation runs at a time (`threading.Lock`) because
ACE-Step's worker queue is sized for a single GPU.

## Env

`ux_case: one_click` — nothing is required. Defaults are baked into the image because
Deploy URLs cannot carry env vars; override only to retune:

| Var                     | Default                | Meaning                                                           |
| ----------------------- | ---------------------- | ----------------------------------------------------------------- |
| `ACESTEP_CONFIG_PATH`   | `acestep-v15-turbo`    | DiT checkpoint loaded at startup                                  |
| `ACESTEP_LM_MODEL_PATH` | `acestep-5Hz-lm-0.6B`  | 5Hz LM for `thinking=true` / metadata                             |
| `ACESTEP_NO_INIT`       | `false`                | Eager-load models at boot (recommended for smoke)                 |
| `ACESTEP_INIT_LLM`      | `false`                | Force DiT-only (skip vLLM 5Hz LM). Set `true` for `thinking=true` |
| `API_MODEL`             | `ACE-Step/Ace-Step1.5` | Catalog model id returned by `/v1/models`                         |
| `ACESTEP_API_PORT`      | `8001`                 | Internal upstream port (do not expose publicly)                   |
| `POLL_TIMEOUT_S`        | `900`                  | Max wait for sync generation                                      |

## Build the image yourself

The endpoint runs upstream [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5)
(`acestep-api`) plus this folder's sync wrapper. Build and push to a registry you
control, then deploy that ref:

```bash
cd templates/endpoint-ace-step-1-5
docker build -t <your-registry>/acestep-serve:1 .
docker push <your-registry>/acestep-serve:1
```

Run it locally on a CUDA host to check before deploying:

```bash
docker run --rm --gpus all -p 8000:8000 --shm-size=16g <your-registry>/acestep-serve:1
curl -sS localhost:8000/v1/models
```

## Failure modes

| Symptom                                   | Likely cause                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 502 / connection refused for many minutes | Weights still downloading; acestep-api has not passed `/health` yet                               |
| `acestep-api exited early` / exit -11     | Often vLLM LM segfault — keep `ACESTEP_INIT_LLM=false` for DiT-only smoke; else check CUDA/driver |
| `acestep-api exited early` (other codes)  | CUDA/driver mismatch or failed pip install — check GPU platform                                   |
| OOM during model init                     | H100 preset required; do not downsize without offloading flags                                    |
| HTTP 504 on `/v1/audio/generations`       | Clip too long or cold queue backlog — raise `POLL_TIMEOUT_S` or use async upstream API            |
| Empty MP3                                 | Upstream task failed — inspect acestep-api logs for DiT/LM errors                                 |
| Preemptible stop mid-generation           | Retry the request; prefer async upstream jobs for long clips                                      |

## Toward production

- **Async jobs:** Expose upstream `/release_task` + `/query_result` directly (or via a
  gateway) when clients should not hold HTTP connections for minutes.
- **Quality vs latency:** Set `ACESTEP_INIT_LLM=true` and `thinking: true` (plus more
  `inference_steps`) for LM-guided generation; keep defaults (`INIT_LLM=false`,
  `thinking: false`) for fast DiT-only previews.
- **Model variants:** Swap `ACESTEP_CONFIG_PATH` to `acestep-v15-base` for fine-tune
  workflows (separate backlog template).
- **Concurrency:** Scale out endpoint replicas; do not raise in-process worker count on
  one GPU (upstream queue is single-worker by design).
- **Observability:** Log task ids, queue depth, and VRAM at init; alert on repeated 504s.

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often 15–30+ minutes). Wait until `/v1/models` returns
JSON before generating.

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
  --image cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/acestep-serve:d315ae1 \
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

| Symptom                                        | Cause                                                                                                                                             |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Smoke returns 502 for the first 15–30+ minutes | DiT + LM weights download on first boot; wait for `upstream ready` in logs                                                                        |
| `no CUDA device` in logs                       | Deployed on a CPU platform/preset                                                                                                                 |
| `generation timed out`                         | Increase `POLL_TIMEOUT_S` or shorten `audio_duration` / `inference_steps`                                                                         |
| `502 failed to connect to local service`       | Tunnel up but port 8000 not bound yet — poll `/v1/models`; RUNNING ≠ API ready                                                                    |
| Slow first pull                                | Add optional `HF_TOKEN`; disk throughput scales with size — template asks for 500 Gi                                                              |
| `shm` errors in worker logs                    | Request `--shm-size 16Gi` (set in deploy configuration)                                                                                           |
| Wrong image or port                            | `cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/acestep-serve:d315ae1` on container port `8000` (`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, preemptible) |
