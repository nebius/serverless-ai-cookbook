---
title: Personal-Subject FLUX.2 LoRA Avatar - Train, Serve, Connect to Claude and ChatGPT
category: training
type: workflow
runtime: gpu
frameworks:
  - pytorch
  - diffusers
  - ai-toolkit
keywords:
  - finetuning
  - lora
  - flux
  - image-generation
  - object-storage
  - endpoint
  - mcp
  - chatgpt-actions
difficulty: advanced
---

# Personal-Subject FLUX.2 LoRA Avatar on Nebius Serverless

Fine-tune a FLUX.2-dev LoRA on 30-60 photos of yourself with a Serverless AI
Job, serve it behind a token-authenticated Serverless AI Endpoint, and let
Claude (via MCP) or ChatGPT (via a Custom GPT Action) generate photorealistic
images of you on demand - with the GPU billing nothing while you are not
using it.

This example distills a real, validated end-to-end run; the operational
defaults (preemptible scheduling, resume-after-preemption, timeout budgets,
S3-FUSE staging patterns, identity gating, cold-start expectations) all come
from that run.

```text
 your photos                Serverless AI Job                Serverless AI Endpoint
 ┌───────────┐   upload    ┌─────────────────────┐  adapter  ┌──────────────────────┐
 │ 30-60     │ ──────────> │ ai-toolkit           │ ────────> │ FLUX.2-dev           │
 │ solo shots│  + captions │ FLUX.2-dev LoRA      │  (S3)     │ + your LoRA          │
 └───────────┘  (S3)       │ ~1-1.5 h on 1 GPU    │           │ /generate (bearer)   │
       │                   └─────────────────────┘           └──────────┬───────────┘
       │ holdout refs             │ checkpoints                          │ HTTPS
       v                          v                                      v
 ┌───────────┐  ArcFace    ┌─────────────────────┐              ┌───────────────────┐
 │ refs/     │ <────────── │ score_identity.py    │              │ Claude (MCP)      │
 │ (never    │  gate, not  │ pick the best step,  │              │ ChatGPT (Action)  │
 │  trained) │  eyeballing │ not the last one     │              └───────────────────┘
 └───────────┘             └─────────────────────┘
```

## What this example does

- prepares a training dataset from your own photos (face-checked, resized,
  captioned with a rare trigger token, with a held-out reference set)
