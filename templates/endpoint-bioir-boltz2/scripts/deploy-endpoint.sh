#!/usr/bin/env bash
set -euo pipefail

# The README button launches the password-protected notebook.
# This helper deploys the optional token-protected HTTP service instead.
: "${PARENT_ID:?Set PARENT_ID to the Nebius project ID.}"
: "${SUBNET_ID:?Set SUBNET_ID to a subnet in the Nebius project.}"
: "${IMAGE_REFERENCE:?Set IMAGE_REFERENCE to an immutable image @sha256 reference.}"
: "${AUTH_TOKEN_SECRET:?Set AUTH_TOKEN_SECRET to a customer-owned MysteryBox selector.}"

[[ "$IMAGE_REFERENCE" =~ @sha256:[[:xdigit:]]{64}$ ]] \
  || { echo "IMAGE_REFERENCE must be an immutable @sha256 reference." >&2; exit 2; }

# CLI 0.12.206 copies the reference into a VM label limited to 64 characters.
# An explicitly supplied short alias is safe to use only after digest verification.
deployment_image="$IMAGE_REFERENCE"
if [[ -n "${DEPLOY_IMAGE_REFERENCE:-}" ]]; then
  (( ${#DEPLOY_IMAGE_REFERENCE} <= 64 )) \
    || { echo "DEPLOY_IMAGE_REFERENCE must be at most 64 characters." >&2; exit 2; }
  command -v crane >/dev/null \
    || { echo "Install crane to verify the deployment alias." >&2; exit 2; }
  expected_digest="${IMAGE_REFERENCE##*@}"
  actual_digest="$(crane digest "$DEPLOY_IMAGE_REFERENCE")"
  [[ "$actual_digest" == "$expected_digest" ]] \
    || { echo "Deployment alias does not match IMAGE_REFERENCE." >&2; exit 2; }
  deployment_image="$DEPLOY_IMAGE_REFERENCE"
fi

nebius ai endpoint create \
  --parent-id "$PARENT_ID" \
  --name "${ENDPOINT_NAME:-bioir-boltz2-tutorial}" \
  --image "$deployment_image" \
  --platform "${PLATFORM:-gpu-l40s-a}" \
  --preset "${PRESET:-1gpu-8vcpu-32gb}" \
  --subnet-id "$SUBNET_ID" \
  --container-port 8000 \
  --disk-size "${DISK_SIZE:-500Gi}" \
  --public \
  --auth token \
  --token-secret "$AUTH_TOKEN_SECRET"
