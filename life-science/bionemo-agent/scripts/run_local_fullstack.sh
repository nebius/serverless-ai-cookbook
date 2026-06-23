#!/usr/bin/env bash
set -euo pipefail

# Run the full stack locally with no Nebius resources:
#   1. start the self-hosted BioNeMo-compatible service in a container,
#   2. serve the NeMo Agent Toolkit agent against it,
#   3. send one research-only /generate request that drives a live tool call.
#
# This is the cheapest way to validate the agent -> service -> LLM path before
# creating any GPU endpoint. The service image is CUDA-based but starts on CPU;
# nvidia-smi simply reports unavailable in the health payload.
#
# Requirements: docker, uv, jq, openssl, and an OpenAI-compatible LLM key.

: "${NEBIUS_API_KEY:?Set NEBIUS_API_KEY to a TokenFactory or OpenAI-compatible LLM key.}"

BIONEMO_SERVICE_IMAGE="${BIONEMO_SERVICE_IMAGE:-bionemo-service:local}"
SERVICE_PORT="${SERVICE_PORT:-18080}"
AGENT_PORT="${AGENT_PORT:-8000}"
QUERY="${QUERY:-Use the BioNeMo protein_embedding skill on public sequence MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP and summarize the nonclinical result.}"

SERVICE_TOKEN="$(openssl rand -hex 16)"
SERVICE_CID=""
AGENT_PID=""

cleanup() {
  [[ -n "$AGENT_PID" ]] && kill "$AGENT_PID" 2>/dev/null || true
  [[ -n "$SERVICE_CID" ]] && docker rm -f "$SERVICE_CID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Building the self-hosted BioNeMo-compatible service image"
docker build -f self-hosted-bionemo/Dockerfile -t "$BIONEMO_SERVICE_IMAGE" .

echo "==> Starting the service container on port ${SERVICE_PORT}"
SERVICE_CID="$(docker run -d -p "${SERVICE_PORT}:8000" \
  -e BIONEMO_SERVICE_API_KEY="$SERVICE_TOKEN" "$BIONEMO_SERVICE_IMAGE")"

for _ in $(seq 1 40); do
  curl -sf "http://localhost:${SERVICE_PORT}/health" >/dev/null 2>&1 && break
  sleep 0.5
done
echo "    service health: $(curl -sf "http://localhost:${SERVICE_PORT}/health" | jq -c '{status}')"

echo "==> Installing agent dependencies"
uv sync

echo "==> Serving the agent on port ${AGENT_PORT}"
BIONEMO_BASE_URL="http://localhost:${SERVICE_PORT}" \
BIONEMO_API_KEY="$SERVICE_TOKEN" \
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  uv run nat serve --config_file configs/config.yml \
  --host 0.0.0.0 --port "${AGENT_PORT}" >/tmp/bionemo_fullstack_agent.log 2>&1 &
AGENT_PID=$!

for _ in $(seq 1 60); do
  curl -sf "http://localhost:${AGENT_PORT}/docs" >/dev/null 2>&1 && break
  sleep 1
done

echo "==> Sending one research-only /generate request"
curl -sS "http://localhost:${AGENT_PORT}/generate" \
  -H "Content-Type: application/json" \
  -d "{\"input_message\": $(jq -Rn --arg q "$QUERY" '$q')}" \
  --max-time 180 | jq

echo
echo "==> Service access log (look for POST /v1/embeddings/protein 200):"
docker logs "$SERVICE_CID" 2>&1 | grep -E "POST|GET" | tail -5 || true
echo "==> Done. Local stack is torn down on exit."
