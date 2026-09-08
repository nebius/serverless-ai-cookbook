#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID to the customer project ID}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID to a subnet in that project}"
: "${HCLS_STORAGE_SOURCE:?Set HCLS_STORAGE_SOURCE to s3://BUCKET or a computefilesystem-* resource ID}"
: "${AUTH_TOKEN_SECRET_SELECTOR:?Set AUTH_TOKEN_SECRET_SELECTOR to a MysteryBox secret selector whose payload contains AUTH_TOKEN}"

HCLS_IMAGE="${HCLS_IMAGE:-cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/gromacs-md-api:20260908-2341ac7}"
# The release tag above is non-overwritten and resolves to
# sha256:e8e06b7657218226d19e90ccef37c72dff8197aca2f1c94314a2856eec9b7e34.
# Serverless currently rejects a full digest reference because it copies the
# 136-character image value into a Compute label whose limit is 64 characters.

case "$HCLS_STORAGE_SOURCE" in
  s3://*)
    : "${S3_CREDENTIAL_SECRET_SELECTOR:?For s3:// storage, set S3_CREDENTIAL_SECRET_SELECTOR to a MysteryBox secret containing S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY}"
    S3_PROFILE="${S3_PROFILE:-default}"
    HCLS_VOLUME="${HCLS_STORAGE_SOURCE}:/mnt/hcls:rw:${S3_PROFILE}@${S3_CREDENTIAL_SECRET_SELECTOR}"
    ;;
  computefilesystem-*)
    HCLS_VOLUME="${HCLS_STORAGE_SOURCE}:/mnt/hcls:rw"
    ;;
  storagebucket-*)
    echo "Use s3://BUCKET plus S3_CREDENTIAL_SECRET_SELECTOR for durable Object Storage; bucket resource-ID mounts are not accepted by this template" >&2
    exit 2
    ;;
  *)
    echo "HCLS_STORAGE_SOURCE must be s3://BUCKET or start with computefilesystem-" >&2
    exit 2
    ;;
esac

ENDPOINT_NAME="${ENDPOINT_NAME:-hcls-gromacs-rest-mcp}"
PLATFORM="${PLATFORM:-gpu-l40s-a}"
PRESET="${PRESET:-1gpu-8vcpu-32gb}"
DISK_SIZE="${DISK_SIZE:-100Gi}"
SHM_SIZE="${SHM_SIZE:-16Gi}"
PREEMPTIBLE="${PREEMPTIBLE:-false}"

CREATE_CMD=(nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name "$ENDPOINT_NAME" \
  --image "$HCLS_IMAGE" \
  --container-port 8000 \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --disk-size "$DISK_SIZE" \
  --shm-size "$SHM_SIZE" \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --token-secret "$AUTH_TOKEN_SECRET_SELECTOR" \
  --volume "$HCLS_VOLUME" \
  --public \
  --format json)

case "$PREEMPTIBLE" in
  true|1|yes) CREATE_CMD+=(--preemptible) ;;
  false|0|no) ;;
  *)
    echo "PREEMPTIBLE must be true or false" >&2
    exit 2
    ;;
esac

"${CREATE_CMD[@]}"
