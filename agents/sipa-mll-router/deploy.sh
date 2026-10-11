#!/usr/bin/env bash
# Deploy SIPA MLL Router as a Nebius Serverless CPU Endpoint
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
IMAGE="ghcr.io/soulinpsyabstract/sipa-mll-router:latest"
ENDPOINT_NAME="sipa-mll-router"

# ── Validate ──────────────────────────────────────────────────────────────────
: "${NEBIUS_API_KEY:?Set NEBIUS_API_KEY to your Token Factory API key}"

SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')
echo "Using subnet: $SUBNET_ID"

# ── Deploy ────────────────────────────────────────────────────────────────────
echo "Creating endpoint: $ENDPOINT_NAME"
nebius ai endpoint create \
  --name "$ENDPOINT_NAME" \
  --image "$IMAGE" \
  --platform cpu \
  --preset 4vcpu-8gb \
  --env "NEBIUS_API_KEY=${NEBIUS_API_KEY}" \
  --port 8000 \
  --subnet-id "$SUBNET_ID"

# ── Wait and get IP ───────────────────────────────────────────────────────────
echo "Waiting for endpoint to become active..."
sleep 30

ENDPOINT_ID=$(nebius ai endpoint get-by-name \
  --name "$ENDPOINT_NAME" \
  --format jsonpath='{.metadata.id}')

ENDPOINT_IP=$(nebius ai endpoint get --id "$ENDPOINT_ID" \
  --format jsonpath='{.status.target_group_status.load_balancers[0].ingress_addresses[0].external_address_spec.address}')

echo "Endpoint ready: http://${ENDPOINT_IP}:8000"
echo ""
echo "Test it:"
echo "  curl -X POST http://${ENDPOINT_IP}:8000/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"message\": \"I feel overwhelmed and cannot cope\"}' | jq ."

