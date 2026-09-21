# Cosmos 3 Reasoner (Nano)

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.29.0&amp;command=vllm%20serve%20nvidia%2FCosmos3-Nano%20--tensor-parallel-size%201%20--mm-encoder-tp-mode%20data%20--async-scheduling%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Cosmos3-Nano is NVIDIA's 16B omnimodal world model for Physical AI; this template serves its **Reasoner** surface — video and image understanding for robotics and autonomous driving — OpenAI-compatibly via vLLM on preemptible H100.

**License:** [OpenMDW-1.1](https://openmdw.ai/license/1-1/) · **Source:** [Hugging Face](https://huggingface.co/nvidia/Cosmos3-Nano) · [NVIDIA Cosmos](https://github.com/nvidia/cosmos)

<!-- /factory:intro -->

## What you get

An OpenAI-compatible `POST /v1/chat/completions` endpoint that takes **images and
videos** (Qwen3-VL message conventions) and returns text: detailed captions, event
timelines with timestamps, next-action prediction for robots and vehicles, physical
common-sense judgments, 2D bounding boxes, and plausibility labels. Reasoning is
switched on per request with a `<think>` instruction in the prompt.

Cosmos 3 is one checkpoint with two runtime surfaces. Plain vLLM loads **only the
Reasoner (VLM) weights** — about 17 GiB for Nano, leaving ~51 GiB of KV cache on an
H100 for a 262k-token context. Video, image, sound and action **generation** is the
Generator surface and needs vLLM-Omni; it is not served by this template.

## Test request

Copy the endpoint's public URL from the console (**Public endpoints**) into `BASE_URL`.
Prefer the managed HTTPS FQDN (`https://port8000-<id>.tunnel.applications.<region>.nebius.cloud`);
the raw `IP:port` form also works while it is offered.

> **Auth.** The 1-click link **enables token authentication** — the create form opens with
> Token auth selected and you generate the token there (it is never put in the URL). Every
> call needs `Authorization: Bearer <token>`; set `TOKEN` below and the snippets add the
> header. Without it the endpoint answers `401`. For a quick public test, set Authentication
> to None (or drop `auth=true` from the link) and leave `AUTH` empty. See
> [How to call an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-call-an-endpoint).

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.eu-north1.nebius.cloud'
export TOKEN='<endpoint-auth-token>'               # from the console / CLI output
AUTH=(-H "Authorization: Bearer $TOKEN")           # AUTH=() if the endpoint has no auth
```

**First boot:** the 32.6 GiB repository is pulled from the Hub and vLLM compiles CUDA
graphs — expect ~15 minutes from create to first answer, during which the console
already shows RUNNING. Poll until the API answers:

```bash
until curl -sf "${AUTH[@]}" "$BASE_URL/v1/models" >/dev/null; do echo "waiting…"; sleep 15; done
```

The examples below use NVIDIA's public sample media from the
[Cosmos cookbooks](https://github.com/nvidia/cosmos/tree/main/cookbooks/cosmos3/reasoner/assets),
so you can test without uploading anything. Sampling values follow NVIDIA's
[prompt guide](https://github.com/nvidia/cosmos/blob/main/cookbooks/cosmos3/reasoner/reasoner_prompt_guide.md):
`temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5` without reasoning;
`temperature 0.6, top_p 0.95, presence_penalty 0` with reasoning.

```bash
export ASSETS='https://raw.githubusercontent.com/nvidia/cosmos/main/cookbooks/cosmos3/reasoner/assets'
```

### Image caption

```bash
curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano", "max_tokens": 512, "seed": 0,
  "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
  "messages": [{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "'"$ASSETS"'/robot_153.jpg"}},
    {"type": "text", "text": "Caption the image in detail."}
  ]}]}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

### Video caption

