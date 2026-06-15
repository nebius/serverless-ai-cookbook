#!/usr/bin/env bash
# Build or run the MONAI synthetic medical-imaging job locally.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/run_docker.sh [--build] [MONAI_ARGS...]

Examples:
  scripts/run_docker.sh --build --case-id local-smoke --shape 64,64,32 --device cpu
  USE_GPU=1 scripts/run_docker.sh --device cuda

Environment:
  IMAGE    Local image tag. Default: monai-medical-imaging-job:local
  USE_GPU  Set to 1 to pass --gpus all to Docker.
EOF
}

BUILD=false
ARGS=()

for arg in "$@"; do
    case "$arg" in
        --build)
            BUILD=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            ARGS+=("$arg")
            ;;
    esac
done

IMAGE="${IMAGE:-monai-medical-imaging-job:local}"

if [[ "$BUILD" == "true" ]]; then
    docker build --platform linux/amd64 -t "$IMAGE" .
fi

mkdir -p results

GPU_ARGS=()
if [[ "${USE_GPU:-0}" == "1" ]]; then
    GPU_ARGS+=(--gpus all)
fi

ENV_ARGS=()
for name in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION S3_BUCKET S3_PREFIX S3_ENDPOINT_URL; do
    if [[ -n "${!name:-}" ]]; then
        ENV_ARGS+=(-e "$name=${!name}")
    fi
done

docker run --rm \
    "${GPU_ARGS[@]}" \
    "${ENV_ARGS[@]}" \
    -v "$PWD/results:/workspace/output" \
    "$IMAGE" \
    --output-dir /workspace/output \
    "${ARGS[@]}"

