#!/usr/bin/env bash
set -euo pipefail

# The Create Endpoint button in README.md is normally easier. This is a
# repeatable CLI equivalent for a public image already resolved to a digest.
: "${PARENT_ID:?Set PARENT_ID to the Nebius project ID.}"
: "${SUBNET_ID:?Set SUBNET_ID to a subnet in the Nebius project.}"
: "${IMAGE_REFERENCE:?Set IMAGE_REFERENCE to an immutable image @sha256 reference.}"
: "${AUTH_TOKEN_SECRET:?Set AUTH_TOKEN_SECRET to a customer-owned MysteryBox selector.}"

[[ "$IMAGE_REFERENCE" == *@sha256:* ]] \
  || { echo "IMAGE_REFERENCE must be an immutable @sha256 reference." >&2; exit 2; }

nebius ai endpoint create \
  --parent-id "$PARENT_ID" \
  --name "${ENDPOINT_NAME:-bioir-boltz2-tutorial}" \
  --image "$IMAGE_REFERENCE" \
  --platform "${PLATFORM:-gpu-l40s-a}" \
  --preset "${PRESET:-1gpu-8vcpu-32gb}" \
  --subnet-id "$SUBNET_ID" \
  --container-port 8000 \
  --disk-size "${DISK_SIZE:-500Gi}" \
  --public \
  --auth token \
  --token-secret "$AUTH_TOKEN_SECRET"
