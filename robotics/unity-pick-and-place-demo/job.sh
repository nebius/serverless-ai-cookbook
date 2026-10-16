#!/usr/bin/env bash
set -euo pipefail
case ${1:-submit} in submit|dry-run) ;; *) echo 'usage: bash job.sh [submit|dry-run]' >&2; exit 2 ;; esac
: "${NEBIUS_IMAGE:?set NEBIUS_IMAGE}"
: "${NEBIUS_BUCKET_ID:?set NEBIUS_BUCKET_ID}"
: "${RUN_ID:?set a fresh RUN_ID}"
[[ $RUN_ID =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || { echo 'invalid RUN_ID' >&2; exit 2; }
command=(nebius ai job create --name "unity-$RUN_ID" --image "$NEBIUS_IMAGE"
  --platform gpu-l40s-a --preset 1gpu-8vcpu-32gb --disk-size 50Gi
  --timeout 15m --restart-policy never
  --volume "$NEBIUS_BUCKET_ID:/results:rw"
  --env NVIDIA_DRIVER_CAPABILITIES=all
  --env "OUTPUT_DIR=/results/unity-articulations/$RUN_ID" --env "RUN_SECONDS=${RUN_SECONDS:-180}")
[[ -z ${NEBIUS_SUBNET_ID:-} ]] || command+=(--subnet-id "$NEBIUS_SUBNET_ID")
[[ -z ${NEBIUS_PROJECT_ID:-} ]] || command+=(--parent-id "$NEBIUS_PROJECT_ID")
if [[ ${1:-submit} == dry-run ]]; then
  "${command[@]}" --dry-run
else
  "${command[@]}" --async
fi