Videos use `video_url`. Frame sampling is set per request through `media_io_kwargs`
(`fps: 4` is NVIDIA's default; `num_frames: -1` lifts the frame cap). Always put the
media before the text in `content`.

```bash
curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano", "max_tokens": 512, "seed": 0,
  "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
  "media_io_kwargs": {"video": {"num_frames": -1, "fps": 4}},
  "messages": [{"role": "user", "content": [
    {"type": "video_url", "video_url": {"url": "'"$ASSETS"'/video_caption.mp4"}},
    {"type": "text", "text": "Describe the video in detail."}
  ]}]}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

Observed answer (Nano, 1.2 s):

```text
Two robot arms are positioned on either side of a white table. On the left, Robot Arm 1
is stationary near an open cardboard box filled with air column wraps. On the right,
Robot Arm 2 picks up a white object from the table next to additional air column wraps
and places it into the cardboard box.
```

### Temporal localization (event timeline as JSON)

```bash
curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano", "max_tokens": 1024, "seed": 0,
  "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
  "media_io_kwargs": {"video": {"num_frames": -1, "fps": 4}},
  "messages": [{"role": "user", "content": [
    {"type": "video_url", "video_url": {"url": "'"$ASSETS"'/temporal_localization_2.mp4"}},
    {"type": "text", "text": "Describe the notable events in the provided video. Provide the result in json format with '"'"'mm:ss.ff'"'"' format for time depiction for each event. Use keywords '"'"'start'"'"', '"'"'end'"'"' and '"'"'caption'"'"' in the json output."}
  ]}]}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

Observed answer (Nano, 4.1 s for a 23-second clip, ~11.5k prompt tokens):

```json
[
  {"start": "00:06.20", "end": "00:12.80", "caption": "Two men emerge from a room on the left, each carrying cardboard boxes, and walk down the hallway toward the end where another person stands."},
  {"start": "00:12.80", "end": "00:23.40", "caption": "A third man, dressed in a white sweater, exits the same room holding a box and follows behind the first two men as they continue walking down the hallway."}
]
```

### Embodied reasoning (next action, with `<think>`)

Append NVIDIA's reasoning instruction to turn chain-of-thought on, and switch to the
reasoning sampling values.

```bash
curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano", "max_tokens": 2048, "seed": 0,
  "temperature": 0.6, "top_p": 0.95, "top_k": 20, "presence_penalty": 0.0,
  "media_io_kwargs": {"video": {"num_frames": -1, "fps": 4}},
  "messages": [{"role": "user", "content": [
    {"type": "video_url", "video_url": {"url": "'"$ASSETS"'/robotics_next_action.mp4"}},
    {"type": "text", "text": "What can be the next immediate action?\nAnswer the question using the following format:\n<think>\nYour reasoning.\n</think>\nWrite your final answer immediately after the </think> tag."}
  ]}]}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

Observed answer ends with:

```text
</think>
Robot Arm 2 places the USB to serial converter into the cardboard box on the left side of the table
```

### 2D grounding

Boxes come back in normalized `0–1000` coordinates, `[x1, y1, x2, y2]`, origin top-left.

```bash
curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano", "max_tokens": 256, "seed": 0,
  "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
  "messages": [{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "'"$ASSETS"'/grounding_2d.png"}},
    {"type": "text", "text": "Locate the accurate bounding box of the load as a whole. Return a json."}
  ]}]}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

Observed answer: `[{"bbox_2d": [218, 145, 476, 707], "label": "load"}]`

### Physical plausibility

```bash
curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" -H "Content-Type: application/json" -d '{
  "model": "nvidia/Cosmos3-Nano", "max_tokens": 64, "seed": 0,
  "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
  "media_io_kwargs": {"video": {"num_frames": -1, "fps": 4}},
  "messages": [{"role": "user", "content": [
    {"type": "video_url", "video_url": {"url": "'"$ASSETS"'/physical_plausibility.mp4"}},
    {"type": "text", "text": "Is this video physically plausible/possible according to your understanding of e.g. object permanence, shape constancy (objects maintain shape over time), continuous trajectories of objects? Assume it is the normal laws of physics.\nYour answer should be based on the events in the video and ignore the quality of the simulation engine. The rising wall is part of the experiment setup and should not be judged for plausibility.\n(A) Possible\n(B) Impossible"}
  ]}]}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

Observed answer: `A`

### Python (OpenAI SDK)

```python
import os
from openai import OpenAI

client = OpenAI(base_url=f"{os.environ['BASE_URL']}/v1", api_key=os.environ.get("TOKEN", "EMPTY"))
ASSETS = "https://raw.githubusercontent.com/nvidia/cosmos/main/cookbooks/cosmos3/reasoner/assets"

