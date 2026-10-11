#!/usr/bin/env bash
set -euo pipefail

python_bin="${VIRTUAL_ENV:-/opt/bioir/venv}/bin/python"

# A public endpoint needs browser authentication.  A caller can set a durable
# JUPYTER_PASSWORD in the endpoint environment; otherwise generate one and
# expose it only through the endpoint's private logs.
if [[ -z "${JUPYTER_PASSWORD:-}" ]]; then
  JUPYTER_PASSWORD="$("$python_bin" -c 'import secrets; print(secrets.token_urlsafe(24))')"
  export JUPYTER_PASSWORD
  printf 'Generated Jupyter password (shown once): %s\n' "$JUPYTER_PASSWORD" >&2
fi

password_hash="$("$python_bin" -c '
import os
from jupyter_server.auth import passwd
print(passwd(os.environ["JUPYTER_PASSWORD"]))
')"

exec jupyter lab \
  --ip=0.0.0.0 \
  --port="${JUPYTER_PORT:-8888}" \
  --no-browser \
  --ServerApp.root_dir=/workspace \
  --IdentityProvider.hashed_password="$password_hash" \
  --IdentityProvider.token='' \
  --ServerApp.allow_remote_access=True
