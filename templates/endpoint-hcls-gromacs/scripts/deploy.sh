#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID to the customer project ID}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID to a subnet in that project}"
: "${HCLS_STORAGE_RESOURCE_ID:?Set HCLS_STORAGE_RESOURCE_ID to a storagebucket-* or computefilesystem-* resource ID}"
: "${AUTH_TOKEN_SECRET_SELECTOR:?Set AUTH_TOKEN_SECRET_SELECTOR to a MysteryBox secret selector whose payload contains AUTH_TOKEN}"
: "${HCLS_IMAGE:?Set HCLS_IMAGE to the published GROMACS image tag or digest}"

case "$HCLS_STORAGE_RESOURCE_ID" in
  storagebucket-*|computefilesystem-*) ;;
  *)
    echo "HCLS_STORAGE_RESOURCE_ID must start with storagebucket- or computefilesystem-" >&2
    exit 2
    ;;
esac

ENDPOINT_NAME="${ENDPOINT_NAME:-hcls-gromacs-rest-mcp}"
PLATFORM="${PLATFORM:-gpu-l40s-a}"
PRESET="${PRESET:-1gpu-8vcpu-32gb}"
DISK_SIZE="${DISK_SIZE:-100Gi}"
SHM_SIZE="${SHM_SIZE:-16Gi}"
PREEMPTIBLE="${PREEMPTIBLE:-false}"

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name "$ENDPOINT_NAME" \
  --image "$HCLS_IMAGE" \
  --container-port 8000 \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --disk-size "$DISK_SIZE" \
  --shm-size "$SHM_SIZE" \
  --preemptible "$PREEMPTIBLE" \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --token-secret "$AUTH_TOKEN_SECRET_SELECTOR" \
  --volume "$HCLS_STORAGE_RESOURCE_ID:/mnt/hcls:rw" \
  --public \
  --format json
