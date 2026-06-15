#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0}"
: "${AUTH_TOKEN:?AUTH_TOKEN required. Generate one with: export AUTH_TOKEN=\$(openssl rand -hex 16)}"

if [[ -z "${NEBIUS_API_KEY:-}" && -z "${NEBIUS_API_KEY_SECRET:-}" ]]; then
  cat >&2 <<'EOF'
Error: set NEBIUS_API_KEY for a quick demo or NEBIUS_API_KEY_SECRET for a MysteryBox secret selector.
The endpoint can start without a key, but chat requests need an OpenAI-compatible LLM key.
EOF
  exit 1
fi

PARENT_ID="${PARENT_ID:-}"
PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-4vcpu-16gb}"
ENDPOINT_NAME="${ENDPOINT_NAME:-bionemo-agent}"
AGENT_LLM_BASE_URL="${AGENT_LLM_BASE_URL:-https://api.tokenfactory.us-central1.nebius.com/v1}"
AGENT_MODEL_NAME="${AGENT_MODEL_NAME:-zai-org/GLM-5}"

CREATE_CMD=(
  nebius ai endpoint create
  --name "$ENDPOINT_NAME"
  --image "$IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --container-port 8000
  --public
  --auth token
  --token "$AUTH_TOKEN"
  --env "AGENT_LLM_BASE_URL=$AGENT_LLM_BASE_URL"
  --env "AGENT_MODEL_NAME=$AGENT_MODEL_NAME"
)

if [[ -n "$PARENT_ID" ]]; then
  CREATE_CMD+=(--parent-id "$PARENT_ID")
fi

if [[ -n "${SUBNET_ID:-}" ]]; then
  CREATE_CMD+=(--subnet-id "$SUBNET_ID")
fi

if [[ -n "${NEBIUS_API_KEY_SECRET:-}" ]]; then
  CREATE_CMD+=(--env-secret "NEBIUS_API_KEY=$NEBIUS_API_KEY_SECRET")
else
  CREATE_CMD+=(--env "NEBIUS_API_KEY=$NEBIUS_API_KEY")
fi

if [[ -n "${BIONEMO_BASE_URL:-}" ]]; then
  CREATE_CMD+=(--env "BIONEMO_BASE_URL=$BIONEMO_BASE_URL")
fi

if [[ -n "${BIONEMO_API_KEY_SECRET:-}" ]]; then
  CREATE_CMD+=(--env-secret "BIONEMO_API_KEY=$BIONEMO_API_KEY_SECRET")
elif [[ -n "${BIONEMO_API_KEY:-}" ]]; then
  CREATE_CMD+=(--env "BIONEMO_API_KEY=$BIONEMO_API_KEY")
fi

echo "Creating Nebius Serverless Endpoint: $ENDPOINT_NAME"
"${CREATE_CMD[@]}"
cat <<EOF

Endpoint created. Keep the AUTH_TOKEN value in your shell for test requests.

Get the endpoint IP:
  nebius ai endpoint get-by-name --name "$ENDPOINT_NAME" --format json
EOF
