#!/usr/bin/env bash
# Submit the synthetic MONAI medical-imaging workflow as a Nebius AI Job.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/run_serverless.sh

Required:
  IMAGE              Container image pushed to a registry accessible by Nebius AI Jobs

Optional:
  PARENT_ID          Nebius project ID. Uses CLI profile default when unset.
  SUBNET_ID          Explicit subnet ID when the project requires one.
  PLATFORM           Default: gpu-l40s-a
  PRESET             Default: 1gpu-8vcpu-32gb
  TIMEOUT            Default: 1h
  DISK_SIZE          Default: 100Gi
  JOB_NAME           Default: monai-medimg-<timestamp>
  CASE_ID            Default: synthetic-phantom-001
  SHAPE              Default: 96,96,64
  DEVICE             Default: auto
  PREEMPTIBLE        Set to true to request preemptible capacity.

Optional Object Storage upload:
  S3_BUCKET S3_PREFIX S3_ENDPOINT_URL AWS_ACCESS_KEY_ID AWS_DEFAULT_REGION
  AWS_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY_SECRET
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

: "${IMAGE:?IMAGE required, for example cr.eu-north1.nebius.cloud/<project>/monai-medical-imaging-job:0.1.0}"

PLATFORM="${PLATFORM:-gpu-l40s-a}"
PRESET="${PRESET:-1gpu-8vcpu-32gb}"
TIMEOUT="${TIMEOUT:-1h}"
DISK_SIZE="${DISK_SIZE:-100Gi}"
JOB_NAME="${JOB_NAME:-monai-medimg-$(date +%s)}"
CASE_ID="${CASE_ID:-synthetic-phantom-001}"
SHAPE="${SHAPE:-96,96,64}"
DEVICE="${DEVICE:-auto}"
S3_PREFIX="${S3_PREFIX:-monai-medical-imaging}"

MONAI_ARGS="--case-id ${CASE_ID} --shape ${SHAPE} --device ${DEVICE} --output-dir /workspace/output"

CREATE_CMD=(
    nebius ai job create
    --name "$JOB_NAME"
    --image "$IMAGE"
    --platform "$PLATFORM"
    --preset "$PRESET"
    --timeout "$TIMEOUT"
    --disk-size "$DISK_SIZE"
)

if [[ -n "${PARENT_ID:-}" ]]; then
    CREATE_CMD+=(--parent-id "$PARENT_ID")
fi

if [[ -n "${SUBNET_ID:-}" ]]; then
    CREATE_CMD+=(--subnet-id "$SUBNET_ID")
fi

if [[ "${PREEMPTIBLE:-false}" == "true" ]]; then
    CREATE_CMD+=(--preemptible)
fi

if [[ -n "${S3_BUCKET:-}" ]]; then
    : "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL required when S3_BUCKET is set}"
    : "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required when S3_BUCKET is set}"
    if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -z "${AWS_SECRET_ACCESS_KEY_SECRET:-}" ]]; then
        echo "Error: set AWS_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY_SECRET when S3_BUCKET is set." >&2
        exit 1
    fi

    MONAI_ARGS="${MONAI_ARGS} --upload-s3"
    CREATE_CMD+=(
        --env "S3_BUCKET=$S3_BUCKET"
        --env "S3_PREFIX=$S3_PREFIX"
        --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL"
        --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
        --env "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-eu-north1}"
    )
    if [[ -n "${AWS_SECRET_ACCESS_KEY_SECRET:-}" ]]; then
        CREATE_CMD+=(--env-secret "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_SECRET")
    else
        CREATE_CMD+=(--env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY")
    fi
else
    MONAI_ARGS="${MONAI_ARGS} --no-upload-s3"
fi

CREATE_CMD+=(--args "$MONAI_ARGS")

echo "Submitting Nebius AI Job: $JOB_NAME"
echo "Image: $IMAGE"
echo "Platform/preset: $PLATFORM / $PRESET"
"${CREATE_CMD[@]}"

