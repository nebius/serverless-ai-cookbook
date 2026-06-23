#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0}"

PARENT_ID="${PARENT_ID:-}"
PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-4vcpu-16gb}"
TIMEOUT="${TIMEOUT:-20m}"
QUERY="${QUERY:-protein sequence embedding}"
JOB_NAME="${JOB_NAME:-bionemo-agent-smoke-$(date +%s)}"
PREEMPTIBLE="${PREEMPTIBLE:-false}"

CREATE_CMD=(
  nebius ai job create
  --name "$JOB_NAME"
  --image "$IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --timeout "$TIMEOUT"
  --container-command python
  --args "-m bionemo_agent.smoke --query '$QUERY'"
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

echo "Submitting Nebius AI Job: $JOB_NAME"
"${CREATE_CMD[@]}"

GET_CMD=(nebius ai job get-by-name --name "$JOB_NAME" --format "jsonpath={.metadata.id}")
if [[ -n "$PARENT_ID" ]]; then
  GET_CMD+=(--parent-id "$PARENT_ID")
fi

JOB_ID="$("${GET_CMD[@]}")"
echo "$JOB_ID"
echo "Follow logs with: nebius ai logs $JOB_ID --follow --timestamps"
