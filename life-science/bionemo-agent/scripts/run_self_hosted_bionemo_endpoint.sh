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

CREATE_CMD=(
  nebius ai endpoint create
  --name "$ENDPOINT_NAME"
  --image "$BIONEMO_SERVICE_IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --container-port 8000
  --public
  --auth token
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

echo "Creating self-hosted BioNeMo-compatible GPU endpoint: $ENDPOINT_NAME"
"${CREATE_CMD[@]}"
cat <<EOF

Endpoint created. Set BIONEMO_BASE_URL to http://<public-endpoint> after it reaches RUNNING.
EOF
