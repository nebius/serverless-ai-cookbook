#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID to the customer project ID}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID to a subnet in that project}"
: "${SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR:?Set SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR to a MysteryBox secret whose payload key is SCIENTIFIC_MODELS_API_KEY}"
: "${TOKEN_FACTORY_SECRET_SELECTOR:?Set TOKEN_FACTORY_SECRET_SELECTOR to a MysteryBox secret whose payload key is NEBIUS_API_KEY}"
: "${TAVILY_SECRET_SELECTOR:?Set TAVILY_SECRET_SELECTOR to a MysteryBox secret whose payload key is TAVILY_API_KEY}"
# New deployments get the tested public skills release by default. An explicit
# IMAGE still selects a separately qualified customer/runtime override.
DEPLOY_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=release-image.sh
source "$DEPLOY_SCRIPT_DIR/release-image.sh"
IMAGE="${IMAGE:-$SCIENTIFIC_AI_RELEASE_IMAGE}"

# One user-owned supervisor, not a distributed lock on an S3 mount.
case "${SCIENTIFIC_STUDY_OWNER_MODE:-}" in
  first-instance|stopped-predecessor) ;;
  *) printf '%s\n' 'Set SCIENTIFIC_STUDY_OWNER_MODE=first-instance only after confirming no active supervisor for this user, or stopped-predecessor after stopping its exact previous instance. Preserve bucket/receipts. Overlapping same-user supervisors are unsupported.' >&2; exit 2 ;;
esac
: "${SEED_DEFAULT_USER_EMAIL:?Durable studies require one configured dedicated user}"
: "${TEAM_BUCKET_NAME:?Durable studies require a persistent customer bucket mount}"

case "${SERVERLESS_PUBLIC_IP:-true}" in
  true|false) ;;
  *) printf '%s\n' 'SERVERLESS_PUBLIC_IP must be true or false.' >&2; exit 2 ;;
esac

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
  --env "SCIENTIFIC_STUDY_OWNER_MODE=$SCIENTIFIC_STUDY_OWNER_MODE"
  # Product-owner-approved default. Keep overrides explicit and never change the
  # fallback model without approval.
  --env "SCIENTIFIC_CHAT_MODEL=${SCIENTIFIC_CHAT_MODEL:-zai-org/GLM-5.3-Flash}"
  --env "SCIENTIFIC_CHAT_REASONING_EFFORT=${SCIENTIFIC_CHAT_REASONING_EFFORT:-}"
  --env "SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS=${SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS:-}"
  --env "SCIENTIFIC_CHAT_MAX_OUTPUT_TOKENS=${SCIENTIFIC_CHAT_MAX_OUTPUT_TOKENS:-16384}"
  --env "SCIENTIFIC_CONTEXT_AUDIT_PATH=${SCIENTIFIC_CONTEXT_AUDIT_PATH:-}"
  --env-secret "SCIENTIFIC_MODELS_API_KEY=$SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR"
  --env-secret "NEBIUS_API_KEY=$TOKEN_FACTORY_SECRET_SELECTOR"
  --env-secret "TAVILY_API_KEY=$TAVILY_SECRET_SELECTOR"
  --auth none
  --format json
)
if [[ "${SERVERLESS_PUBLIC_IP:-true}" == true ]]; then
  CREATE_CMD+=(--public)
else
  CREATE_CMD+=(--public=false)
fi

# Mount only user files on Object Storage. Mongo and credential encryption state
# remain on the endpoint disk; they must never use the S3/FUSE mount.
if [[ -n "${TEAM_BUCKET_NAME:-}" ]]; then
  : "${S3_CREDENTIAL_SECRET_SELECTOR:?Set the MysteryBox selector with S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY}"
  : "${TEAM_ID:?Set TEAM_ID for the mounted workspace owner}"
  # The CLI loads regional endpoint settings from this local AWS profile, then
  # replaces its credentials with the selected MysteryBox secret. Operator
  # machines are not required to call that profile "default".
  S3_AWS_PROFILE="${S3_AWS_PROFILE:-default}"
  CREATE_CMD+=(--volume "s3://${TEAM_BUCKET_NAME}:/workspace:rw:${S3_AWS_PROFILE}@${S3_CREDENTIAL_SECRET_SELECTOR}"
    --env "TEAM_ID=$TEAM_ID" --env "TEAM_BUCKET_NAME=$TEAM_BUCKET_NAME")
fi

if [[ -n "${SEED_DEFAULT_USER_EMAIL:-}" ]]; then
  : "${USER_PASSWORD_SECRET_SELECTOR:?Set the MysteryBox selector containing SEED_DEFAULT_USER_PASSWORD}"
  CREATE_CMD+=(--env "SEED_DEFAULT_USER_EMAIL=$SEED_DEFAULT_USER_EMAIL"
    --env-secret "SEED_DEFAULT_USER_PASSWORD=$USER_PASSWORD_SECRET_SELECTOR"
    --env "ALLOW_REGISTRATION=false")
fi
if [[ -n "${SSH_PUBLIC_KEY_FILE:-}" ]]; then
  if [[ "${SERVERLESS_PUBLIC_IP:-true}" == false ]]; then
    printf '%s\n' 'SSH_PUBLIC_KEY_FILE is set: SSH access can allocate a public IP even with SERVERLESS_PUBLIC_IP=false. Unset SSH_PUBLIC_KEY_FILE for a private-only deployment.' >&2
  fi
  CREATE_CMD+=(--ssh-key "$(<"$SSH_PUBLIC_KEY_FILE")")
fi

"${CREATE_CMD[@]}"
