#!/bin/bash
# Build the lerobot-finetune image and run a local smoke test.
#
# Mounts train/ and configs/ from the host so you can edit run.py without rebuilding.
# Outputs go to ./lerobot-outputs/ on the host.
#
# Usage:
#   ./scripts/run_docker.sh [--rebuild] [POLICY] [DATASET] [STEPS]
#
# Examples:
#   ./scripts/run_docker.sh                                    # skip build, run act / lerobot/pusht / 50
#   ./scripts/run_docker.sh --rebuild                          # rebuild image, then run defaults
#   ./scripts/run_docker.sh --rebuild diffusion lerobot/pusht 100
#
# Environment variables:
#   IMAGE          Override the image tag (default: lerobot-finetune:dev)
#   HF_TOKEN       HuggingFace token (for private datasets)
#   WANDB_API_KEY  If set, passed into the container; train/run.py enables W&B

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE="${IMAGE:-lerobot-finetune:dev}"
REBUILD=0
if [ "${1:-}" = "--rebuild" ]; then
  REBUILD=1
  shift
fi

POLICY="${1:-act}"
DATASET="${2:-lerobot/pusht}"
STEPS="${3:-50}"
BATCH_SIZE="${BATCH_SIZE:-}"

mkdir -p "${REPO_ROOT}/lerobot-outputs"

if [ "$REBUILD" -eq 1 ]; then
  echo "Rebuilding image: $IMAGE"
  docker build --platform linux/amd64 -t "$IMAGE" "$REPO_ROOT"
else
  echo "Skipping build — using existing image: $IMAGE"
fi

echo ""
echo "Running smoke test (CPU, $STEPS steps)"
echo "  Policy:  $POLICY"
echo "  Dataset: $DATASET"
echo "  Steps:   $STEPS"
echo "  Host mounts: train/ configs/ -> container (edit run.py without rebuild)"
echo "  Outputs:     ${REPO_ROOT}/lerobot-outputs/"
if [ -n "${WANDB_API_KEY:-}" ]; then
  echo "  W&B:         WANDB_API_KEY will be passed (logging enabled in train/run.py)"
fi
echo ""
echo "Note: 'Using device: cpu' is expected on a macOS or GPU-less host."
echo "      GPU will be used automatically in the serverless job."
echo ""

docker run --rm \
  --platform linux/amd64 \
  --shm-size 2g \
  -v "${REPO_ROOT}/train:/lerobot/train" \
  -v "${REPO_ROOT}/configs:/lerobot/configs" \
  -v "${REPO_ROOT}/lerobot-outputs:/lerobot/outputs" \
  ${HF_TOKEN:+--env "HF_TOKEN=$HF_TOKEN"} \
  ${WANDB_API_KEY:+--env "WANDB_API_KEY=$WANDB_API_KEY"} \
  "$IMAGE" \
  --policy "$POLICY" \
  --dataset "$DATASET" \
  --steps "$STEPS" \
  ${BATCH_SIZE:+--batch-size "$BATCH_SIZE"}
