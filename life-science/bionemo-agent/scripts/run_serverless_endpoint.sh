#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?Set IMAGE to the immutable application reference ending in @sha256:<digest>}"
: "${AUTH_TOKEN_SECRET:?Set AUTH_TOKEN_SECRET to a MysteryBox selector whose payload contains AUTH_TOKEN}"
: "${NEBIUS_API_KEY_SECRET:?Set NEBIUS_API_KEY_SECRET to a MysteryBox selector whose payload contains NEBIUS_API_KEY}"

if [[ -z "${NVIDIA_API_KEY_SECRET:-}" && -z "${NGC_API_KEY_SECRET:-}" ]]; then
  echo "Set NVIDIA_API_KEY_SECRET or NGC_API_KEY_SECRET to its matching MysteryBox payload." >&2
  exit 2
fi
if [[ -n "${NVIDIA_API_KEY_SECRET:-}" && -n "${NGC_API_KEY_SECRET:-}" ]]; then
  echo "Set only one of NVIDIA_API_KEY_SECRET or NGC_API_KEY_SECRET." >&2
  exit 2
fi

if [[ "$IMAGE" != cr.*.nebius.cloud/*@sha256:* ]]; then
  echo "IMAGE must be an immutable Nebius Container Registry reference." >&2
  exit 2
fi

ENDPOINT_NAME="${ENDPOINT_NAME:-bionemo-agent-2-1}"
PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-4vcpu-16gb}"
DISK_SIZE="${DISK_SIZE:-30Gi}"
PROFILE="${PROFILE:-sandbox}"

CREATE_CMD=(
  nebius --profile "$PROFILE" ai endpoint create
  --name "$ENDPOINT_NAME"
  --image "$IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --disk-size "$DISK_SIZE"
  --container-port 18789
  --public
  --auth token
  --token-secret "$AUTH_TOKEN_SECRET"
  --env-secret "AUTH_TOKEN=$AUTH_TOKEN_SECRET"
  --env-secret "NEBIUS_API_KEY=$NEBIUS_API_KEY_SECRET"
  --env "BIONEMO_ENABLE_HTTPS_TUNNEL=true"
)

if [[ -n "${NVIDIA_API_KEY_SECRET:-}" ]]; then
  CREATE_CMD+=(--env-secret "NVIDIA_API_KEY=$NVIDIA_API_KEY_SECRET")
else
  CREATE_CMD+=(--env-secret "NGC_API_KEY=$NGC_API_KEY_SECRET")
fi

if [[ -n "${PARENT_ID:-}" ]]; then CREATE_CMD+=(--parent-id "$PARENT_ID"); fi
if [[ -n "${SUBNET_ID:-}" ]]; then CREATE_CMD+=(--subnet-id "$SUBNET_ID"); fi
if [[ -n "${REGISTRY_SECRET:-}" ]]; then CREATE_CMD+=(--registry-secret "$REGISTRY_SECRET"); fi

echo "Creating task-owned regular CPU Serverless Endpoint '$ENDPOINT_NAME' from an immutable image."
"${CREATE_CMD[@]}"

cat <<EOF

The endpoint starts a supervised Cloudflare quick tunnel and prints an HTTPS URL
to its logs. The URL never contains the gateway token.

Inspect the endpoint and logs:
  nebius --profile "$PROFILE" ai endpoint get-by-name --name "$ENDPOINT_NAME" --format json
  ENDPOINT_ID=\$(nebius --profile "$PROFILE" ai endpoint get-by-name --name "$ENDPOINT_NAME" --format jsonpath='{.metadata.id}')
  nebius --profile "$PROFILE" ai endpoint logs "\$ENDPOINT_ID" --tail 200 --timestamps

Open the logged https://*.trycloudflare.com URL from a clean browser and enter
the AUTH_TOKEN value. The direct Serverless IP remains protected by the same
MysteryBox AUTH_TOKEN through Serverless endpoint authentication.
EOF
