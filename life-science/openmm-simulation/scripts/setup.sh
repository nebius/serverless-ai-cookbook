#!/bin/bash

# Setup script for local development

set -e

echo "Setting up OpenMM Serverless Simulation environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed."
    echo ""
    echo "Install it with one of the following (recommended — uses a signed package):"
    echo "  macOS (Homebrew):  brew install uv"
    echo "  Linux  (pipx):     pipx install uv"
    echo "  Any OS (pip):      pip install --user uv"
    echo ""
    echo "Alternatively, install from upstream by downloading the script first,"
    echo "inspecting it, and then running it — do not pipe curl directly into a shell."
    echo "  curl -LsSf --proto '=https' --tlsv1.2 https://astral.sh/uv/install.sh -o /tmp/uv-install.sh"
    echo "  less /tmp/uv-install.sh   # review before executing"
    echo "  sh /tmp/uv-install.sh"
    echo ""
    echo "After installing, restart your shell (or 'source ~/.bashrc' / 'source ~/.zshrc')"
    echo "and re-run this script."
    exit 1
fi

MIN_MINOR=11

if [ -n "${UV_PYTHON:-}" ]; then
    PYTHON_BIN="$UV_PYTHON"
else
    PYTHON_BIN=""
    for candidate in python3 python3.13 python3.12 python3.11; do
        if command -v "$candidate" >/dev/null 2>&1; then
            CANDIDATE_MINOR="$("$candidate" -c 'import sys; print(sys.version_info.minor)')"
            if [ "$CANDIDATE_MINOR" -ge "$MIN_MINOR" ]; then
                PYTHON_BIN="$candidate"
                break
            fi
        fi
    done
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Python 3.${MIN_MINOR}+ is required for this example." >&2
    echo "Install a supported Python version and rerun ./scripts/setup.sh, or set UV_PYTHON." >&2
    exit 1
fi

echo "Using Python interpreter: $PYTHON_BIN"
echo "Creating virtual environment..."
uv venv --clear --python "$PYTHON_BIN"

echo "Installing dependencies..."
uv pip install .

echo "Setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To run a local simulation:"
echo "  python -m sim.run --protein-id 1UBQ --steps 1000"
echo ""
echo "To submit a serverless job:"
echo "  bash ./scripts/run_serverless.sh 1UBQ 1000"
echo ""
