#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0}"

if [[ -z "${AUTH_TOKEN:-}" && -z "${AUTH_TOKEN_SECRET:-}" ]]; then
  cat >&2 <<'EOF'
Error: set AUTH_TOKEN for a quick demo or AUTH_TOKEN_SECRET for a MysteryBox secret selector.
The MysteryBox payload key for AUTH_TOKEN_SECRET must be AUTH_TOKEN.
EOF
  exit 1
fi

if [[ -z "${NEBIUS_API_KEY:-}" && -z "${NEBIUS_API_KEY_SECRET:-}" ]]; then
  cat >&2 <<'EOF'
Error: set NEBIUS_API_KEY for a quick demo or NEBIUS_API_KEY_SECRET for a MysteryBox secret selector.
The endpoint can start without a key, but chat requests need an OpenAI-compatible LLM key.
EOF
  exit 1
fi

if [[ -z "${BIONEMO_BASE_URL:-}" ]]; then
  cat >&2 <<'EOF'
Error: set BIONEMO_BASE_URL to the running BioNeMo-compatible model service endpoint.
The full-stack agent endpoint must be wired to a model service.
EOF
  exit 1
fi

if [[ -z "${BIONEMO_API_KEY:-}" && -z "${BIONEMO_API_KEY_SECRET:-}" ]]; then
  cat >&2 <<'EOF'
Error: set BIONEMO_API_KEY or BIONEMO_API_KEY_SECRET for the BioNeMo-compatible model service.
The agent needs this bearer token to call the model service endpoint.
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
  --env "AGENT_LLM_BASE_URL=$AGENT_LLM_BASE_URL"
  --env "AGENT_MODEL_NAME=$AGENT_MODEL_NAME"
)

if [[ -n "${AUTH_TOKEN_SECRET:-}" ]]; then
  CREATE_CMD+=(--token-secret "$AUTH_TOKEN_SECRET")
else
  CREATE_CMD+=(--token "$AUTH_TOKEN")
fi

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

CREATE_CMD+=(--env "BIONEMO_BASE_URL=$BIONEMO_BASE_URL")

if [[ -n "${BIONEMO_API_KEY_SECRET:-}" ]]; then
  CREATE_CMD+=(--env-secret "BIONEMO_API_KEY=$BIONEMO_API_KEY_SECRET")
else
  CREATE_CMD+=(--env "BIONEMO_API_KEY=$BIONEMO_API_KEY")
fi

echo "Creating Nebius Serverless Endpoint: $ENDPOINT_NAME"
"${CREATE_CMD[@]}"
cat <<EOF

Endpoint created. Keep the AUTH_TOKEN value in your shell for test requests.

Get the endpoint IP:
  nebius ai endpoint get-by-name --name "$ENDPOINT_NAME" --format json
EOF
