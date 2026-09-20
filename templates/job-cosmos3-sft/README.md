# Cosmos 3 Post-Training (SFT)

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/job/create?image=nvidia%2Fcuda%3A13.0.2-cudnn-devel-ubuntu24.04&amp;command=bash%20-c%20%22apt-get%20update%20-qq%20%26%26%20apt-get%20install%20-y%20-qq%20curl%20ca-certificates%20%3E%2Fdev%2Fnull%20%26%26%20curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftemplates%2Fjob-cosmos3-sft%2Fsrc%2Frun.sh%20-o%20%2Ftmp%2Frun.sh%20%26%26%20bash%20%2Ftmp%2Frun.sh%22&amp;platform=gpu-h100-sxm&amp;preset=8gpu-128vcpu-1600gb&amp;volume=%2Fdata&amp;diskSize=500GiB&amp;preemptible=true&amp;env=MAX_ITER%3D20"><img src="../assets/create-job.svg" alt="Create Job" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Fine-tunes the Cosmos3-Nano video generator on captioned robot videos with NVIDIA's Cosmos Framework SFT recipe on an 8×H100 node, exports the result as a Diffusers pipeline into your bucket — ready to serve with the Generator endpoint template.

**License:** [OpenMDW-1.1](https://openmdw.ai/license/1-1/) · **Source:** [Cosmos Framework](https://github.com/NVIDIA/cosmos-framework) · [NVIDIA Cosmos recipes](https://github.com/nvidia/cosmos/tree/main/cookbooks/cosmos3/generator/audiovisual/finetune)

<!-- /factory:intro -->

## What you get

A Serverless **Job** that runs NVIDIA's `vision_sft_nano` recipe end to end — no image to
build, nothing to install locally:

1. Installs Cosmos Framework (pinned release) on the public CUDA 13 image.
2. Downloads the training data — by default NVIDIA's
   [BridgeData2 subset](https://huggingface.co/datasets/nvidia/BridgeData2-Subset-Synthetic-Captions)
   (1,324 robot-manipulation clips with structured captions, not gated) — and the Wan2.2 VAE.
3. Converts the `nvidia/Cosmos3-Nano` base checkpoint and trains with FSDP on all 8 GPUs
   (`MAX_ITER` iterations; NVIDIA's recipe is 500).
4. Exports the last checkpoint to Hugging Face safetensors and converts it to a **Diffusers**
   pipeline.
5. Copies everything to the bucket mounted at `/data`, then exits:

```text
/data/cosmos3-sft/<run-id>/
  diffusers/        serve this: vllm serve /path/diffusers --omni --model-class-name Cosmos3OmniDiffusersPipeline
  model/            Hugging Face safetensors export
  config.yaml       resolved training config
  sft.toml          the recipe as run (with your MAX_ITER / SAVE_ITER)
```

**Serve the result** with the [Cosmos 3 Generator](../endpoint-cosmos3-generator/README.md)
template — validated: mount the same bucket read-only and point `vllm serve` at the folder.

```bash
nebius ai endpoint create \
  --name cosmos3-finetuned-generator \
  --image vllm/vllm-omni:cosmos3 \
  --public --auth token \
  --platform gpu-h200-sxm --preset 1gpu-16vcpu-200gb \
  --container-port 8000 --shm-size 32Gi --disk-size 500Gi \
  --volume "$BUCKET:/data:ro" \
  --container-command vllm \
  --args "serve /data/cosmos3-sft/<run-id>/diffusers --omni --model-class-name Cosmos3OmniDiffusersPipeline --no-guardrails --host 0.0.0.0 --port 8000 --init-timeout 1800"
```

The served model id is the path (`/data/cosmos3-sft/<run-id>/diffusers`, read it from
`/v1/models`); requests are otherwise identical to the Generator template's. Observed: ready
~6 min after create (30 GB read from the mount), text-to-image 4 s, an 81-frame 720p clip 66 s
on one H200 — and the outputs carry the training domain (BridgeData's toy-kitchen scenes and
gripper) even after the 20-iteration smoke run.

## How to run it

1. **Click Create Job.** Pick the **bucket** to mount at `/data` and raise **shared memory**
   to 128 GiB if the form offers it (the link cannot preset it; eight `torchrun` ranks need
   more than the default). Everything else is prefilled; the link sets `MAX_ITER=20`, a
   **smoke run** that proves the pipeline in about an hour. For NVIDIA's full recipe change
   the env to `MAX_ITER=500`.
2. **Watch** with `nebius ai job logs <aijob-id> --follow`. The launcher logs six stages
   (`1/6 system packages` … `6/6 copy results`); the training loop prints loss per iteration.
3. **Collect** the `diffusers/` folder from the bucket, or serve it directly as above.

### Bring your own data

Cosmos Framework trains from a JSONL dataset (one clip per line with `vision_path` and
structured `caption_json` windows) — see NVIDIA's
[JSONL dataset format](https://github.com/NVIDIA/cosmos-framework/blob/main/docs/dataset_jsonl.md).
Upload your dataset directory (with `train/video_dataset_file.jsonl` and the videos) to the
bucket and set env `DATASET_PATH=/data/my-dataset`. The default recipe expects 256px clips
with dense captions; NVIDIA's sample set is the reference for the layout.

### Knobs (env vars in the form or `--env` in the CLI)

| Variable | Default | Notes |
| --- | --- | --- |
| `RECIPE` | `nano` | `edge` (2B full SFT, cheaper) or `super` (LoRA on the 64B model) — NVIDIA's three recipes |
| `MAX_ITER` | `500` (NVIDIA's recipe); the 1-click link sets `20` | smoke run first, then `500`; warm-up and LR schedule are rescaled to match |
| `SAVE_ITER` | `= MAX_ITER` (one final checkpoint) | a Nano DCP checkpoint with optimizer state is ~200 GiB and takes ~12 min to write; intermediate saves need a bigger `--disk-size` |
| `NPROC` | all GPUs | number of `torchrun` ranks |
| `DATASET_PATH` | NVIDIA's BridgeData2 subset | your JSONL dataset dir under `/data` |
| `OUTPUT_DIR` | `/data/cosmos3-sft` | results root in the bucket |
| `RUN_ID` | `run-<timestamp>` | result sub-folder |
| `FRAMEWORK_REF` | pinned release commit | Cosmos Framework git ref |
| `HF_TOKEN` | unset | only for gated datasets or models |

### Observed results

Smoke run (`RECIPE=nano`, `MAX_ITER=20`) on a preemptible **8×H200** node in us-central1,
500 GiB disk, output to a mounted bucket — job `COMPLETED`, exit 0:

| Stage | Measured |
| --- | --- |
| Provisioning + image pull | ~6 min |
| Framework install (`uv sync`, torch 2.10 + cu130) | < 1 min |
| Dataset + VAE download, base checkpoint → DCP | ~8 min |
| Training | first iteration 83 s (compile), then **12.8 s / iteration** (8 GPUs, FSDP, 45k packed tokens) |
| Checkpoint save (full state, 165 GiB) | ~12 min |
| Export to safetensors + Diffusers conversion | ~3 min |
| Copy `diffusers/` (30 GB) to the bucket | < 1 min |
| **Total** | **~37 min**, of which ~4 min is the 20-iteration training itself |

Extrapolation for NVIDIA's full recipe (`MAX_ITER=500`, one final checkpoint): ~2 h of training
plus the ~30 min of fixed costs above, so about 2.5 hours on 8×H200 (H100 is the recipe's
reference hardware and should be similar).

### Other platforms

The 1-click link targets NVIDIA's reference hardware, 8×H100 in eu-north1. The run above used
`--platform gpu-h200-sxm --preset 8gpu-128vcpu-1600gb` in us-central1 (same preset name);
8×H100 in eu-north1 was not allocatable within the wait window on the day of testing.

> ⚠️ **Preemptible and not resumable.** The launcher redoes installation and download after a
> restart, so it runs with `--restart-policy never`. Use preemptible for smoke runs; for the
> full 500-iteration recipe untick *Preemptible*. Checkpoints stay on the job's disk and are
> lost with the VM — only the exported result is copied to the bucket.

> 💾 **Disk.** 500 GiB fits: framework + caches (~35 GiB), the converted base model (~32 GiB),
> **one** ~200 GiB training checkpoint, and the exports. Before exporting, the launcher deletes
> the wheel cache, the base-model copy and all but the latest checkpoint. If you set `SAVE_ITER`
> below `MAX_ITER`, raise `--disk-size` by ~200 GiB per extra checkpoint kept.

> ⚠️ **Guardrails.** Training does not use them. If you run framework *inference* on the
> result, its guardrails need `HF_TOKEN` with access to the gated guardrail models, or
> `--no-guardrails`.

<!-- factory:cli -->

## CLI alternative

```bash
BUCKET=$(nebius storage bucket get-by-name --name <your-bucket> --format jsonpath='{.metadata.id}')

nebius ai job create \
  --name cosmos3-sft-$(date +%Y%m%d-%H%M%S) \
  --image nvidia/cuda:13.0.2-cudnn-devel-ubuntu24.04 \
  --platform gpu-h100-sxm \
  --preset 8gpu-128vcpu-1600gb \
  --preemptible \
  --restart-policy never \
  --timeout 6h \
  --shm-size 128Gi \
  --disk-size 500Gi \
  --volume "$BUCKET:/data:rw" \
  --env MAX_ITER=500 \
  --container-command bash \
  --args '-c "apt-get update -qq && apt-get install -y -qq curl ca-certificates >/dev/null && curl -fsSL https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/main/templates/job-cosmos3-sft/src/run.sh -o /tmp/run.sh && bash /tmp/run.sh"'
```

`--shm-size` matters: eight `torchrun` ranks exchange tensors through `/dev/shm` (NVIDIA runs
the container with `--ipc=host`). The 8×H100 preset has 1.6 TB of RAM, so 128 GiB is safe.

<!-- /factory:cli -->

## Troubleshooting

- **`No space left on device` during export** — too many checkpoints on disk. Keep `SAVE_ITER = MAX_ITER` (default) or raise `--disk-size` (~200 GiB per Nano checkpoint).
- **Slow `Checkpoint save completed: Time taken: 7xx seconds`** — normal: a full-state DCP checkpoint of Nano is ~200 GiB.
- **`torch.cuda.device_count()` prints fewer GPUs than expected** — check the preset; `NPROC` defaults to all visible GPUs.
- **NCCL or shared-memory errors at training start** — raise `--shm-size`; the console form's default is too small for 8 ranks.
- **Job ends FAILED after preemption** — expected with `--restart-policy never`; rerun, or untick *Preemptible* for long runs.
- **Out of memory on smaller GPUs** — the Nano full fine-tune is tuned for 8×80 GB. Use `RECIPE=edge`, or `RECIPE=super` (LoRA) only on 8×H200.
- **Want to train the Reasoner instead?** — NVIDIA's `reasoner/finetune` recipes follow the same framework; point `COSMOS_REF`/recipe paths at them (not wrapped by this template yet).
