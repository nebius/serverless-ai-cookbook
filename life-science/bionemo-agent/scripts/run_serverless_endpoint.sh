#!/usr/bin/env bash
set -euo pipefail

VARIANT="${1:-}"
if [[ "$VARIANT" != "nvidia" && "$VARIANT" != "tokenfactory" ]] || (( $# != 1 )); then
  echo "Usage: $0 nvidia|tokenfactory" >&2
  exit 2
fi

: "${AUTH_TOKEN_SECRET:?Set AUTH_TOKEN_SECRET to a MysteryBox selector containing AUTH_TOKEN}"
: "${MODEL_CREDENTIALS_SECRET:?Set MODEL_CREDENTIALS_SECRET to the selected backend MysteryBox selector}"

# This public image, the application port, managed HTTPS mode, CPU shape, and
# MCP service are release invariants. Resolve the friendly tag once and pin the
# endpoint to its immutable digest so a later tag promotion cannot change a
# running deployment.
DEFAULT_IMAGE="cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/ba:latest"
IMAGE="${IMAGE:-$DEFAULT_IMAGE}"
if [[ "$IMAGE" != cr.*.nebius.cloud/*@sha256:* && "$IMAGE" != cr.*.nebius.cloud/*:* ]]; then
  echo "IMAGE must be a Nebius Container Registry tag or digest reference." >&2
  exit 2
fi
if [[ "$IMAGE" != *@sha256:* ]]; then
  command -v crane >/dev/null 2>&1 || { echo "crane is required to resolve IMAGE to an immutable digest." >&2; exit 2; }
  IMAGE_REPOSITORY="${IMAGE%:*}"
  IMAGE="${IMAGE_REPOSITORY}@$(crane digest "$IMAGE")"
fi

case "$VARIANT" in
  nvidia)
    ENDPOINT_NAME="${ENDPOINT_NAME:-bionemo-agent-workbench-nvidia}"
    MODEL_SECRET_ARGS=(--env-secret "NVIDIA_API_KEY=$MODEL_CREDENTIALS_SECRET")
    ;;
  tokenfactory)
    ENDPOINT_NAME="${ENDPOINT_NAME:-bionemo-agent-workbench-tokenfactory-mcp}"
    MODEL_SECRET_ARGS=(
      --env-secret "NEBIUS_API_KEY=$MODEL_CREDENTIALS_SECRET"
      --env-secret "BIONEMO_MCP_API_KEY=$MODEL_CREDENTIALS_SECRET"
    )
    ;;
esac

CREATE_CMD=(
  nebius ai endpoint create
  --name "$ENDPOINT_NAME"
  --image "$IMAGE"
  --platform cpu-d3
  --preset 4vcpu-16gb
  --disk-size 30Gi
  --container-port 18789
  --env-secret "AUTH_TOKEN=$AUTH_TOKEN_SECRET"
  "${MODEL_SECRET_ARGS[@]}"
  # The credential names select the reasoning provider and scientific backend.
  # Every other runtime default is image-owned; only managed HTTPS differs from
  # the safe generic-container default.
  --env "BIONEMO_HTTPS_MODE=nebius"
)

# A subnet is genuinely deployment-specific, but Serverless can select one
# from the active Nebius profile when this is omitted.
if [[ -n "${SUBNET_ID:-}" ]]; then CREATE_CMD+=(--subnet-id "$SUBNET_ID"); fi
if [[ -n "${TAVILY_SECRET:-}" ]]; then CREATE_CMD+=(--env-secret "TAVILY_API_KEY=$TAVILY_SECRET"); fi

echo "Creating '$ENDPOINT_NAME' ($VARIANT) on native Nebius HTTPS from $IMAGE."
"${CREATE_CMD[@]}"

cat <<EOF

The active Nebius CLI profile supplies the project automatically. The managed
endpoint has no public VM IP or second authentication layer; OpenClaw requires
the rate-limited AUTH_TOKEN as its single browser login.

Inspect the endpoint and obtain its browser URL:
  ENDPOINT_ID=\$(nebius ai endpoint get-by-name --name "$ENDPOINT_NAME" --format jsonpath='{.metadata.id}')
  nebius ai endpoint get "\$ENDPOINT_ID" --format json
EOF
