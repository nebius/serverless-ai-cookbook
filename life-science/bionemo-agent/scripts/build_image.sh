#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?IMAGE required, for example cr.<region>.nebius.cloud/<registry-path>/bionemo-agent:0.1.0}"

docker build -t "$IMAGE" .
docker push "$IMAGE"
