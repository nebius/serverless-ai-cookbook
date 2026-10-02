---
title: Train a FLUX 3 Action SO-101 Pick Orange task LoRA
category: robotics
type: batch-job
runtime: nebius-ai-jobs
frameworks: [pytorch, lerobot, isaac-sim]
keywords: [robotics, flux-action, so101, lora, benchmark]
difficulty: advanced
---

# Train a FLUX 3 Action SO-101 Pick Orange task LoRA

This demo trains a **task LoRA** on [BFL's prepared SO-101 policy](https://docs.bfl.ai/flux_3/flux3_action_so101). It uses one Nebius GPU Job and 60 demonstrations from [LeIsaac Pick Orange](https://huggingface.co/datasets/LightwheelAI/leisaac-pick-orange) (Apache 2.0). The model uses the [FLUX Kommunity License](https://huggingface.co/black-forest-labs/flux-3-action-so101). To train full weights for a different robot, use the [new embodiment demo](../flux-action-new-embodiment-full-finetune/README.md).

The demo downloads pinned data and model revisions, converts LeIsaac's joint values into the model's SO-101 frame, trains 100 microsteps for a smoke test or 60,000 for the example full run, and publishes adapters to Nebius Object Storage. An earlier calibrated 100-step Nebius smoke ran end to end, but neither base nor adapter placed an orange in its one evaluation seed. The 60,000-step calibrated run and 25-seed comparison have not completed. Training alone does not establish policy quality.

## 1. Configure and build

Install and sign in to the Nebius CLI, Docker, and AWS CLI. Use a project, subnet, bucket, and registry in the same region. Work from this directory:

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
export NEBIUS_IMAGE="cr.$NEBIUS_REGION.nebius.cloud/${NEBIUS_REGISTRY_ID#registry-}/flux-so101-orange:$(date -u +%Y%m%dT%H%M%SZ)"
docker build --platform linux/amd64 -t "$NEBIUS_IMAGE" .
docker push "$NEBIUS_IMAGE"
```

If Hugging Face requires a token for the SO-101 weights, set `NEBIUS_HF_TOKEN_SECRET` to its **Nebius MysteryBox secret selector**. The job receives it as `HF_TOKEN`; do not put the token in the image. W&B tracking is optional: set `WANDB_API_KEY` to a MysteryBox selector and `WANDB_PROJECT` to a project name before submitting.

## 2. Try a short run

```bash
export RUN_NAME="flux-orange-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
bash job.sh smoke
```

Save the returned job ID. Check the job and its durable result:

```bash
nebius ai job get SMOKE_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs SMOKE_JOB_ID --profile "$NEBIUS_PROFILE" --tail 50
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect `COMPLETED`, `microsteps: 100`, and an adapter hash in `TRAIN_COMPLETE.json`. Inspect `calibration-report.json` and `camera-preview.jpg` in the same run prefix before a long run. The report flags how far the demonstrations extend beyond the checkpoint's usual joint range. Use `bash job.sh smoke dry-run` to inspect a submission before sending it.

## 3. Train the full adapter

```bash
export FULL_STEPS=60000
export RUN_NAME="flux-orange-full-$(date -u +%Y%m%dT%H%M%SZ)"
bash job.sh full
nebius ai job get FULL_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs FULL_JOB_ID --profile "$NEBIUS_PROFILE" --tail 50
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect a `COMPLETED` job and a `TRAIN_COMPLETE.json` with `microsteps: 60000`. The receipt names the selected checkpoint; its `COMPLETE.json` records hashes for the raw and EMA adapters. Intermediate checkpoints are published every 5,000 microsteps. Use a fresh `RUN_NAME` for every run. If you choose `NEBIUS_PREEMPTIBLE=1`, completed checkpoints remain in Object Storage after interruption, but this demo does not automatically resume.

## 4. Test the policy in Isaac Sim

Follow [EVALUATE.md](EVALUATE.md) on an RTX host with Isaac Sim 5.1 and LeIsaac. It runs the released base and trained adapter on the same 25 Pick Orange seeds, then compares orange placements and full task successes. The H200 training job does not run Isaac Sim. Until that paired evaluation passes, the full run is a published adapter, not a demonstrated improvement.
