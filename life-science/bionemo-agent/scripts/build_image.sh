#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?Set IMAGE to a versioned Nebius Container Registry tag, for example cr.eu-north1.nebius.cloud/<registry>/models/bionemo-agent:3.3.2}"

if [[ "$IMAGE" != cr.*.nebius.cloud/*:* || "$IMAGE" == *@sha256:* ]]; then
  echo "IMAGE must be a versioned tag in an approved Nebius Container Registry." >&2
  exit 2
fi

OUTPUT_DIR="${OUTPUT_DIR:-.task-output/image}"
mkdir -p "$OUTPUT_DIR"

docker build \
  --pull \
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --tag "$IMAGE" \
  .

docker push "$IMAGE"
DIGEST="$(crane digest "$IMAGE")"
IMMUTABLE_IMAGE="${IMAGE%%:*}@${DIGEST}"
printf '%s\n' "$IMMUTABLE_IMAGE" >"$OUTPUT_DIR/immutable-image.txt"

docker image inspect "$IMAGE" >"$OUTPUT_DIR/image-inspect.json"

# Cataloging and the two scanner implementations are independent after the
# immutable digest is known. Keep each scanner's complete report and blocking
# gate in one lane so its cache is never accessed concurrently by two of its
# own processes. Wait for every lane so one failure cannot discard evidence
# still being produced by another.
SCAN_NAMES=(syft grype trivy)
SCAN_PIDS=()
SCAN_STATUSES=()
SCAN_STATUS_FILE="$OUTPUT_DIR/scan-status.tsv"
printf 'scanner\tpid\texit_code\n' >"$SCAN_STATUS_FILE"

(
  set -euo pipefail
  syft "$IMMUTABLE_IMAGE" -o "spdx-json=$OUTPUT_DIR/sbom.spdx.json"
) >"$OUTPUT_DIR/syft.log" 2>&1 &
SCAN_PIDS+=("$!")

(
  set -euo pipefail
  grype "$IMMUTABLE_IMAGE" -o json >"$OUTPUT_DIR/grype.json"
  # Unfixed upstream findings stay visible in the complete report. Publication
  # is blocked on critical findings for which the scanner reports a fix.
  grype "$IMMUTABLE_IMAGE" --only-fixed --fail-on critical
) >"$OUTPUT_DIR/grype.log" 2>&1 &
SCAN_PIDS+=("$!")

(
  set -euo pipefail
  trivy image --scanners vuln,secret --format json --output "$OUTPUT_DIR/trivy.json" "$IMMUTABLE_IMAGE"
  # Keep the full vulnerability/secret report, then enforce the fixable gate.
  trivy image --scanners vuln --severity CRITICAL --ignore-unfixed --exit-code 1 "$IMMUTABLE_IMAGE"
  trivy image --scanners secret --exit-code 1 "$IMMUTABLE_IMAGE"
) >"$OUTPUT_DIR/trivy.log" 2>&1 &
SCAN_PIDS+=("$!")

SCAN_FAILED=0
for INDEX in "${!SCAN_PIDS[@]}"; do
  NAME="${SCAN_NAMES[$INDEX]}"
  PID="${SCAN_PIDS[$INDEX]}"
  if wait "$PID"; then
    STATUS=0
  else
    STATUS=$?
    SCAN_FAILED=1
  fi
  SCAN_STATUSES+=("$STATUS")
  printf '%s\t%s\t%s\n' "$NAME" "$PID" "$STATUS" >>"$SCAN_STATUS_FILE"
  printf '%s scan lane exited with status %s.\n' "$NAME" "$STATUS"
done

if (( SCAN_FAILED != 0 )); then
  echo "One or more image scan lanes failed; all lane logs and completed reports were preserved in $OUTPUT_DIR." >&2
  for INDEX in "${!SCAN_PIDS[@]}"; do
    NAME="${SCAN_NAMES[$INDEX]}"
    STATUS="${SCAN_STATUSES[$INDEX]}"
    if [[ "$STATUS" != "0" ]]; then
      echo "Last 200 lines from $OUTPUT_DIR/$NAME.log:" >&2
      tail -n 200 "$OUTPUT_DIR/$NAME.log" >&2
    fi
  done
  exit 1
fi

printf '%s\n' "$IMMUTABLE_IMAGE"
cat <<EOF

Published immutable application image:
  $IMMUTABLE_IMAGE

Evidence:
  $OUTPUT_DIR/immutable-image.txt
  $OUTPUT_DIR/image-inspect.json
  $OUTPUT_DIR/sbom.spdx.json
  $OUTPUT_DIR/grype.json
  $OUTPUT_DIR/trivy.json
  $OUTPUT_DIR/scan-status.tsv
  $OUTPUT_DIR/syft.log
  $OUTPUT_DIR/grype.log
  $OUTPUT_DIR/trivy.log
EOF
