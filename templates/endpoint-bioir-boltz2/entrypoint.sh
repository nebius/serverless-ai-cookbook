#!/usr/bin/env bash
set -euo pipefail

pip_bin="${VIRTUAL_ENV:-/opt/bioir/venv}/bin/pip"
python_bin="${VIRTUAL_ENV:-/opt/bioir/venv}/bin/python"

if ! "$pip_bin" show bionemo-ir >/dev/null 2>&1 || [[ "${BIOIR_FORCE_REINSTALL:-false}" == "true" ]]; then
  install_target="${BIOIR_WHEEL_URL:-}"
  if [[ -z "$install_target" ]]; then
    distribution="${BIOIR_DISTRIBUTION:-bionemo-ir}"
    version="${BIOIR_VERSION:-}"
    install_target="$distribution"
    if [[ -n "$version" ]]; then
      install_target+="==$version"
    fi
  fi

  echo "Installing BioIR from NVIDIA's public package release."
  "$pip_bin" install --no-cache-dir --upgrade "$install_target"
fi

"$pip_bin" show bionemo-ir | awk '/^(Name|Version):/ {print}'
exec "$@"
