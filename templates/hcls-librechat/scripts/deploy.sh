#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID to the customer project ID}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID to a subnet in that project}"
: "${SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR:?Set SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR to a MysteryBox secret whose payload key is SCIENTIFIC_MODELS_API_KEY}"
: "${TOKEN_FACTORY_SECRET_SELECTOR:?Set TOKEN_FACTORY_SECRET_SELECTOR to a MysteryBox secret whose payload key is NEBIUS_API_KEY}"
: "${TAVILY_SECRET_SELECTOR:?Set TAVILY_SECRET_SELECTOR to a MysteryBox secret whose payload key is TAVILY_API_KEY}"
: "${IMAGE:?Set IMAGE to the tested release tag or digest}"

ENDPOINT_NAME="${ENDPOINT_NAME:-nebius-scientific-ai-agent}"
SCIENTIFIC_MODELS_API_BASE_URL="${SCIENTIFIC_MODELS_API_BASE_URL:-https://89.169.99.188/v1}"
SCIENTIFIC_MODELS_MCP_URL="${SCIENTIFIC_MODELS_MCP_URL:-https://89.169.99.188/mcp}"

NEBIUS_CMD=(nebius)
if [[ -n "${NEBIUS_PROFILE:-}" ]]; then NEBIUS_CMD+=(--profile "$NEBIUS_PROFILE"); fi
CREATE_CMD=(
  "${NEBIUS_CMD[@]}" ai endpoint create
  --parent-id "$NEBIUS_PROJECT_ID"
  --name "$ENDPOINT_NAME"
  --image "$IMAGE"
  --container-port 3080
  --platform "${PLATFORM:-cpu-d3}"
  --preset "${PRESET:-4vcpu-16gb}"
  --disk-size "${DISK_SIZE:-100Gi}"
  --subnet-id "$NEBIUS_SUBNET_ID"
  --env "SCIENTIFIC_MODELS_API_BASE_URL=$SCIENTIFIC_MODELS_API_BASE_URL"
  --env "SCIENTIFIC_MODELS_MCP_URL=$SCIENTIFIC_MODELS_MCP_URL"
  --env "SCIENTIFIC_DEDICATED_CHAT_ENABLED=${SCIENTIFIC_DEDICATED_CHAT_ENABLED:-true}"
  --env "SCIENTIFIC_CHAT_MODEL=${SCIENTIFIC_CHAT_MODEL:-Qwen/Qwen3-235B-A22B-Instruct-2507}"
  --env-secret "SCIENTIFIC_MODELS_API_KEY=$SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR"
  --env-secret "NEBIUS_API_KEY=$TOKEN_FACTORY_SECRET_SELECTOR"
  --env-secret "TAVILY_API_KEY=$TAVILY_SECRET_SELECTOR"
  --auth none
  --public
  --format json
)

# Mount only user files on Object Storage. Mongo and credential encryption state
# remain on the endpoint disk; they must never use the S3/FUSE mount.
if [[ -n "${TEAM_BUCKET_NAME:-}" ]]; then
  : "${S3_CREDENTIAL_SECRET_SELECTOR:?Set the MysteryBox selector with S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY}"
  : "${TEAM_ID:?Set TEAM_ID for the mounted workspace owner}"
  CREATE_CMD+=(--volume "s3://${TEAM_BUCKET_NAME}:/workspace:rw:default@${S3_CREDENTIAL_SECRET_SELECTOR}"
    --env "TEAM_ID=$TEAM_ID" --env "TEAM_BUCKET_NAME=$TEAM_BUCKET_NAME")
fi

if [[ -n "${SEED_DEFAULT_USER_EMAIL:-}" ]]; then
  : "${USER_PASSWORD_SECRET_SELECTOR:?Set the MysteryBox selector containing SEED_DEFAULT_USER_PASSWORD}"
  CREATE_CMD+=(--env "SEED_DEFAULT_USER_EMAIL=$SEED_DEFAULT_USER_EMAIL"
    --env-secret "SEED_DEFAULT_USER_PASSWORD=$USER_PASSWORD_SECRET_SELECTOR"
    --env "ALLOW_REGISTRATION=false")
fi
if [[ -n "${SSH_PUBLIC_KEY_FILE:-}" ]]; then
  CREATE_CMD+=(--ssh-key "$(<"$SSH_PUBLIC_KEY_FILE")")
fi

"${CREATE_CMD[@]}"
