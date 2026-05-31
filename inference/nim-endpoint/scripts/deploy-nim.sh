#!/usr/bin/env bash
#
# Mirror an NVIDIA NIM image into your in-region Nebius Container Registry and
# deploy it as a Serverless AI Endpoint.
#
# Why mirror? Large NIM images (10-25GB+) often can't be pulled from nvcr.io
# inside the endpoint cold-start window, so a direct deploy fails with no logs.
# Pulling from an in-region Container Registry is fast and reliable.
#
# Usage:
#   export NIM_IMAGE="nvcr.io/nim/meta/llama-3.2-1b-instruct:1.8.6"
#   export PROJECT_ID="project-..."
#   export NGC_API_KEY="nvapi-..."
#   # optional: REGION PLATFORM PRESET DISK SUBNET_ID AUTH_TOKEN
#   ./deploy-nim.sh
#
set -euo pipefail

: "${NIM_IMAGE:?set NIM_IMAGE, e.g. nvcr.io/nim/meta/llama-3.2-1b-instruct:1.8.6}"
: "${PROJECT_ID:?set PROJECT_ID (project-...)}"
: "${NGC_API_KEY:?set NGC_API_KEY (nvapi-...)}"

REGION="${REGION:-us-central1}"
PLATFORM="${PLATFORM:-gpu-rtx6000}"
PRESET="${PRESET:-1gpu-24vcpu-218gb}"
DISK="${DISK:-150Gi}"
AUTH_TOKEN="${AUTH_TOKEN:-$(openssl rand -hex 16)}"

NIM_NAME="$(basename "${NIM_IMAGE%%:*}")"
NIM_TAG="${NIM_IMAGE##*:}"

echo ">> Resolving Container Registry 'nim-mirror' in ${PROJECT_ID} ..."
REG_ID="$(nebius registry list --parent-id "$PROJECT_ID" --format json \
  | jq -r '.items[]? | select(.metadata.name=="nim-mirror") | .metadata.id' | head -1)"
if [ -z "${REG_ID:-}" ]; then
  echo ">> Creating registry 'nim-mirror' ..."
  REG_ID="$(nebius registry create --name nim-mirror --parent-id "$PROJECT_ID" \
    --format json | jq -r '.metadata.id')"
fi
REGISTRY="cr.${REGION}.nebius.cloud/${REG_ID#registry-}"   # path = id without "registry-" prefix
TARGET="${REGISTRY}/${NIM_NAME}:${NIM_TAG}"

echo ">> Mirroring ${NIM_IMAGE} -> ${TARGET} ..."
nebius registry configure-helper
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
docker pull "$NIM_IMAGE"
docker tag  "$NIM_IMAGE" "$TARGET"
docker push "$TARGET"

SUBNET_ID="${SUBNET_ID:-$(nebius vpc subnet list --parent-id "$PROJECT_ID" \
  --format json | jq -r '.items[0].metadata.id')}"

echo ">> Creating endpoint '${NIM_NAME}' on ${PLATFORM}/${PRESET} ..."
nebius ai endpoint create \
  --parent-id "$PROJECT_ID" \
  --name "$NIM_NAME" \
  --image "$TARGET" \
  --container-port 8000 \
  --platform "$PLATFORM" --preset "$PRESET" \
  --disk-size "$DISK" \
  --subnet-id "$SUBNET_ID" \
  --env NGC_API_KEY="$NGC_API_KEY" \
  --public --auth token --token "$AUTH_TOKEN"

cat <<EOF

>> Endpoint '${NIM_NAME}' is provisioning. Auth token: ${AUTH_TOKEN}

Wait for readiness, then call it:

  ID=\$(nebius ai endpoint get-by-name --parent-id "${PROJECT_ID}" --name "${NIM_NAME}" --format jsonpath='{.metadata.id}')
  IP=\$(nebius ai endpoint get "\$ID" --format json | jq -r '.status.public_endpoints[0]')
  # poll until {"status":"ready"}:
  curl -s "http://\$IP/v1/health/ready" -H "Authorization: Bearer ${AUTH_TOKEN}"

Cleanup:  nebius ai endpoint delete "\$ID"
EOF
