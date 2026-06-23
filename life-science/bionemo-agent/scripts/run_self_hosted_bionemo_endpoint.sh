#!/usr/bin/env bash
set -euo pipefail

: "${BIONEMO_SERVICE_IMAGE:?BIONEMO_SERVICE_IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-service:0.1.0}"

if [[ -z "${AUTH_TOKEN:-}" && -z "${AUTH_TOKEN_SECRET:-}" ]]; then
  cat >&2 <<'EOF'
Error: set AUTH_TOKEN for a quick demo or AUTH_TOKEN_SECRET for a MysteryBox secret selector.
The MysteryBox payload key for AUTH_TOKEN_SECRET must be AUTH_TOKEN.
EOF
  exit 1
fi

PARENT_ID="${PARENT_ID:-}"
PLATFORM="${PLATFORM:-gpu-b200-sxm-a}"
PRESET="${PRESET:-1gpu-20vcpu-224gb}"
ENDPOINT_NAME="${BIONEMO_ENDPOINT_NAME:-self-hosted-bionemo-demo}"
BIONEMO_MODEL_SERVICE_MODE="${BIONEMO_MODEL_SERVICE_MODE:-demo}"
BIONEMO_REQUIRE_GPU="${BIONEMO_REQUIRE_GPU:-true}"
BIONEMO_HEALTH_STRICT="${BIONEMO_HEALTH_STRICT:-true}"

CREATE_CMD=(
  nebius ai endpoint create
  --name "$ENDPOINT_NAME"
  --image "$BIONEMO_SERVICE_IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --container-port 8000
  --public
  --auth token
  --env "BIONEMO_MODEL_SERVICE_MODE=$BIONEMO_MODEL_SERVICE_MODE"
  --env "BIONEMO_REQUIRE_GPU=$BIONEMO_REQUIRE_GPU"
  --env "BIONEMO_HEALTH_STRICT=$BIONEMO_HEALTH_STRICT"
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

while IFS='=' read -r name _; do
  if [[ "$name" == BIONEMO_MODEL_*_URL || "$name" == BIONEMO_MODEL_*_API_KEY ]]; then
    CREATE_CMD+=(--env "$name=${!name}")
  fi
done < <(env | sort)

echo "Creating self-hosted BioNeMo-compatible GPU endpoint: $ENDPOINT_NAME"
"${CREATE_CMD[@]}"
cat <<EOF

Endpoint created. Set BIONEMO_BASE_URL to http://<public-endpoint> after it reaches RUNNING.
EOF
