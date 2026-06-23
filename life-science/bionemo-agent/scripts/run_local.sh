#!/usr/bin/env bash
set -euo pipefail

uv sync
uv run python -m bionemo_agent.smoke --query "${1:-protein sequence embedding}"

if [[ -z "${NEBIUS_API_KEY:-}" ]]; then
  cat <<'EOF'
NEBIUS_API_KEY is not set, so skipping nat serve.
Set NEBIUS_API_KEY to run the interactive agent locally.
EOF
  exit 0
fi

PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  uv run nat serve --config_file configs/config.yml --host 0.0.0.0 --port "${PORT:-8000}"
