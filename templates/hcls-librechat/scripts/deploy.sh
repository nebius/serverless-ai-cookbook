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
  --env "SCIENTIFIC_MODELS_API_BASE_URL=$SCIENTIFIC_MODELS_API_BASE_URL"
  --env "SCIENTIFIC_MODELS_MCP_URL=$SCIENTIFIC_MODELS_MCP_URL"
  --env-secret "SCIENTIFIC_MODELS_API_KEY=$SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR"
  --env-secret "NEBIUS_API_KEY=$TOKEN_FACTORY_SECRET_SELECTOR"
  --env-secret "TAVILY_API_KEY=$TAVILY_SECRET_SELECTOR"
  --auth none
  --public
  --format json
)

"${CREATE_CMD[@]}"
