#!/usr/bin/env bash
set -euo pipefail

python_bin="${VIRTUAL_ENV:-/opt/bioir/venv}/bin/python"

"$python_bin" -c '
import importlib.metadata
import os
installed = importlib.metadata.version("bionemo-ir")
expected = os.environ.get("BIOIR_VERSION", "0.1.0")
if installed != expected:
    raise SystemExit(f"Image contains BioIR {installed}, requested {expected}; rebuild the image to change versions.")
print(f"BioIR {installed} (installed at image build time)", flush=True)
'
exec "$@"
