#!/usr/bin/env bash
# Usage: bash job.sh smoke|full [dry-run]
set -euo pipefail

run_mode=${1:-}
case "$run_mode" in smoke|full) ;; *) echo "usage: bash job.sh smoke|full [dry-run]" >&2; exit 2 ;; esac
case ${2:-} in ''|dry-run) ;; *) echo "only dry-run is supported as a second argument" >&2; exit 2 ;; esac

: "${NEBIUS_PROFILE:?set NEBIUS_PROFILE}"
: "${NEBIUS_PROJECT_ID:?set NEBIUS_PROJECT_ID}"
: "${NEBIUS_SUBNET_ID:?set NEBIUS_SUBNET_ID}"
: "${NEBIUS_BUCKET_ID:?set NEBIUS_BUCKET_ID}"
: "${NEBIUS_IMAGE:?set NEBIUS_IMAGE}"
: "${RUN_NAME:?set RUN_NAME}"
[[ $RUN_NAME =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || { echo "invalid RUN_NAME" >&2; exit 2; }

platform=${NEBIUS_GPU_PLATFORM:-gpu-h200-sxm}
case "$platform" in
  gpu-h100-sxm|gpu-h200-sxm) preset=1gpu-16vcpu-200gb ;;
  gpu-rtx6000|gpu-rtx6000-a) preset=1gpu-24vcpu-218gb ;;
  gpu-b200-sxm|gpu-b200-sxm-a) preset=1gpu-20vcpu-224gb ;;
  *) echo "unsupported NEBIUS_GPU_PLATFORM: $platform" >&2; exit 2 ;;
esac

command=(nebius ai job create --profile "$NEBIUS_PROFILE"
  --parent-id "$NEBIUS_PROJECT_ID" --subnet-id "$NEBIUS_SUBNET_ID"
  --name "flux-so101-orange-$run_mode-$(date -u +%Y%m%dT%H%M%SZ)"
  --image "$NEBIUS_IMAGE" --platform "$platform" --preset "$preset"
  --volume "$NEBIUS_BUCKET_ID:/workspace/data:rw" --disk-size 200Gi
  --timeout 72h --container-command python3 --args /app/recipe/train_job.py
  --env "RUN_MODE=$run_mode" --env "RUN_NAME=$RUN_NAME"
  --env "IMAGE_REF=$NEBIUS_IMAGE"
  --env PYTHONUNBUFFERED=1)
if [[ ${NEBIUS_PREEMPTIBLE:-0} == 1 ]]; then
  command+=(--preemptible --restart-policy never)
fi
if [[ $run_mode == full ]]; then
  full_steps=${FULL_STEPS:-10000}
  if [[ ! $full_steps =~ ^[1-9][0-9]*$ ]] || (( full_steps < 10000 || full_steps % 5000 != 0 )); then
    echo "FULL_STEPS must be at least 10000 and a multiple of 5000" >&2
    exit 2
  fi
  command+=(--env "FULL_STEPS=$full_steps")
fi
if [[ -n ${NEBIUS_HF_TOKEN_SECRET:-} ]]; then
  command+=(--env-secret "HF_TOKEN=$NEBIUS_HF_TOKEN_SECRET")
fi
if [[ -n ${WANDB_API_KEY:-} ]]; then
  command+=(--env-secret "WANDB_API_KEY=$WANDB_API_KEY"
    --env "WANDB_PROJECT=${WANDB_PROJECT:-flux-so101-orange}")
  if [[ -n ${WANDB_ENTITY:-} ]]; then
    command+=(--env "WANDB_ENTITY=$WANDB_ENTITY")
  fi
elif [[ -n ${WANDB_PROJECT:-} || -n ${WANDB_ENTITY:-} ]]; then
  echo "set WANDB_API_KEY to the Nebius secret selector to enable W&B tracking" >&2
  exit 2
fi

if [[ ${2:-} == dry-run ]]; then
  "${command[@]}" --dry-run
else
  "${command[@]}" --async
fi
