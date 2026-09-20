#!/usr/bin/env bash
# Cosmos 3 synthetic-data job launcher: starts vLLM-Omni in the background, fetches the
# batch driver and (if PROMPTS is unset) the sample prompt list, renders, then exits so the
# job — and billing — stops. Runs inside vllm/vllm-omni:cosmos3.
set -euo pipefail
export MODEL="${MODEL:-nvidia/Cosmos3-Nano}"
export OUTPUT_DIR="${OUTPUT_DIR:-/data/output}"
COOKBOOK_RAW="${COOKBOOK_RAW:-https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/main}"
SRC="$COOKBOOK_RAW/templates/job-cosmos3-synthetic-data/src"
WORK=/tmp/cosmos3-sdg; mkdir -p "$WORK"; cd "$WORK"

curl -fsSL "$SRC/generate.py" -o generate.py
if [ -z "${PROMPTS:-}" ]; then curl -fsSL "$SRC/prompts.jsonl" -o prompts.jsonl; export PROMPTS="$WORK/prompts.jsonl"; fi

GUARD=--no-guardrails
if [ "${GUARDRAILS:-false}" = "true" ]; then GUARD=""; fi   # needs HF_TOKEN with access to nvidia/Cosmos-1.0-Guardrail

echo "starting vLLM-Omni for $MODEL (guardrails: ${GUARDRAILS:-false})"
# shellcheck disable=SC2086
vllm serve "$MODEL" --omni --model-class-name Cosmos3OmniDiffusersPipeline $GUARD \
  --host 127.0.0.1 --port 8000 --init-timeout 1800 > "$WORK/server.log" 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

# surface server failures instead of waiting 40 minutes for nothing
( while kill -0 $SERVER_PID 2>/dev/null; do sleep 15; done; echo "vLLM-Omni exited — last log lines:"; tail -30 "$WORK/server.log" ) &

python3 generate.py
