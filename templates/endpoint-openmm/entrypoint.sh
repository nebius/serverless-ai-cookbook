#!/usr/bin/env bash
set -euo pipefail

/opt/hcls/bin/python /app/runtime_loader.py

set -a
# shellcheck disable=SC1091
source /run/hcls-openmm/runtime.env
set +a

exec "$@"
