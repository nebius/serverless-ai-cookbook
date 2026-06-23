#!/usr/bin/env bash
set -euo pipefail

: "${BIONEMO_BASE_URL:?BIONEMO_BASE_URL required, for example http://<service-endpoint-ip>:8000}"
: "${BIONEMO_API_KEY:?BIONEMO_API_KEY required for the BioNeMo-compatible model service}"

payload="$(curl -fsS "$BIONEMO_BASE_URL/v1/models/health" \
  -H "Authorization: Bearer $BIONEMO_API_KEY")"

status="$(jq -r '.status' <<<"$payload")"
checked="$(jq -r '.checked_models' <<<"$payload")"
healthy="$(jq -r '.healthy_models' <<<"$payload")"

if [[ "$status" != "healthy" || "$checked" != "$healthy" ]]; then
  jq >&2 . <<<"$payload"
  echo "BioNeMo-compatible model service health check failed." >&2
  exit 1
fi

jq . <<<"$payload"
