#!/usr/bin/env bash
set -euo pipefail

pip_bin="${VIRTUAL_ENV:-/opt/bioir/venv}/bin/pip"
python_bin="${VIRTUAL_ENV:-/opt/bioir/venv}/bin/python"

if ! "$pip_bin" show bionemo-ir >/dev/null 2>&1 || [[ "${BIOIR_FORCE_REINSTALL:-false}" == "true" ]]; then
  wheel_url="${BIOIR_WHEEL_URL:-}"

  if [[ -z "$wheel_url" ]]; then
    repository="${BIOIR_REPOSITORY:-NVIDIA-BioNeMo/BioNeMo-Inference-Runtime}"
    release="${BIOIR_RELEASE:-latest}"
    pattern="${BIOIR_WHEEL_PATTERN:-bionemo_ir-.*\+cu132-.*cp312.*x86_64.*\.whl}"
    api_path="releases/latest"
    if [[ "$release" != "latest" ]]; then
      api_path="releases/tags/$release"
    fi

    release_json="$(curl --fail --show-error --silent --location \
      --header 'Accept: application/vnd.github+json' \
      "https://api.github.com/repos/${repository}/${api_path}")"
    wheel_url="$(printf '%s' "$release_json" | "$python_bin" -c '
import json
import re
import sys

pattern = re.compile(sys.argv[1])
assets = json.load(sys.stdin).get("assets", [])
matches = [asset["browser_download_url"] for asset in assets if pattern.fullmatch(asset["name"])]
if len(matches) != 1:
    names = ", ".join(asset["name"] for asset in assets)
    raise SystemExit(f"Expected one BioIR wheel matching {pattern.pattern!r}; release assets: {names}")
print(matches[0])
' "$pattern")"
  fi

  echo "Installing BioIR from the official NVIDIA release asset."
  "$pip_bin" install --no-cache-dir --upgrade "$wheel_url"
fi

"$pip_bin" show bionemo-ir | awk '/^(Name|Version):/ {print}'
exec "$@"
