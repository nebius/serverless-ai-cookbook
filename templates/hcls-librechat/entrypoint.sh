#!/bin/sh
set -eu

DATA_DIR="${LIBRECHAT_DATA_DIR:-/data/hcls-librechat}"
MONGO_DATA_DIR="${LIBRECHAT_MONGO_DATA_DIR:-/data/db}"
RUNTIME_SECRETS="$DATA_DIR/runtime-secrets.env"

mkdir -p "$DATA_DIR" "$MONGO_DATA_DIR" /app/uploads /app/logs
umask 077

secret_hex() {
  bytes="$1"
  od -An -N "$bytes" -tx1 /dev/urandom | tr -d ' \n'
}

if [ ! -s "$RUNTIME_SECRETS" ]; then
  {
    printf 'CREDS_KEY=%s\n' "$(secret_hex 32)"
    printf 'CREDS_IV=%s\n' "$(secret_hex 16)"
    printf 'JWT_SECRET=%s\n' "$(secret_hex 32)"
    printf 'JWT_REFRESH_SECRET=%s\n' "$(secret_hex 32)"
  } > "$RUNTIME_SECRETS"
fi

set -a
# The generated path is deployment-local state.
# shellcheck disable=SC1090
. "$RUNTIME_SECRETS"
set +a

node /opt/hcls-librechat/render-config.mjs "$CONFIG_PATH"

mongod \
  --dbpath "$MONGO_DATA_DIR" \
  --bind_ip 127.0.0.1 \
  --port 27017 \
  --fork \
  --logpath "$DATA_DIR/mongod.log" \
  --noauth

node /app/seed-hcls-workbench.js

# Deployment-only convenience (set SEED_DEFAULT_USER_EMAIL/PASSWORD to use).
if [ -n "${SEED_DEFAULT_USER_EMAIL:-}" ] && [ -n "${SEED_DEFAULT_USER_PASSWORD:-}" ]; then
  node /opt/hcls-librechat/seed-user.js
fi

exec node /app/api/server/index.js
