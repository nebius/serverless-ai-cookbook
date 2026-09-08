#!/usr/bin/env bash
set -euo pipefail

runtime_env="/run/hcls-gromacs/runtime.env"
/opt/hcls/bin/python /app/runtime_loader.py --env-file "$runtime_env"

set -a
# shellcheck disable=SC1090
source "$runtime_env"
set +a

exec "$@"
