#!/usr/bin/env bash
# Submit one attempt; use the same RUN_ROOT to reuse finished documents.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID in .env}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID in .env}"
: "${S3_SECRET_ID:?Set S3_SECRET_ID in .env}"
: "${RUN_ROOT:?Set RUN_ROOT in .env}"
: "${JOB_NAME:?Choose a new JOB_NAME for this attempt}"
if [[ -z ${GPU_PLATFORM:-} && -z ${GPU_PRESET:-} && ${NEBIUS_REGION:-eu-north1} == eu-north1 ]]; then
  # Keep existing .env files on their original L40S configuration.
  NEBIUS_REGION=eu-north1
  GPU_PLATFORM=gpu-l40s-d
  GPU_PRESET=1gpu-16vcpu-96gb
fi
: "${GPU_PLATFORM:?Set GPU_PLATFORM and GPU_PRESET to a preemptible GPU configuration in your project}"
: "${GPU_PRESET:?Set GPU_PRESET to a one-GPU preset for GPU_PLATFORM}"
: "${NEBIUS_REGION:?Set NEBIUS_REGION to the region of your bucket}"
if [[ ! $NEBIUS_REGION =~ ^[a-z0-9-]+$ ]]; then
  echo "Set NEBIUS_REGION to a region ID, for example eu-west1." >&2
  exit 2
fi
case "$GPU_PLATFORM" in
  gpu-b200-sxm|gpu-b200-sxm-a|gpu-b300-sxm|gpu-rtx6000|gpu-rtx6000-a) cuda=12.8 ;;
  *) cuda=12.6 ;;
esac
nebius ai job create \
  --parent-id "$NEBIUS_PROJECT_ID" --name "$JOB_NAME" \
  --image "pytorch/pytorch:2.7.1-cuda${cuda}-cudnn9-runtime" \
  --platform "$GPU_PLATFORM" --preset "$GPU_PRESET" \
  --preemptible --follows-spot-price \
  --disk-size 80Gi --timeout 1h --restart-policy never \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --container-command python3 --args /recipe/run_job.py \
  --inject-file scripts/run_job.py:/recipe/run_job.py \
  --env "RUN_ROOT=$RUN_ROOT" \
  --env "S3_ENDPOINT_URL=https://storage.${NEBIUS_REGION}.nebius.cloud" \
  --env "AWS_DEFAULT_REGION=$NEBIUS_REGION" \
  --env "RECIPE_REF=${RECIPE_REF:-main}" \
  --env "MAX_NEW_DOCUMENTS=${MAX_NEW_DOCUMENTS:-0}" \
  --env "CRASH_AFTER_CHUNKS=${CRASH_AFTER_CHUNKS:-}" \
  --env PYTHONUNBUFFERED=1 \
  --env-secret "AWS_ACCESS_KEY_ID=$S3_SECRET_ID" \
  --env-secret "AWS_SECRET_ACCESS_KEY=$S3_SECRET_ID" \
  "$@"
