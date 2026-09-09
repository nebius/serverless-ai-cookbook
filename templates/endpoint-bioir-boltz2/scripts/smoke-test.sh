#!/usr/bin/env bash
set -euo pipefail

: "${ENDPOINT_URL:?Set ENDPOINT_URL to the token-protected endpoint URL.}"
: "${AUTH_TOKEN:?Set AUTH_TOKEN to the endpoint token.}"

base_url="${ENDPOINT_URL%/}"
config_file="$(mktemp)"
trap 'rm -f "$config_file"' EXIT
umask 077
printf '%s\n' \
  'fail' \
  'silent' \
  'show-error' \
  "header = \"Authorization: Bearer ${AUTH_TOKEN}\"" >"$config_file"

curl --config "$config_file" "${base_url}/healthz" | jq

for attempt in $(seq 1 "${READY_ATTEMPTS:-60}"); do
  if response="$(curl --config "$config_file" "${base_url}/readyz" 2>/dev/null)" \
    && printf '%s' "$response" | jq -e '.status == "ready"' >/dev/null; then
    printf '%s\n' "$response" | jq
    break
  fi
  if [[ "$attempt" == "${READY_ATTEMPTS:-60}" ]]; then
    echo "endpoint did not become ready before the retry limit" >&2
    exit 1
  fi
  sleep "${READY_INTERVAL_SECONDS:-15}"
done

response="$(curl --config "$config_file" \
  --header 'Content-Type: application/json' \
  --data '{"sequence":"ACKIENIKYKGKEVESKLGSQLIDIFNDLDRAKEEYDKLSSPEFIAKFGDWINDEVERNVNEDGEPLLIQDVRQDSSKHYFFILKNGERFDLLTR"}' \
  "${base_url}/v1/fold")"
printf '%s' "$response" | jq -e '.model == "boltz-2" and (.cif | startswith("data_")) and (.scores | type == "object")' >/dev/null
printf '%s\n' "$response" | jq '{request_id, model, model_inference_time_seconds, total_time_seconds, score_keys: (.scores | keys)}'
