#!/usr/bin/env bash
# Submit one attempt; use the same RUN_ROOT to reuse finished documents.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID in .env}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID in .env}"
: "${S3_SECRET_ID:?Set S3_SECRET_ID in .env}"
: "${RUN_ROOT:?Set RUN_ROOT in .env}"
: "${JOB_NAME:?Choose a new JOB_NAME for this attempt}"
nebius ai job create \
  --parent-id "$NEBIUS_PROJECT_ID" --name "$JOB_NAME" \
  --image pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime \
  --platform gpu-l40s-d --preset 1gpu-16vcpu-96gb \
  --preemptible --follows-spot-price \
  --disk-size 80Gi --timeout 1h --restart-policy never \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --container-command python3 --args /recipe/run_job.py \
  --inject-file scripts/run_job.py:/recipe/run_job.py \
  --env "RUN_ROOT=$RUN_ROOT" \
  --env "S3_ENDPOINT_URL=https://storage.eu-north1.nebius.cloud" \
  --env "AWS_DEFAULT_REGION=eu-north1" \
  --env "RECIPE_REF=${RECIPE_REF:-main}" \
  --env "MAX_NEW_DOCUMENTS=${MAX_NEW_DOCUMENTS:-0}" \
  --env "CRASH_AFTER_CHUNKS=${CRASH_AFTER_CHUNKS:-}" \
  --env PYTHONUNBUFFERED=1 \
  --env-secret "AWS_ACCESS_KEY_ID=$S3_SECRET_ID" \
  --env-secret "AWS_SECRET_ACCESS_KEY=$S3_SECRET_ID" \
  "$@"
