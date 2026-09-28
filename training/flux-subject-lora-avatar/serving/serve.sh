#!/usr/bin/env bash
# Create a token-authenticated Nebius Serverless AI Endpoint serving
# FLUX.2-dev + your subject LoRA.
#
# Prereqs:
#   - the serving image is built from serving/Dockerfile and pushed to a
#     registry the endpoint can pull from (an in-region Nebius Container
#     Registry gives much faster cold starts than a cross-region pull)
#   - the winning adapter is uploaded to
#     s3://$BUCKET_NAME/$PREFIX/serving/lora.safetensors
#
# Required env: PARENT_ID, BUCKET_NAME, NB_REGION_ID, HF_TOKEN, SERVING_IMAGE
# Optional env: SUBNET_ID, BUCKET_ID, PLATFORM, PRESET, PREFIX, TRIGGER_WORD,
#               TRIGGER_CLASS, LORA_PATH,
#               AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (enables "url" mode)
set -euo pipefail

: "${PARENT_ID:?set PARENT_ID to your Nebius project id}"
: "${BUCKET_NAME:?set BUCKET_NAME to your Object Storage bucket}"
: "${NB_REGION_ID:?set NB_REGION_ID, e.g. eu-north1 or us-central1}"
: "${HF_TOKEN:?FLUX.2-dev is gated - export an HF token whose account accepted the model license}"
: "${SERVING_IMAGE:?e.g. cr.<region>.nebius.cloud/<registry-id>/flux-avatar-serving:v1}"

PLATFORM="${PLATFORM:-gpu-h200-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
PREFIX="${PREFIX:-flux-avatar}"
TRIGGER_WORD="${TRIGGER_WORD:-TOK4ME}"
TRIGGER_CLASS="${TRIGGER_CLASS:-person}"
LORA_PATH="${LORA_PATH:-/workspace/bucket/${PREFIX}/serving/lora.safetensors}"

SUBNET_ID="${SUBNET_ID:-$(nebius vpc subnet list --parent-id "$PARENT_ID" --format json | jq -r '.items[0].metadata.id')}"
BUCKET_ID="${BUCKET_ID:-$(nebius storage bucket get-by-name --name "$BUCKET_NAME" --parent-id "$PARENT_ID" --format json | jq -r '.metadata.id')}"

EP_NAME="flux-avatar-ep-$(date +%Y%m%d%H%M%S)"

# One bearer token passes both auth layers: the platform proxy (--auth token)
# and the fail-closed in-container check (API_TOKEN). Stored locally with
# 600 permissions; never commit or echo it.
AUTH_TOKEN="$(openssl rand -hex 32)"
umask 077
printf '%s' "$AUTH_TOKEN" > ./endpoint.token
echo "Bearer token written to ./endpoint.token (chmod 600)."

# NOTE: --env values are visible to project members via `nebius ai endpoint
# get`. In shared projects use MysteryBox secrets: --token-secret for the
# platform token and --env-secret for HF_TOKEN / API_TOKEN / AWS keys.
EXTRA_ARGS=()
if [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  EXTRA_ARGS+=(
    --env "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}"
    --env "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}"
    --env "S3_BUCKET=${BUCKET_NAME}"
    --env "S3_ENDPOINT_URL=https://storage.${NB_REGION_ID}.nebius.cloud"
    --env "S3_PREFIX=${PREFIX}/generated/"
  )
  echo "Object Storage credentials detected: response_format=url enabled."
else
  echo "No AWS credentials in env: endpoint will support base64 responses only."
fi

echo "Creating endpoint ${EP_NAME} (create blocks until scheduled)..."
nebius ai endpoint create \
  --name "$EP_NAME" \
  --parent-id "$PARENT_ID" \
  --subnet-id "$SUBNET_ID" \
  --image "$SERVING_IMAGE" \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --disk-size 300Gi \
  --container-port 8000 \
  --auth token \
  --token "$AUTH_TOKEN" \
  --volume "${BUCKET_ID}:/workspace/bucket:ro" \
  --env "MODEL_ID=black-forest-labs/FLUX.2-dev" \
  --env "LORA_PATH=${LORA_PATH}" \
  --env "TRIGGER_WORD=${TRIGGER_WORD}" \
  --env "TRIGGER_CLASS=${TRIGGER_CLASS}" \
  --env "HF_TOKEN=${HF_TOKEN}" \
  --env "API_TOKEN=${AUTH_TOKEN}" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

EP_ID=$(nebius ai endpoint get-by-name --parent-id "$PARENT_ID" \
  --name "$EP_NAME" --format json | jq -r '.metadata.id')
cat <<EOF

Endpoint : $EP_NAME
ID       : $EP_ID

Cold start is ~15-30 minutes (image pull + ~90 GB model download + load).
Poll until state=RUNNING, then until /healthz reports ready=true:

  nebius ai endpoint get $EP_ID --format json | jq -r .status.state
  EP_URL=\$(nebius ai endpoint get $EP_ID --format json | jq -r '.status.public_endpoints[0]')
  curl -s "\$EP_URL/healthz" -H "Authorization: Bearer \$(cat ./endpoint.token)"

IMPORTANT: the HTTPS hostname in .status.public_endpoints[0] changes every
time the endpoint is stopped and started again - always re-resolve it, never
hardcode it.

Smoke test (base64 response decoded to out.png):

  curl -s -X POST "\$EP_URL/generate" \\
    -H "Authorization: Bearer \$(cat ./endpoint.token)" \\
    -H "Content-Type: application/json" \\
    -d '{"prompt": "${TRIGGER_WORD} ${TRIGGER_CLASS}, studio portrait, natural skin texture", "seed": 42}' \\
    | python3 -c 'import base64, json, sys; open("out.png", "wb").write(base64.b64decode(json.load(sys.stdin)["image_base64"]))'

Verify auth fails closed (expect 401):

  curl -s -o /dev/null -w '%{http_code}\n' -X POST "\$EP_URL/generate" -d '{}'

The endpoint bills per second while RUNNING. Stop it when idle - it keeps its
ID, token, and adapter, and restarts in ~15-30 min:

  nebius ai endpoint stop $EP_ID
  nebius ai endpoint start $EP_ID
EOF