- fine-tunes `black-forest-labs/FLUX.2-dev` with LoRA in a Serverless AI Job
  using the public [ostris/ai-toolkit](https://github.com/ostris/ai-toolkit)
  runtime image - no custom training image to build
- optionally scores every checkpoint against the held-out references with an
  ArcFace identity gate instead of eyeballing sample grids
- serves base model + adapter through a minimal FastAPI app
  (diffusers `Flux2Pipeline` + PEFT `load_lora_weights`) on a Serverless AI
  Endpoint with fail-closed bearer-token auth
- connects the endpoint to Claude via an MCP server (including endpoint
  start/stop tools) and to ChatGPT via a Custom GPT Action

## Why this is useful

- **The full arc in one place**: dataset -> training -> quality gate ->
  serving -> LLM integration, using only Serverless Jobs/Endpoints and
  Object Storage - no clusters.
- **On-demand economics**: endpoints bill per second; the runbook here keeps
  the endpoint stopped when idle and lets your LLM start it when needed.
- **Code outside the image**: training config and entry script live in the
  bucket, so you iterate on hyperparameters without building any image.
- **Hard-won operational defaults**: every non-obvious flag in `train.sh`
  and `serve.sh` exists because the naive alternative failed in practice
  (see Troubleshooting).

## Files in this folder

```text
training/flux-subject-lora-avatar/
├── README.md
├── prepare_dataset.py      # photos -> captioned pairs + holdout refs
├── train_config.yaml       # ai-toolkit recipe (validated defaults)
├── train.sh                # launch the training job
├── score_identity.py       # optional ArcFace identity gate
├── serving/
│   ├── server.py           # FastAPI + Flux2Pipeline + LoRA, bearer auth
│   ├── Dockerfile          # serving image
│   └── serve.sh            # create the endpoint
├── mcp/
│   └── server.py           # MCP server for Claude & other MCP clients
└── chatgpt/
    ├── openapi.yaml        # Custom GPT Action schema
    └── gpt-instructions.md # Custom GPT system instructions
```

## Requirements

- Nebius CLI installed and authenticated; `jq`; Docker; AWS CLI (for Object
  Storage); Python 3.10+ locally
- quota for one GPU Serverless AI Job, one GPU Serverless AI Endpoint, and
  Object Storage
- a Hugging Face account token: **FLUX.2-dev is a gated model with its own
  license**. Visit the
  [model page](https://huggingface.co/black-forest-labs/FLUX.2-dev), accept
  the license, and read its terms - they govern what you may do with the
  model and its outputs. Export the token as `HF_TOKEN`.

> **Likeness and consent.** Only train on photos of **your own** likeness,
> or with the explicit, informed consent of the person depicted. A
> subject-LoRA endpoint can produce convincing photorealistic images of a
> real person: keep it private (`--public` never set here), keep the bearer
> token secret, and never use it to depict anyone deceptively.

## Runtime / compute

- training image: `docker.io/ostris/aitoolkit:latest` (public; pin a digest
  for reproducibility; the ai-toolkit project is MIT-licensed)
- serving image: built from `serving/Dockerfile`
  (`pytorch/pytorch:2.9.1-cuda12.8-cudnn9-runtime` + `diffusers>=0.36`)
- example platform/preset: `gpu-h200-sxm` / `1gpu-16vcpu-200gb` (any modern
  single datacenter GPU with >= 80 GB VRAM works for this quantized recipe)
- observed timings on one high-end GPU: **~3 s/step**, so the 1200-step
  recipe is **~1-1.5 h** including the ~90 GB model fetch; endpoint cold
  start **~15-30 min**; warm generation **~12-45 s** per 1024 px image

## 1. Set variables and create the bucket

```bash
export PARENT_ID=<PROJECT_ID>                # project-...
export NB_REGION_ID=<REGION>                 # e.g. eu-north1, us-central1
export BUCKET_NAME=<YOUR_BUCKET>             # globally unique
export HF_TOKEN=<your-hf-token>              # accepted the FLUX.2-dev license
export AWS_ACCESS_KEY_ID=<object-storage-access-key>
export AWS_SECRET_ACCESS_KEY=<object-storage-secret>

nebius storage bucket create --name "$BUCKET_NAME" --parent-id "$PARENT_ID"
```

If you need Object Storage credentials, see
[Working with Object Storage using the AWS CLI](https://docs.nebius.com/object-storage/interfaces/aws-cli).

## 2. Prepare the dataset from your photos

What makes good data (this matters more than any hyperparameter):

- **30-60 solo shots** of you, and only you, per photo
- **varied** everything: locations, lighting, clothing, angles, expressions,
  distance (close-ups and full-body) - variety is what lets the model
  separate *you* from *the scene*
- sharp faces, short side ideally >= 1024 px; avoid heavy filters,
  sunglasses in most shots, and group photos

```bash
pip install pillow insightface onnxruntime opencv-python-headless

python3 prepare_dataset.py \
  --input ~/my-photos \
  --output ./prepared \
  --trigger TOK4ME \
  --class-word person \
  --holdout 6
```

The script verifies each photo contains exactly one face, resizes, writes
captions like `TOK4ME person, photo` (a `.txt` sidecar next to a source
photo overrides the default - hand-written varied captions train better),
and reserves 6 photos as **holdout references** that are never trained on.
The trigger token is a rare string the base model has no prior for; keep the
default `TOK4ME` or pick your own and change it everywhere at once
(captions, `train_config.yaml`, sample prompts, serving env).

Upload:

```bash
aws --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp --recursive ./prepared/dataset "s3://$BUCKET_NAME/flux-avatar/dataset/"
aws --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp --recursive ./prepared/refs "s3://$BUCKET_NAME/flux-avatar/refs/"
```

## 3. Train

```bash
chmod +x train.sh
./train.sh
```

The script renders `train_config.yaml` (rank-32 LoRA, lr 5e-5, EMA,
qfloat8-quantized transformer, 1200 steps - a validated recipe), uploads the
config plus an entry script to the bucket, and creates the job with defaults
that earned their place:

- `--preemptible` + `--restart-policy on-failure`: preemptible jobs schedule
  in ~90 s even when the on-demand pool is tight; the entry script preseeds
  earlier checkpoints from the bucket so a preempted run **resumes** instead
  of starting over
- `--timeout 16h`: the timeout is wall clock **including** preemption
  restarts and the model fetch - budget several times the pure training time
- `--disk-size 400Gi` and `TMPDIR`/`HF_HOME` redirected into `/workspace`:
  FLUX.2 model reconstruction is disk-hungry and overflows the default tmp
- the dataset is staged per-file to local disk (`cat` + size verify): the
  latent cache is written into the dataset folder, and training directly
  from the S3-FUSE mount is both slow and fragile
- checkpoints sync to the bucket every 5 minutes, so even a timed-out job
  leaves its artifacts behind

Monitor (`nebius ai logs <job-id> --follow`); expect ~3 s/step after the
model fetch. Checkpoints and sample grids land under
`s3://$BUCKET_NAME/flux-avatar/output/<run>/<run>/`.

To log to Weights & Biases, set `use_wandb: true` in the config and export
`WANDB_API_KEY` (and optionally `WANDB_ENTITY`) before `./train.sh`.

## 4. Pick the best checkpoint - do not eyeball

The best checkpoint is frequently **not** the final one, and faces that look
fine in a sample grid routinely fail a face-embedding check. Score each
checkpoint's sample images against your holdout references:

```bash
aws --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp --recursive "s3://$BUCKET_NAME/flux-avatar/output/<run>/" ./output/

pip install insightface onnxruntime opencv-python-headless numpy
python3 score_identity.py --refs ./prepared/refs \
  --candidates "./output/<run>/samples/*_000001200_*.jpg" --out step1200.json
# repeat for each saved step (1000, 800, ...) and compare mean/min/pass-rate
```

Because the references were held out of training, similarity against them is
an honest identity signal. Pick the checkpoint with the best pass-rate/mean,
then copy it to a stable serving location:

```bash
aws --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp "s3://$BUCKET_NAME/flux-avatar/output/<run>/<run>/<run>_000001200.safetensors" \
        "s3://$BUCKET_NAME/flux-avatar/serving/lora.safetensors"
```

## 5. Build and push the serving image

```bash
cd serving
docker build -t <YOUR_REGISTRY>/flux-avatar-serving:v1 .
docker push <YOUR_REGISTRY>/flux-avatar-serving:v1
```

Push to an **in-region Nebius Container Registry**
(`cr.<region>.nebius.cloud/<registry-id>/...`) - in-region pulls take
seconds to a few minutes; cross-region first pulls can add many minutes to
every cold start.

## 6. Create the endpoint

```bash
export SERVING_IMAGE=<YOUR_REGISTRY>/flux-avatar-serving:v1
chmod +x serving/serve.sh
./serving/serve.sh
```

This creates a **private** (`--public` never set), token-authenticated
endpoint with the bucket mounted read-only for the adapter. One bearer token
(written to `./endpoint.token`, chmod 600) passes both auth layers: the
platform `--auth token` proxy and the fail-closed in-container check.
Exporting `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` first enables
`response_format: "url"` (required for ChatGPT later).

Wait for `state=RUNNING`, then poll `/healthz` until `ready: true`
(cold start ~15-30 min: image pull + ~90 GB model download + load). The
script prints the smoke-test commands, including the auth check - an
unauthenticated `/generate` must return **401**.

The endpoint's HTTPS URL:

```bash
EP_URL=$(nebius ai endpoint get <endpoint-id> --format json \
  | jq -r '.status.public_endpoints[0]')
```

> **The hostname is not stable.** Every stop/start cycle mints a **new**
> HTTPS hostname; the old one starts returning 404. Always re-resolve the
> URL after starting the endpoint. (There is currently no custom-domain
> option for Serverless Endpoints.)

**Cost discipline:** a running GPU endpoint bills per second around the
clock. Stop it whenever you are done; it keeps its ID, token, and adapter:

```bash
nebius ai endpoint stop <endpoint-id>     # idle: bills nothing
nebius ai endpoint start <endpoint-id>    # ~15-30 min back to ready
```

## 7. Connect Claude via MCP

`mcp/server.py` wraps the endpoint as MCP tools - `avatar_endpoint_status`,
`avatar_endpoint_start`, `avatar_endpoint_stop`, and
`generate_avatar_image` - so Claude can manage the on-demand lifecycle
itself: check status, start the endpoint, poll until ready, generate, and
stop it when you are done. It resolves the endpoint URL at **call time** via
the CLI, so restarts (and their new hostnames) just work.

```bash
python3 -m venv mcp/venv && mcp/venv/bin/pip install mcp
```

Claude Code:

```bash
claude mcp add flux-avatar \
  -e ENDPOINT_ID=<endpoint-id> \
  -e AUTH_TOKEN_FILE=/absolute/path/to/endpoint.token \
  -- /absolute/path/to/mcp/venv/bin/python /absolute/path/to/mcp/server.py
```

Claude Desktop (`claude_desktop_config.json`) and other MCP clients use the
same shape:

```json
{
  "mcpServers": {
    "flux-avatar": {
      "command": "/absolute/path/to/mcp/venv/bin/python",
      "args": ["/absolute/path/to/mcp/server.py"],
      "env": {
        "ENDPOINT_ID": "<endpoint-id>",
        "AUTH_TOKEN_FILE": "/absolute/path/to/endpoint.token",
        "TRIGGER_WORD": "TOK4ME",
        "TRIGGER_CLASS": "person"
      }
    }
  }
}
```

The machine running the MCP server needs the authenticated `nebius` CLI (for
start/stop/status and URL resolution) and read access to the token file.
Then simply ask Claude: *"generate a picture of me hiking at sunrise -
start the endpoint if it's stopped, and stop it when we're done."*

## 8. Connect ChatGPT via a Custom GPT Action

1. ChatGPT -> Explore GPTs -> **Create a GPT** -> Configure.
2. Paste `chatgpt/gpt-instructions.md` (below the divider) into
   **Instructions**.
3. **Actions -> Create new action**: paste `chatgpt/openapi.yaml` into the
   schema field, replacing the server URL with your endpoint's current one
   (`jq -r '.status.public_endpoints[0]'` as above).
4. Authentication: **API Key**, Auth Type **Bearer**, paste the token from
   `endpoint.token`.
5. Privacy: keep the GPT **"Only me"**. Anyone with access to the GPT
   effectively holds your endpoint token - and your likeness.

Why `response_format: "url"`: ChatGPT truncates Action responses at roughly
**100 KB**. A 1024 px PNG is a couple of megabytes, so an inline base64
response can never arrive. In `url` mode the endpoint uploads the PNG to
Object Storage and returns a presigned URL (expires ~1 h) that the GPT
renders inline with markdown.

Two operational caveats ChatGPT cannot work around itself:

- it cannot start/stop your endpoint - do that from your machine (or ask
  Claude via MCP) before and after a session
- after every endpoint restart the Action's server URL is stale (the old
  hostname 404s) - re-paste the new URL into the GPT's schema

## Expected output

- the training job reaches `COMPLETED` with LoRA checkpoints + sample grids
  in the bucket
- `score_identity.py` shows a clear winner checkpoint (pass-rate >= 0.8
  against holdout refs is a strong solo adapter)
- the endpoint reaches `RUNNING`, `/healthz` reports `ready: true`,
  unauthenticated requests get **401**, authenticated `/generate` returns an
  image in ~12-45 s
- Claude and ChatGPT render images of you from plain-language requests

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Job stuck / fails with `NotEnoughResources` | The on-demand GPU pool is tight. For **jobs**: use `--preemptible` (schedules in ~90 s, default here). For **endpoints** (which cannot be preemptible): start the endpoint **before** launching batch jobs that compete for the same pool, or free a slot first; a starved endpoint create times out after ~25 min in `ERROR` - delete and recreate it. |
| Job dies with `TimeoutExceeded` mid-training | `--timeout` counts wall clock **including** preemption restarts and the ~90 GB model fetch. Budget generously (>= 12 h for a ~1.5 h train); the periodic checkpoint sync means a relaunch resumes from the last saved step. |
| Job crash-loops with `Stale file handle` / `cp` errors on the S3 mount | Never run long-lived scripts directly from the S3-FUSE mount and never train against it: copy scripts and dataset to local disk first (the entry script in `train.sh` does both), and write outputs locally with periodic sync back. |
| ChatGPT Action "fails" although the endpoint works | Action responses are truncated at ~100 KB - use `response_format: "url"`, never base64, for ChatGPT. If the Action gets 404s, the endpoint was restarted and the schema's server URL points at the old hostname. |
| `/healthz` returns 404 | Stale hostname (endpoint was restarted - re-resolve the URL) or the container is not listening yet (cold start). Only `ready: true` on the **current** URL means the endpoint is up. |
| `nebius ai job create` / `endpoint start` seems to hang | `create` blocks until the workload is scheduled and `start` several minutes - this is normal; poll `... get <id>` from another shell. |
| "multiple subnets found" on create | Projects with several subnets require an explicit `--subnet-id`; the scripts pick the first subnet - override `SUBNET_ID` if needed. |
| Disk-full during model load | FLUX.2 reconstruction needs a lot of scratch space: keep `--disk-size` >= 400Gi for training / 300Gi for serving and the `TMPDIR`/`HF_HOME` redirects. |
| Weak likeness despite low loss | Data problem first: more variety, sharper faces, exactly one person per shot. Then let `score_identity.py` pick the step - the last checkpoint is often overcooked. Never describe the face in prompts; the trigger token carries identity. |

## Security notes

- The endpoint is never `--public`; its HTTPS URL is token-gated by the
  platform proxy, and the container refuses requests without the bearer
  token (fail-closed) as a second layer.
- `--env` values are visible to project members via `nebius ai job/endpoint
  get`. In shared projects move `HF_TOKEN`, `API_TOKEN`, and cloud
  credentials into MysteryBox secrets (`--env-secret`, `--token-secret`).
- Presigned image URLs are unguessable but fetchable by anyone holding the
  link until expiry - do not post them publicly.
- Treat the bearer token like a password to your own face; rotate it
  (recreate the endpoint) if it may have leaked.

## Cleanup

```bash
nebius ai job delete <job-id>            # after collecting artifacts
nebius ai endpoint delete <endpoint-id>  # when you no longer need serving
# remove bucket contents + bucket if you are done with the project
```
