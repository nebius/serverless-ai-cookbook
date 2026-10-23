---
title: Train a Black Forest Labs FLUX 3 Action SO-101 Pick Orange task LoRA
category: robotics
type: batch-job
runtime: nebius-ai-jobs
frameworks: [pytorch, lerobot]
keywords: [robotics, black-forest-labs, flux-action, so101, lora, training]
difficulty: advanced
---

<p align="center">
  <a href="https://bfl.ai"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/black-forest-labs-white.svg">
    <img src="assets/black-forest-labs-black.svg" alt="Black Forest Labs" height="48">
  </picture></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://nebius.com"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/nebius-white.svg">
    <img src="assets/nebius-black.svg" alt="Nebius" height="48">
  </picture></a>
</p>

# Train a Black Forest Labs FLUX 3 Action SO-101 Pick Orange task LoRA

This demo trains a **task LoRA** on [Black Forest Labs' prepared SO-101 policy](https://docs.bfl.ai/flux_3/flux3_action_so101). It uses one Nebius GPU Job and 60 demonstrations from [LeIsaac Pick Orange](https://huggingface.co/datasets/LightwheelAI/leisaac-pick-orange) (Apache 2.0). The model uses the [FLUX Kommunity License](https://huggingface.co/black-forest-labs/flux-3-action-so101). To train full weights for a different robot, use the [new embodiment demo](../bfl-flux-action-new-embodiment-full-finetune/README.md).

The demo downloads pinned data and model revisions, converts LeIsaac's joint values into the model's SO-101 frame, trains 100 microsteps for a smoke test or 60,000 for the example full run, and publishes adapters to Nebius Object Storage. Preparation and training run inside the Serverless job; no local GPU or simulator is required. A calibrated 100-microstep Nebius smoke on 2026-10-23 completed preparation, 25 optimizer updates, and checkpoint publication; independent Object Storage readback verified both raw and EMA adapter hashes. The calibrated 60,000-step run remains unverified. This cookbook ends with a published adapter; it does not measure robot task success.

## Workflow

[![SO-101 training workflow: pinned Pick Orange data and model settings feed one Serverless GPU job for dataset preparation, joint calibration, and LoRA training. Object Storage holds complete adapter checkpoints, hashes, and the training receipt.](assets/workflow.png)](assets/workflow.png)

## Requirements and compute

- Local tools: authenticated Nebius CLI, Docker with Linux AMD64 build support, and AWS CLI configured for Object Storage. Python 3.10+ runs the lightweight local tests.
- A Nebius project, subnet, Object Storage bucket, container registry, and quota for the resources below. Keep the resources in the same region.
- Hugging Face model access: accept the linked model's access terms where required, and supply the token through `NEBIUS_HF_TOKEN_SECRET`.

| Stage | Resources | Work |
| --- | --- | --- |
| Training | Default: one H200, `1gpu-16vcpu-200gb`, 200 GiB scratch disk | Smoke: 100 microsteps; documented full run: 60,000. |

Wall-clock runtime, download size, and peak scratch usage have not been benchmarked for the current image. The 72-hour job timeout is a ceiling, not an estimated duration. The training receipt records `train_seconds` for training and publication; it excludes data preparation and model downloads.

## Files

| Path | Purpose |
| --- | --- |
| `Dockerfile` | Build the pinned training environment. |
| `assets/` | Workflow diagram, official logos, and logo source URLs. |
| `configs/` | Pinned model, dataset, and training settings. |
| `scripts/job.sh` | Submit smoke and full-training jobs. |
| `src/` | Dataset preparation, joint calibration, training, and checkpoint publication. |
| `tests/` | Local checks for job submission, calibration, dataset contracts, and publication. |

## 1. Configure and build

Run the following commands from this example directory:

```bash
export NEBIUS_PROFILE=YOUR_PROFILE
export NEBIUS_PROJECT_ID=YOUR_PROJECT_ID
export NEBIUS_SUBNET_ID=YOUR_SUBNET_ID
export NEBIUS_BUCKET=YOUR_BUCKET_NAME
export NEBIUS_BUCKET_ID=YOUR_STORAGEBUCKET_ID
export NEBIUS_REGISTRY_ID=YOUR_REGISTRY_ID
export NEBIUS_REGION=YOUR_REGION
export NEBIUS_GPU_PLATFORM=gpu-h200-sxm
export NEBIUS_S3_ENDPOINT="https://storage.$NEBIUS_REGION.nebius.cloud"
export AWS_PROFILE=YOUR_OBJECT_STORAGE_PROFILE
export NEBIUS_IMAGE="cr.$NEBIUS_REGION.nebius.cloud/${NEBIUS_REGISTRY_ID#registry-}/bfl-s:$(date -u +%m%d%H%M%S)"
docker build --platform linux/amd64 -t "$NEBIUS_IMAGE" .
docker push "$NEBIUS_IMAGE"
```

If Hugging Face requires a token for the SO-101 weights, set `NEBIUS_HF_TOKEN_SECRET` to its **Nebius MysteryBox secret selector**. The job receives it as `HF_TOKEN`; do not put the token in the image. W&B tracking is optional: set `WANDB_API_KEY` to a MysteryBox selector and `WANDB_PROJECT` to a project name before submitting.

## 2. Try a short run

```bash
export RUN_NAME="flux-orange-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/job.sh smoke
```

After submission, the helper prints the run name, artifact prefix, completion receipt, and commands to find and monitor the job. Save the returned job ID. Check the job and its durable result:

```bash
nebius ai job get SMOKE_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs SMOKE_JOB_ID --profile "$NEBIUS_PROFILE" --tail 50
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect `COMPLETED`, `microsteps: 100`, and an adapter hash in `TRAIN_COMPLETE.json`. Inspect `calibration-report.json` and `camera-preview.jpg` in the same run prefix before a long run. The report flags how far the demonstrations extend beyond the checkpoint's usual joint range. Use `bash scripts/job.sh smoke dry-run` to inspect a submission before sending it.

## 3. Train the full adapter

```bash
export FULL_STEPS=60000
export RUN_NAME="flux-orange-full-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/job.sh full
nebius ai job get FULL_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs FULL_JOB_ID --profile "$NEBIUS_PROFILE" --tail 50
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect a `COMPLETED` job and a `TRAIN_COMPLETE.json` with `microsteps: 60000`. The receipt names the final checkpoint; its `COMPLETE.json` records hashes for the raw and EMA adapters. Intermediate checkpoints are published every 5,000 microsteps. Use a fresh `RUN_NAME` for every run. If you choose `NEBIUS_PREEMPTIBLE=1`, completed checkpoints remain in Object Storage after interruption, but this demo does not automatically resume.

## Adapt and check locally

Edit [`configs/recipe.json`](configs/recipe.json) to change the pinned inputs. The calibration in [`src/calibration.py`](src/calibration.py) is specific to this dataset and SO-101 policy; verify joint units, signs, ranges, and camera order before substituting recordings. Use the [full fine-tuning example](../bfl-flux-action-new-embodiment-full-finetune/README.md) for a different embodiment.

Run the lightweight checks from this directory:

```bash
python3 -m unittest discover -s tests -v
```

The parquet/safetensors calibration check skips when its optional dependencies are absent locally; those dependencies are included in the training image.

## Storage, checkpoints, and interruption

Dataset preparation and training use local `/workspace/work` storage so video reads and training writes do not depend on the Object Storage mount. The bucket is mounted at `/workspace/data` for durable artifacts. Scratch disks and job timeouts are configured in `scripts/job.sh`; the defaults provide working room but are not measured minimums.

A background watcher checks for complete checkpoints every 30 seconds and copies them to the bucket. If publication fails, the runner stops the training process group and fails the job, preserving any checkpoints already published. For the documented 60,000-microstep run, checkpoints are saved every 5,000 microsteps. Publication records adapter hashes in `COMPLETE.json`; `TRAIN_COMPLETE.json` is written only after the requested final checkpoint is published. A completed checkpoint may survive an interrupted job even when the training receipt is absent.

`selected_checkpoint` in the receipt identifies **the final checkpoint**. The runner does not rank checkpoints or run policy evaluation; `quality_evaluation: "not_run"` makes that limit explicit in the receipt.

Preemptible execution is opt-in with `NEBIUS_PREEMPTIBLE=1` and disables automatic restart. There is no resume path: after interruption, inspect published checkpoints, then use a fresh `RUN_NAME` for a new training run. Reusing a run name is rejected to prevent overwrites.

## Troubleshooting

Replace `JOB_ID` in the commands below with the ID returned by submission or the printed name lookup.

| Symptom | Diagnose and recover |
| --- | --- |
| Image label exceeds 64 characters | Use a short repository name and tag as above. If validation reports a `metadata.labels` length error, keep the complete image reference at most 64 characters. Long tags and full digest references exceed the limit in the current CLI/API path. |
| Model access denied | Inspect `nebius ai job logs JOB_ID --profile "$NEBIUS_PROFILE" --tail 80`. Accept the model access terms and set `NEBIUS_HF_TOKEN_SECRET` to a MysteryBox selector before a new submission. |
| Pending job or capacity error such as `NotEnoughResources` | Inspect `nebius ai job get JOB_ID --profile "$NEBIUS_PROFILE"` for scheduling details. Check the selected GPU quota and capacity in your region before retrying; a pending job is not evidence that training started. |
| `No space left on device` | Inspect the job logs for the failing path. Increase `--disk-size` in `scripts/job.sh` if scratch storage is exhausted, then submit a fresh run. |
| Interrupted job or timeout | Inspect job state and logs, then list `runs/$RUN_NAME/` in the bucket. Completed checkpoints can remain; a new training run starts from scratch under a fresh name. Increasing a timeout does not enable resume. |
| Run prefix already exists | Choose a fresh `RUN_NAME`; do not delete previous results just to reuse the name. |
| No `TRAIN_COMPLETE.json` | Inspect job state and logs. Individual checkpoints do not prove the requested training run finished; require both a completed job and its training receipt. |
| Calibration check fails | Inspect `calibration-report.json` if written, and the job logs. Verify joint units, signs, ranges, and camera order against `src/calibration.py` and the pinned dataset before retrying. Keep the calibration checks enabled. |
