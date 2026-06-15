#!/usr/bin/env bash
set -euo pipefail

: "${BIONEMO_SERVICE_IMAGE:?BIONEMO_SERVICE_IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-service:0.1.0}"

PARENT_ID="${PARENT_ID:-}"
PLATFORM="${PLATFORM:-gpu-b200-sxm-a}"
PRESET="${PRESET:-1gpu-20vcpu-224gb}"
TIMEOUT="${TIMEOUT:-20m}"
JOB_NAME="${JOB_NAME:-self-hosted-bionemo-smoke-$(date +%s)}"
PREEMPTIBLE="${PREEMPTIBLE:-false}"

CREATE_CMD=(
  nebius ai job create
  --name "$JOB_NAME"
  --image "$BIONEMO_SERVICE_IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --timeout "$TIMEOUT"
  --container-command python3
  --args "-m bionemo_agent.service_smoke"
)

if [[ "$PREEMPTIBLE" == "true" ]]; then
  CREATE_CMD+=(--preemptible)
fi

if [[ -n "$PARENT_ID" ]]; then
  CREATE_CMD+=(--parent-id "$PARENT_ID")
fi

if [[ -n "${SUBNET_ID:-}" ]]; then
  CREATE_CMD+=(--subnet-id "$SUBNET_ID")
fi

echo "Submitting self-hosted BioNeMo-compatible service GPU smoke job: $JOB_NAME"
"${CREATE_CMD[@]}"

GET_CMD=(nebius ai job get-by-name --name "$JOB_NAME" --format "jsonpath={.metadata.id}")
if [[ -n "$PARENT_ID" ]]; then
  GET_CMD+=(--parent-id "$PARENT_ID")
fi

JOB_ID="$("${GET_CMD[@]}")"
echo "$JOB_ID"
echo "Follow logs with: nebius ai logs $JOB_ID --follow --timestamps"
