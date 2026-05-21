#!/usr/bin/env bash
# Submit the Parabricks DeepVariant pipeline as a Nebius AI Job using the
# customer's pre-built pipeline image in their Nebius Container Registry.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/run_serverless.sh

Submit the Parabricks DeepVariant pipeline as a Nebius AI Job.

Required environment:
  PIPELINE_IMAGE        Pipeline image in Nebius Container Registry
  S3_BUCKET             Object Storage bucket name
  S3_ENDPOINT_URL       Object Storage endpoint URL
  AWS_ACCESS_KEY_ID     Object Storage access key ID
  AWS_SECRET_ACCESS_KEY Object Storage secret access key, or set
                        AWS_SECRET_ACCESS_KEY_SECRET to a MysteryBox selector

Optional environment:
  PARENT_ID SUBNET_ID PLATFORM PRESET DISK_SIZE JOB_NAME
  S3_INPUT_PREFIX S3_REF_PREFIX S3_OUTPUT_PREFIX SAMPLE_ID AWS_DEFAULT_REGION
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

: "${PIPELINE_IMAGE:?PIPELINE_IMAGE required (e.g. cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1)}"
: "${S3_BUCKET:?S3_BUCKET required}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required}"
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -z "${AWS_SECRET_ACCESS_KEY_SECRET:-}" ]]; then
    echo "Error: set AWS_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY_SECRET." >&2
    exit 1
fi

S3_INPUT_PREFIX="${S3_INPUT_PREFIX:-parabricks/demo/hg002}"
S3_REF_PREFIX="${S3_REF_PREFIX:-parabricks/ref/grch38}"
S3_OUTPUT_PREFIX="${S3_OUTPUT_PREFIX:-parabricks/out}"
SAMPLE_ID="${SAMPLE_ID:-HG002}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-north1}"

PLATFORM="${PLATFORM:-gpu-h200-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
DISK_SIZE="${DISK_SIZE:-500Gi}"
JOB_NAME="${JOB_NAME:-parabricks-deepvariant-${SAMPLE_ID}-$(date +%s)}"

CREATE_CMD=(
    nebius ai job create
    --name "$JOB_NAME"
    --image "$PIPELINE_IMAGE"
    --platform "$PLATFORM"
    --preset "$PRESET"
    --disk-size "$DISK_SIZE"
    --env "S3_BUCKET=$S3_BUCKET"
    --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL"
    --env "S3_INPUT_PREFIX=$S3_INPUT_PREFIX"
    --env "S3_REF_PREFIX=$S3_REF_PREFIX"
    --env "S3_OUTPUT_PREFIX=$S3_OUTPUT_PREFIX"
    --env "SAMPLE_ID=$SAMPLE_ID"
    --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
    --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"
)

if [[ -n "${AWS_SECRET_ACCESS_KEY_SECRET:-}" ]]; then
    CREATE_CMD+=(--env-secret "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_SECRET")
else
    CREATE_CMD+=(--env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY")
fi

if [[ -n "${PARENT_ID:-}" ]]; then
    CREATE_CMD+=(--parent-id "$PARENT_ID")
fi

if [[ -n "${SUBNET_ID:-}" ]]; then
    CREATE_CMD+=(--subnet-id "$SUBNET_ID")
fi

echo "Submitting Nebius AI Job: $JOB_NAME"
"${CREATE_CMD[@]}"
