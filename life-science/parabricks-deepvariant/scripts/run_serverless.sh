#!/usr/bin/env bash
# Submit the Parabricks DeepVariant pipeline as a Nebius AI Job using the
# customer's pre-built pipeline image in their Nebius Container Registry.

set -euo pipefail

: "${PIPELINE_IMAGE:?PIPELINE_IMAGE required (e.g. cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1)}"
: "${S3_BUCKET:?S3_BUCKET required}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required}"

S3_INPUT_PREFIX="${S3_INPUT_PREFIX:-parabricks/demo/hg002}"
S3_REF_PREFIX="${S3_REF_PREFIX:-parabricks/ref/grch38}"
S3_OUTPUT_PREFIX="${S3_OUTPUT_PREFIX:-parabricks/out}"
SAMPLE_ID="${SAMPLE_ID:-HG002}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-north1}"

PLATFORM="${PLATFORM:-gpu-h200-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
DISK_SIZE="${DISK_SIZE:-500Gi}"
JOB_NAME="${JOB_NAME:-parabricks-deepvariant-${SAMPLE_ID}-$(date +%s)}"

set -x
nebius ai job create \
    --name "$JOB_NAME" \
    --image "$PIPELINE_IMAGE" \
    --platform "$PLATFORM" \
    --preset "$PRESET" \
    --disk-size "$DISK_SIZE" \
    --env "S3_BUCKET=$S3_BUCKET" \
    --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL" \
    --env "S3_INPUT_PREFIX=$S3_INPUT_PREFIX" \
    --env "S3_REF_PREFIX=$S3_REF_PREFIX" \
    --env "S3_OUTPUT_PREFIX=$S3_OUTPUT_PREFIX" \
    --env "SAMPLE_ID=$SAMPLE_ID" \
    --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" \
    --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" \
    --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"
