#!/bin/sh
set -eu
workspace_root="${BIONEMO_WORKSPACE_ROOT:-/workspace/shared}"
artifact_root="${BIONEMO_ARTIFACT_ROOT:-$workspace_root/bionemo-artifacts}"
mkdir -p /data/db /workspace "$workspace_root" "$artifact_root" /app/uploads /app/logs

# Serverless instances may be restarted while retaining their local disk.  Use
# stable, per-deployment credentials so existing sessions and encrypted
# settings remain usable after that restart.  The seed comes from the mounted
# Token Factory credential and never leaves this process.
if [ -n "${NEBIUS_API_KEY:-}" ]; then
  derive_secret() {
    printf '%s' "$1:${NEBIUS_API_KEY}" | sha256sum | awk '{print $1}'
  }
  export CREDS_KEY="${CREDS_KEY:-$(derive_secret librechat-creds-key)}"
  export CREDS_IV="${CREDS_IV:-$(derive_secret librechat-creds-iv | cut -c1-32)}"
  export JWT_SECRET="${JWT_SECRET:-$(derive_secret librechat-jwt)}"
  export JWT_REFRESH_SECRET="${JWT_REFRESH_SECRET:-$(derive_secret librechat-refresh-jwt)}"
fi

if [ ! -f /data/db/WiredTiger ]; then mongod --dbpath /data/db --bind_ip 127.0.0.1 --fork --logpath /data/mongod.log --noauth; else mongod --dbpath /data/db --bind_ip 127.0.0.1 --fork --logpath /data/mongod.log --noauth; fi
node /app/seed-workbench.js
exec node /app/api/server/index.js
