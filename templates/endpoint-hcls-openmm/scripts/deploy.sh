#!/usr/bin/env bash
set -euo pipefail

: "${NEBIUS_PROJECT_ID:?Set NEBIUS_PROJECT_ID to the customer project ID}"
: "${NEBIUS_SUBNET_ID:?Set NEBIUS_SUBNET_ID to a subnet in that project}"
: "${HCLS_STORAGE_SOURCE:?Set HCLS_STORAGE_SOURCE to s3://BUCKET or a computefilesystem-* resource ID}"
: "${NGC_API_KEY_SECRET_SELECTOR:?Set NGC_API_KEY_SECRET_SELECTOR to a MysteryBox secret whose payload key is NGC_API_KEY}"

HCLS_IMAGE="${HCLS_IMAGE:-cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/openmm-md-api:20260908-dynamic-v3}"
OPENMM_VERSION="${OPENMM_VERSION:-latest}"

case "$HCLS_STORAGE_SOURCE" in
  s3://*)
    : "${S3_CREDENTIAL_SECRET_SELECTOR:?For s3:// storage, set S3_CREDENTIAL_SECRET_SELECTOR to a MysteryBox secret containing S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY}"
    : "${AWS_CONFIG_FILE:?For s3:// storage, set AWS_CONFIG_FILE to a readable AWS config containing the selected S3 profile, region, and endpoint_url}"
    [[ -r "$AWS_CONFIG_FILE" ]] || { echo "AWS_CONFIG_FILE is not readable" >&2; exit 2; }
    S3_PROFILE="${S3_PROFILE:-default}"
    HCLS_VOLUME="${HCLS_STORAGE_SOURCE}:/mnt/hcls:rw:${S3_PROFILE}@${S3_CREDENTIAL_SECRET_SELECTOR}"
    ;;
  computefilesystem-*) HCLS_VOLUME="${HCLS_STORAGE_SOURCE}:/mnt/hcls:rw" ;;
  *)
    echo "HCLS_STORAGE_SOURCE must be s3://BUCKET or start with computefilesystem-" >&2
    exit 2
    ;;
esac

CREATE_CMD=(nebius ai endpoint create
  --parent-id "$NEBIUS_PROJECT_ID"
  --name "${ENDPOINT_NAME:-hcls-openmm-rest-mcp}"
  --image "$HCLS_IMAGE"
  --container-port 8000
  --platform "${PLATFORM:-gpu-l40s-a}"
  --preset "${PRESET:-1gpu-8vcpu-32gb}"
  --disk-size "${DISK_SIZE:-100Gi}"
  --shm-size "${SHM_SIZE:-16Gi}"
  --subnet-id "$NEBIUS_SUBNET_ID"
  --env "OPENMM_VERSION=$OPENMM_VERSION"
  --env-secret "NGC_API_KEY=$NGC_API_KEY_SECRET_SELECTOR"
  --auth token
  --volume "$HCLS_VOLUME"
  --public
  --format json)

if [[ -n "${AUTH_TOKEN_SECRET_SELECTOR:-}" && -n "${AUTH_TOKEN:-}" ]]; then
  echo "Set only one of AUTH_TOKEN_SECRET_SELECTOR or AUTH_TOKEN" >&2
  exit 2
fi

GENERATED_AUTH_TOKEN=""
if [[ -n "${AUTH_TOKEN_SECRET_SELECTOR:-}" ]]; then
  CREATE_CMD+=(--token-secret "$AUTH_TOKEN_SECRET_SELECTOR")
elif [[ -n "${AUTH_TOKEN:-}" ]]; then
  CREATE_CMD+=(--token "$AUTH_TOKEN")
else
  GENERATED_AUTH_TOKEN="$(openssl rand -hex 32)"
  CREATE_CMD+=(--token "$GENERATED_AUTH_TOKEN")
fi

case "${PREEMPTIBLE:-false}" in
  true|1|yes) CREATE_CMD+=(--preemptible) ;;
  false|0|no) ;;
  *) echo "PREEMPTIBLE must be true or false" >&2; exit 2 ;;
esac

"${CREATE_CMD[@]}"
if [[ -n "$GENERATED_AUTH_TOKEN" ]]; then
  printf '\nGenerated Serverless token (shown once; store it securely):\nAUTH_TOKEN=%s\n' "$GENERATED_AUTH_TOKEN" >&2
fi
