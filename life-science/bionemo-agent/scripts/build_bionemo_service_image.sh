#!/usr/bin/env bash
set -euo pipefail

: "${BIONEMO_SERVICE_IMAGE:?BIONEMO_SERVICE_IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-service:0.1.0}"

docker build -f self-hosted-bionemo/Dockerfile -t "$BIONEMO_SERVICE_IMAGE" .
docker push "$BIONEMO_SERVICE_IMAGE"