r = client.chat.completions.create(
    model="nvidia/Cosmos3-Nano",
    messages=[{"role": "user", "content": [
        {"type": "video_url", "video_url": {"url": f"{ASSETS}/situation_understanding.mp4"}},
        {"type": "text", "text": "What is the person doing with the skillet? What will the person likely do next in this situation?"},
    ]}],
    max_tokens=256, seed=0, temperature=0.7, top_p=0.8, presence_penalty=1.5,
    extra_body={"top_k": 20, "media_io_kwargs": {"video": {"num_frames": -1, "fps": 4}}},
)
print(r.choices[0].message.content)
```

More prompts (describe-anything, action trajectories, driving scenes, robot task
planning) are in NVIDIA's
[Reasoner notebook](https://github.com/nvidia/cosmos/blob/main/cookbooks/cosmos3/reasoner/run_with_vllm.ipynb);
every one of them runs unchanged against this endpoint by pointing `base_url` at it.

> ⚠️ **Preemptible.** This template runs on a preemptible VM. When Compute reclaims it,
> the endpoint moves to **STOPPED** and does not restart by itself — start it again with
> `nebius ai endpoint start <endpoint-id>` (or **Start** in the console; ~10 minutes to
> ready). Untick *Preemptible* for production.

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

```bash
nebius ai endpoint create \
  --name cosmos3-nano-reasoner \
  --image vllm/vllm-openai:v0.29.0 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --auth token \
  --container-command vllm \
  --args "serve nvidia/Cosmos3-Nano --tensor-parallel-size 1 --mm-encoder-tp-mode data --async-scheduling --host 0.0.0.0 --port 8000"
```

`--auth token` without `--token` makes Nebius generate a bearer token and print it **once**
(`Token: …`) — copy it into `TOKEN`; it is truncated in `endpoint get` and unrecoverable.
Pass `--token <value>` to set your own, or `--token-secret <secret-version-id>` for CI.

### Other platforms

Validated on **RTX Pro 6000 Blackwell** (96 GB) in `uk-south2` with the same command:
`--platform gpu-rtx6000-a --preset 1gpu-24vcpu-218gb` (plus `--parent-id` of a uk-south2
project). 17 GiB of weights, 67 GiB of KV cache, ready ~14 min after create; request latencies
within ~1.5× of the H100 figures above. Good fit for preemptible capacity.

### Other model sizes

| Variant | Change | Platform / preset | Notes |
| --- | --- | --- | --- |
| **Cosmos3-Edge** (4B) | `nvidia/Cosmos3-Edge` | `gpu-h100-sxm` / `1gpu-16vcpu-200gb` (validated), `gpu-rtx6000-a` / `1gpu-24vcpu-218gb` (uk-south2), or `gpu-l40s-a` / `1gpu-16vcpu-64gb` | Same flags, validated with this template's requests on H100. 4.7 GiB of weights, 131k context, ready in ~7 min. Edge **reasons by default** (emits `<think>…</think>` even without the instruction) and spends ~2× Nano's prompt tokens per video — give it `max_tokens ≥ 512` or ask for "only the letter/JSON" when you want a short answer. |
| **Cosmos3-Super** (64B) | `nvidia/Cosmos3-Super` and `--tensor-parallel-size 8` | `gpu-h200-sxm` / `8gpu-128vcpu-1600gb` | Highest quality; Nebius offers 1- and 8-GPU presets, so Super runs TP=8. Not validated in this template. |

<!-- /factory:cli -->

## Troubleshooting

- **Console shows RUNNING but requests fail / `502`** — weights (32.6 GiB) are still downloading or vLLM is compiling. Poll `/v1/models`; first boot is ~15 minutes.
- **Endpoint is STOPPED without you stopping it** — the preemptible VM was reclaimed. `nebius ai endpoint start <id>`, or recreate without `--preemptible`.
- **Video request rejected while images work** — use `video_url` (not `image_url`), put the media block before the text block, and pass `media_io_kwargs` at the top level of the request body (the OpenAI SDK needs it in `extra_body`).
- **Long video costs many tokens** — `num_frames: -1` samples the whole clip at `fps`; lower `fps` (e.g. `2`) or set an explicit `num_frames` for long videos. Context is 262k tokens.
- **Want generation (video/image/action)?** — that is the Generator surface; serve it with vLLM-Omni (`vllm/vllm-omni:cosmos3`), not this template.
- **Slow first pull** — add optional env `HF_TOKEN` in the console for authenticated Hub downloads; keep the 500 Gi disk.
