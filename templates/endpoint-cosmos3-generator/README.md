# Cosmos 3 Generator (Nano)

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Acosmos3&amp;command=vllm%20serve%20nvidia%2FCosmos3-Nano%20--omni%20--model-class-name%20Cosmos3OmniDiffusersPipeline%20--no-guardrails%20--host%200.0.0.0%20--port%208000%20--init-timeout%201800&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Cosmos3-Nano is NVIDIA's 16B omnimodal world model for Physical AI; this template serves its **Generator** surface — text-to-image, text-to-video, image-to-video and video-to-video with optional synchronized sound — through vLLM-Omni's OpenAI-style API on preemptible H100.

**License:** [OpenMDW-1.1](https://openmdw.ai/license/1-1/) · **Source:** [Hugging Face](https://huggingface.co/nvidia/Cosmos3-Nano) · [NVIDIA Cosmos](https://github.com/nvidia/cosmos)

<!-- /factory:intro -->

## What you get

A vLLM-Omni server exposing the Cosmos 3 Generator:

| Workflow | Route | Output |
| --- | --- | --- |
| Text-to-image | `POST /v1/images/generations` (JSON) | base64 PNG, a few seconds |
| Text-to-video | `POST /v1/videos` (multipart) → poll → `/content` | MP4, 1–4 minutes |
| Image-to-video | same, plus `input_reference=@image` | MP4 |
| Video-to-video | same, plus `input_reference=@video` or a `video_reference` URL | MP4 |
| Video with sound | add `generate_sound=true` | MP4 with an audio track |

Forward/inverse dynamics, action policy and transfer controls (edge, depth,
segmentation) use the same server; see NVIDIA's
[Generator notebooks](https://github.com/nvidia/cosmos/tree/main/cookbooks/cosmos3/generator).
World *understanding* (captioning, grounding, reasoning) is the Reasoner surface —
use the [Cosmos 3 Reasoner](../endpoint-cosmos3-reasoner/README.md) template for that.

The Generator loads ~30 GiB onto the GPU (diffusion expert, video VAE, sound
tokenizer). Nano fits one H100; Super needs tensor parallelism (see CLI alternative).

> ⚠️ **Guardrails are off in this template.** vLLM-Omni normally loads
> [nvidia/Cosmos-1.0-Guardrail](https://huggingface.co/nvidia/Cosmos-1.0-Guardrail) (a
> prompt filter plus an output video filter with face blurring) at startup. That repository
> is **gated**, and without access the server exits before serving — so the 1-click command
> passes `--no-guardrails`. To turn guardrails on: (1) request access to the gated repo on
> Hugging Face, (2) add an env `HF_TOKEN` with a token that has that access when creating the
> endpoint, (3) remove `--no-guardrails` from the command. Either way, filter generated media
> before exposing it publicly; NVIDIA places
> [license compliance](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
> on the deployer.

## Test request

Copy the endpoint's public URL from the console (**Public endpoints**) into `BASE_URL`.
Prefer the managed HTTPS FQDN (`https://port8000-<id>.tunnel.applications.<region>.nebius.cloud`).

> **Auth.** The 1-click link **enables token authentication** — the create form opens with
> Token auth selected and you generate the token there. Every call needs
> `Authorization: Bearer <token>`; set `TOKEN` below and the snippets add the header. For a
> quick public test, set Authentication to None and leave `AUTH` empty.

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.eu-north1.nebius.cloud'
export TOKEN='<endpoint-auth-token>'
AUTH=(-H "Authorization: Bearer $TOKEN")           # AUTH=() if the endpoint has no auth
```

**First boot:** the 32.6 GiB repository is pulled from the Hub, then vLLM-Omni warms the
pipeline — about 10 minutes from create to first answer, during which the console already
shows RUNNING. Poll until the API answers:

```bash
until curl -sf "${AUTH[@]}" "$BASE_URL/v1/models" >/dev/null; do echo "waiting…"; sleep 15; done
```

Parameters below are NVIDIA's official Cosmos 3 sampling settings (`num_inference_steps 35`,
`guidance_scale 6.0`, `flow_shift 10.0`, 720p at 24 fps). Short prompts are fine — the
Generator upsamples them into dense scene descriptions.

### Text-to-image

```bash
curl -sS -X POST "$BASE_URL/v1/images/generations" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano",
  "prompt": "A photorealistic red sports car on a city street at golden hour, cinematic lighting.",
  "negative_prompt": "blurry, distorted, low quality",
  "size": "1024x1024", "n": 1, "response_format": "b64_json",
  "num_inference_steps": 50, "guidance_scale": 7.0, "seed": 42
}' | python3 -c 'import sys,json,base64; open("cosmos3_t2i.png","wb").write(base64.b64decode(json.load(sys.stdin)["data"][0]["b64_json"])); print("wrote cosmos3_t2i.png")'
```

Observed: HTTP 200 in 3.2 s, 3.1 MB PNG.

### Text-to-video (async job)

Video generation takes minutes, and the public gateway closes idle HTTP responses after
**60 seconds** — so `POST /v1/videos/sync` returns `504 Gateway Time-out` for anything but
very short clips while the GPU keeps rendering. Use the **async** route: submit, poll, download.

```bash
JOB=$(curl -sS -X POST "$BASE_URL/v1/videos" "${AUTH[@]}" -H "Accept: application/json" \
  --form-string "model=nvidia/Cosmos3-Nano" \
  --form-string "prompt=A small warehouse robot moves a blue box across a clean floor." \
  --form-string "negative_prompt=blurry, distorted, low quality" \
  --form-string "size=1280x720" --form-string "num_frames=81" --form-string "fps=24" \
  --form-string "num_inference_steps=35" --form-string "guidance_scale=6.0" --form-string "flow_shift=10.0" \
  --form-string "seed=42" \
  --form-string 'extra_params={"use_resolution_template":false,"use_duration_template":false,"guardrails":false}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "job $JOB"

until [ "$(curl -sS "${AUTH[@]}" "$BASE_URL/v1/videos/$JOB" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')" = "completed" ]; do sleep 10; done
curl -sS -L "${AUTH[@]}" "$BASE_URL/v1/videos/$JOB/content" -o cosmos3_t2v.mp4
echo "wrote cosmos3_t2v.mp4 ($(wc -c < cosmos3_t2v.mp4 | tr -d ' ') bytes)"
```

`status` moves `queued → in_progress → completed` (or `failed`). `num_frames=189` is the
standard 7.9-second clip; `81` renders in about a minute on an H100 and is a good first test; 189 frames take
3–4 minutes. See [Observed results](#observed-results).

### Image-to-video

Upload the conditioning image as `input_reference` (multipart). The example uses NVIDIA's
public sample frame.

```bash
curl -sfLO https://raw.githubusercontent.com/nvidia/cosmos/main/cookbooks/cosmos3/generator/audiovisual/assets/images/image2video/car_driving.jpg

JOB=$(curl -sS -X POST "$BASE_URL/v1/videos" "${AUTH[@]}" -H "Accept: application/json" \
  -F "model=nvidia/Cosmos3-Nano" \
  -F "prompt=The car keeps driving along the road with smooth, natural motion." \
  -F "negative_prompt=blurry, distorted, low quality" \
  -F "size=1280x720" -F "num_frames=81" -F "fps=24" \
  -F "num_inference_steps=35" -F "guidance_scale=6.0" -F "max_sequence_length=4096" -F "flow_shift=10.0" \
  -F 'extra_params={"use_resolution_template":false,"use_duration_template":false,"guardrails":false}' \
  -F "seed=1111" \
  -F "input_reference=@car_driving.jpg;type=image/jpeg" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

Poll and download exactly as above. For **video-to-video**, pass a video instead
(`-F "input_reference=@clip.mp4;type=video/mp4"`, or a JSON URL reference
`--form-string 'video_reference={"video_url":"https://…/clip.mp4"}'`) and add
`"condition_frame_indexes_vision":[0,1],"condition_video_keep":"first"` to `extra_params`.

### Video with synchronized sound

Add two form fields to a text-to-video or image-to-video job:

```bash
  --form-string "generate_sound=true" --form-string "sound_duration=7.875"   # 189 frames @ 24 fps
```

### Python

```python
import os, time, requests

BASE = os.environ["BASE_URL"].rstrip("/")
H = {"Authorization": f"Bearer {os.environ['TOKEN']}"} if os.environ.get("TOKEN") else {}

job = requests.post(f"{BASE}/v1/videos", headers=H, data={
    "model": "nvidia/Cosmos3-Nano",
    "prompt": "A small warehouse robot moves a blue box across a clean floor.",
    "negative_prompt": "blurry, distorted, low quality",
    "size": "1280x720", "num_frames": 81, "fps": 24,
    "num_inference_steps": 35, "guidance_scale": 6.0, "flow_shift": 10.0, "seed": 42,
    "extra_params": '{"use_resolution_template":false,"use_duration_template":false,"guardrails":false}',
}, timeout=60).json()

while (s := requests.get(f"{BASE}/v1/videos/{job['id']}", headers=H, timeout=30).json())["status"] not in ("completed", "failed"):
    print(s["status"], s.get("progress")); time.sleep(10)

if s["status"] == "completed":
    open("cosmos3_t2v.mp4", "wb").write(requests.get(f"{BASE}/v1/videos/{job['id']}/content", headers=H, timeout=120).content)
```

### Observed results

Nano on one H100, this template's command, HTTPS FQDN:

| Request | Result |
| --- | --- |
| Text-to-image 1024², 50 steps | 3.2 s, 3.1 MB PNG |
| Text-to-video 720p, 189 frames, **sync** | `504 Gateway Time-out` after 60 s (render continues server-side) — use async |
| Text-to-video 720p, 81 frames, async | completed; 3.4 MB h264, 3.4 s clip (render ≈ 60 s when the GPU is idle) |
| Image-to-video 720p, 81 frames, async (uploaded frame) | completed in 63 s; 7.4 MB |
| Text-to-video with sound 720p, 189 frames, async | completed in 207 s; 11 MB, h264 + AAC track, 7.9 s |

> ⚠️ **Preemptible.** When Compute reclaims the VM, the endpoint moves to **STOPPED** and does
> not restart by itself — `nebius ai endpoint start <endpoint-id>` (or **Start** in the console)
> brings it back in ~10 minutes; queued jobs are lost. Untick *Preemptible* for production.

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

```bash
nebius ai endpoint create \
  --name cosmos3-nano-generator \
  --image vllm/vllm-omni:cosmos3 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 32Gi \
  --disk-size 500Gi \
  --auth token \
  --container-command vllm \
  --args "serve nvidia/Cosmos3-Nano --omni --model-class-name Cosmos3OmniDiffusersPipeline --no-guardrails --host 0.0.0.0 --port 8000 --init-timeout 1800"
```

`--auth token` without `--token` makes Nebius generate a bearer token and print it **once**
(`Token: …`); pass `--token <value>` to set your own, or `--token-secret <secret-version-id>` for CI.
The `cosmos3` image tag is NVIDIA's Cosmos 3 build of vLLM-Omni (`0.25.0`); it is a moving
tag, so pin by digest for reproducible deployments.

### Other model sizes

| Variant | Change | Platform / preset | Notes |
| --- | --- | --- | --- |
| **Cosmos3-Edge** (4B) | `nvidia/Cosmos3-Edge` | `gpu-h100-sxm` / `1gpu-16vcpu-200gb` or `gpu-l40s-a` / `1gpu-16vcpu-64gb` | No sound generation on Edge. Not validated in this template. |
| **Cosmos3-Super** (64B) | `nvidia/Cosmos3-Super`, add `--tensor-parallel-size 8 --enable-layerwise-offload` | `gpu-h200-sxm` / `8gpu-128vcpu-1600gb` | Highest quality; Nebius offers 1- and 8-GPU presets. Not validated in this template. |

<!-- /factory:cli -->

## Troubleshooting

- **`504 Gateway Time-out` on `/v1/videos/sync`** — the gateway limit is 60 s; the render still completes on the GPU. Use `POST /v1/videos` + polling, or keep sync clips very short.
- **Console shows RUNNING but requests fail / `502`** — weights are still downloading or the pipeline is warming up. Poll `/v1/models`; first boot is ~10 minutes.
- **Server exits during startup mentioning `Cosmos-1.0-Guardrail` / 401** — guardrails are enabled but the gated repo is not accessible. Keep `--no-guardrails`, or add `HF_TOKEN` with granted access.
- **Endpoint is STOPPED without you stopping it** — the preemptible VM was reclaimed. `nebius ai endpoint start <id>`, or recreate without `--preemptible`.
- **Job `failed`** — read `GET /v1/videos/<id>` for the error; common causes are an unreadable `input_reference` and unsupported `size`/`num_frames` combinations (use 1280x720 or 832x480; frames as `8n+1`).
- **Want captions, grounding or reasoning about a video?** — that is the Reasoner surface; use the [Cosmos 3 Reasoner](../endpoint-cosmos3-reasoner/README.md) template.
