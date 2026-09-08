#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID to the customer project ID}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID to a subnet in that project}"
: "${GROMACS_MCP_URL:?Set GROMACS_MCP_URL to the complete https://.../mcp URL}"

IMAGE="${IMAGE:-cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/librechat-gromacs:latest}"
ENDPOINT_NAME="${ENDPOINT_NAME:-hcls-librechat-gromacs}"

CREATE_CMD=(
  nebius ai endpoint create
  --parent-id "$NEBIUS_PROJECT_ID"
  --name "$ENDPOINT_NAME"
  --image "$IMAGE"
  --container-port 3080
  --platform "${PLATFORM:-cpu-d3}"
  --preset "${PRESET:-4vcpu-16gb}"
  --disk-size "${DISK_SIZE:-100Gi}"
  --subnet-id "$NEBIUS_SUBNET_ID"
  --env "GROMACS_MCP_URL=$GROMACS_MCP_URL"
  --auth none
  --public
  --format json
)

# Both mappings are optional. Without them, LibreChat asks each signed-in user
# for the corresponding credential and encrypts it with its generated CREDS key.
if [[ -n "${TOKEN_FACTORY_SECRET_SELECTOR:-}" ]]; then
  CREATE_CMD+=(--env-secret "NEBIUS_API_KEY=$TOKEN_FACTORY_SECRET_SELECTOR")
fi
if [[ -n "${GROMACS_AUTH_TOKEN_SECRET_SELECTOR:-}" ]]; then
  CREATE_CMD+=(--env-secret "AUTH_TOKEN=$GROMACS_AUTH_TOKEN_SECRET_SELECTOR")
fi

"${CREATE_CMD[@]}"
