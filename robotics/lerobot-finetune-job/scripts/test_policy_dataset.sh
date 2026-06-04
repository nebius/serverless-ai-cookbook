#!/usr/bin/env bash
set -euo pipefail

# Hardcoded smoke commands for quick local validation (CPU via Docker).
# Requires HF_TOKEN set for the gated dataset; otherwise those two commands will fail.
# Steps are fixed at 20.

export IMAGE="${IMAGE:-lerobot-finetune:dev}"

echo "Running hardcoded smoke tests with image: $IMAGE"
echo ""

echo "==== act / lerobot/pusht (rebuild) ===="
BATCH_SIZE=4 bash scripts/run_docker.sh --rebuild act lerobot/pusht 20
echo ""

echo "==== diffusion / lerobot/pusht ===="
BATCH_SIZE=4 bash scripts/run_docker.sh diffusion lerobot/pusht 20
echo ""

echo "==== act / lerobot/aloha_sim_transfer_cube_human ===="
HF_TOKEN="${HF_TOKEN:-}" NUM_WORKERS=0 BATCH_SIZE=2 \
  bash scripts/run_docker.sh act lerobot/aloha_sim_transfer_cube_human 20
echo ""

echo "==== diffusion / lerobot/aloha_sim_transfer_cube_human ===="
HF_TOKEN="${HF_TOKEN:-}" NUM_WORKERS=0 BATCH_SIZE=2 \
  bash scripts/run_docker.sh diffusion lerobot/aloha_sim_transfer_cube_human 20
echo ""

echo "Done."
