#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?Set IMAGE to a versioned Nebius Container Registry tag, for example cr.eu-north1.nebius.cloud/<registry>/models/bionemo-agent:3.2.3}"

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

docker image inspect "$IMAGE" >"$OUTPUT_DIR/image-inspect.json"
syft "$IMMUTABLE_IMAGE" -o "spdx-json=$OUTPUT_DIR/sbom.spdx.json"
grype "$IMMUTABLE_IMAGE" -o json >"$OUTPUT_DIR/grype.json"
trivy image --scanners vuln,secret --format json --output "$OUTPUT_DIR/trivy.json" "$IMMUTABLE_IMAGE"

# Unfixed upstream findings stay visible in both complete reports. Publication
# is blocked on critical findings for which the scanner reports a fix.
grype "$IMMUTABLE_IMAGE" --only-fixed --fail-on critical
trivy image --scanners vuln --severity CRITICAL --ignore-unfixed --exit-code 1 "$IMMUTABLE_IMAGE"

printf '%s\n' "$IMMUTABLE_IMAGE" | tee "$OUTPUT_DIR/immutable-image.txt"
cat <<EOF

Published immutable application image:
  $IMMUTABLE_IMAGE

Evidence:
  $OUTPUT_DIR/image-inspect.json
  $OUTPUT_DIR/sbom.spdx.json
  $OUTPUT_DIR/grype.json
  $OUTPUT_DIR/trivy.json
EOF
