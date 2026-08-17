#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_API_KEY:?Set the TokenFactory key in NEBIUS_API_KEY}"
if [[ -z "${NVIDIA_API_KEY:-}" && -z "${NGC_API_KEY:-}" ]]; then
  echo "Set NVIDIA_API_KEY (preferred) or NGC_API_KEY." >&2
  exit 2
fi
: "${AUTH_TOKEN:?Set a random gateway token with at least 24 characters}"

if ((${#AUTH_TOKEN} < 24)); then
  echo "AUTH_TOKEN must contain at least 24 characters." >&2
  exit 2
fi

IMAGE="${IMAGE:-bionemo-agent:3.3.3-local}"
PORT="${PORT:-18789}"
STATE_VOLUME="${STATE_VOLUME:-bionemo-agent-state}"
ARTIFACT_VOLUME="${ARTIFACT_VOLUME:-bionemo-agent-artifacts}"

docker build --tag "$IMAGE" .
docker run --rm --name bionemo-agent-local \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --volume "$STATE_VOLUME:/workspace/state" \
  --volume "$ARTIFACT_VOLUME:/workspace/agent/artifacts" \
  --publish "127.0.0.1:${PORT}:18789" \
  --env NEBIUS_API_KEY \
  --env NVIDIA_API_KEY \
  --env NGC_API_KEY \
  --env AUTH_TOKEN \
  --env BIONEMO_HTTPS_MODE=local \
  --env BIONEMO_ENABLE_HTTPS_TUNNEL=false \
  "$IMAGE"
