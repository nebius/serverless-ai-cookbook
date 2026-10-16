---
title: Full fine-tune FLUX 3 Action for a new robot embodiment
category: robotics
type: batch-job
runtime: nebius-ai-jobs
frameworks: [pytorch, lerobot]
keywords: [robotics, flux-action, full-finetune, new-embodiment, aloha]
difficulty: advanced
---

# Full fine-tune FLUX 3 Action for a new robot embodiment

This demo trains the weights of [FLUX 3 Action base](https://docs.bfl.ai/flux_3/flux3_action_finetuning) and a new 14-action ALOHA head on **one Nebius H200**. It uses [ALOHA Static Cups Open](https://huggingface.co/datasets/lerobot/aloha_static_cups_open), a small MIT-licensed dataset. The model has its own [license](https://huggingface.co/black-forest-labs/flux-3-action-base) and requires access on Hugging Face. For a task LoRA on BFL's prepared SO-101 policy, use the [SO-101 demo](../flux-action-so101-pick-orange-task-lora/README.md).

The demo downloads pinned model and dataset revisions, trains four updates as a smoke test or 3,000 updates as a full run, and saves checkpoints and a BF16 export to Nebius Object Storage. A separate CPU job reloads the export and scores one reserved dataset window. Earlier Nebius runs completed the four-update smoke, its one-window reload, and a 3,000-update train. The full export has not yet been reloaded independently, and robot task success has not been measured.

## 1. Configure and build

Install and sign in to the Nebius CLI, Docker, and AWS CLI. Use a project, subnet, bucket, and registry in the same region. Run these commands from this directory:

```bash
export NEBIUS_PROFILE=YOUR_PROFILE
export NEBIUS_PROJECT_ID=YOUR_PROJECT_ID
export NEBIUS_SUBNET_ID=YOUR_SUBNET_ID
export NEBIUS_BUCKET=YOUR_BUCKET_NAME
export NEBIUS_BUCKET_ID=YOUR_STORAGEBUCKET_ID
export NEBIUS_REGISTRY_ID=YOUR_REGISTRY_ID
export NEBIUS_REGION=YOUR_REGION
export NEBIUS_S3_ENDPOINT="https://storage.$NEBIUS_REGION.nebius.cloud"
export AWS_PROFILE=YOUR_OBJECT_STORAGE_PROFILE
export NEBIUS_IMAGE="cr.$NEBIUS_REGION.nebius.cloud/${NEBIUS_REGISTRY_ID#registry-}/flux-action-full:$(date -u +%Y%m%dT%H%M%SZ)"
docker build --platform linux/amd64 -t "$NEBIUS_IMAGE" .
docker push "$NEBIUS_IMAGE"
```

If Hugging Face requires a token, set `NEBIUS_HF_TOKEN_SECRET` to its **Nebius MysteryBox secret selector**. The job reads the token as `HF_TOKEN`; do not put the token in the image.

## 2. Try a short run

```bash
export RUN_NAME="flux-aloha-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
bash job.sh smoke
```

Save the returned job ID. Check the job and its result:

```bash
nebius ai job get SMOKE_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs SMOKE_JOB_ID --profile "$NEBIUS_PROFILE" --tail 80
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect a `COMPLETED` job and `optimizer_updates: 4` in `TRAIN_COMPLETE.json`. The run prefix also holds the pinned recipe, dataset index, metrics, checkpoint, and export. Use `bash job.sh smoke dry-run` to inspect a submission before sending it.

Reload the published export in a separate CPU job:

```bash
export CHECK_NAME="smoke-check-$(date -u +%Y%m%dT%H%M%SZ)"
bash job.sh check
nebius ai job get CHECK_JOB_ID --profile "$NEBIUS_PROFILE"
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/checks/$CHECK_NAME/COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect `COMPLETED`, one scored window, and finite action errors. This is an inference check, not a quality benchmark.

## 3. Train the full example

```bash
export RUN_NAME="flux-aloha-full-$(date -u +%Y%m%dT%H%M%SZ)"
bash job.sh full
nebius ai job get FULL_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs FULL_JOB_ID --profile "$NEBIUS_PROFILE" --tail 80
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
export CHECK_NAME="full-check-$(date -u +%Y%m%dT%H%M%SZ)"
bash job.sh check
```

Expect `optimizer_updates: 3000` and an `export_model_sha256` in the training receipt. The check job writes `checks/$CHECK_NAME/COMPLETE.json`. A full run publishes checkpoints every 500 updates. Use a fresh `RUN_NAME` for every run.

## Use your own robot

Edit [`recipe.json`](recipe.json) for the dataset revision, robot type, ordered state and action channels, cameras, FPS, and reserved episodes. Edit [`train.json`](train.json) for the action head, camera layout, action horizon, timing, and schedule. Check action units and whether commands are absolute or deltas, both grippers' signs and ranges, camera order, and episode alignment against real recordings. The preparation step rejects mismatched metadata and policy settings. You must also map exported actions back into your robot's command frame and measure task success separately; matching 14 numbers alone is not enough.
