#!/usr/bin/env bash
# gpu_preflight.sh — Isaac for Healthcare ray-tracing GPU compatibility gate.
#
# Isaac for Healthcare's ray-traced sensor simulation (e.g. the robotic
# ultrasound B-mode simulator) requires an RT-Core GPU with CUDA compute
# capability >= 8.6. Data-center accelerators without RT Cores (the i4h docs
# explicitly list A100 and H100) cannot run the ray tracer. This script
# reproduces the i4h compatibility check and classifies the GPU you actually
# landed on so you can fail fast BEFORE pulling the large Isaac Sim image.
#
# Exit codes: 0 = known-good RT-Core GPU, 2 = compute-cap gate failed,
#             3 = compute cap OK but RT-Core support not confirmed for this part.
set -euo pipefail

echo "============================================================"
echo "Isaac for Healthcare — GPU ray-tracing preflight"
echo "============================================================"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "FAIL: nvidia-smi not found. No NVIDIA GPU visible in this container."
  exit 2
fi

# i4h documented check: name + compute capability.
nvidia-smi --query-gpu=name,compute_cap,memory.total,driver_version \
  --format=csv,noheader | sed 's/^/GPU: /'

NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1 | xargs)"
CC="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -n1 | xargs)"

echo
echo "Detected GPU : ${NAME}"
echo "Compute cap  : ${CC}  (i4h requires >= 8.6)"

# --- Compute-capability gate (necessary condition) -------------------------
cc_major="${CC%%.*}"
cc_minor="${CC##*.}"
cc_score=$(( cc_major * 10 + cc_minor ))
if (( cc_score < 86 )); then
  echo
  echo "RESULT: FAIL — compute capability ${CC} < 8.6. Not supported by Isaac Sim ray tracing."
  exit 2
fi
echo "Compute-cap gate: PASS"

# --- RT-Core class (sufficient condition) ----------------------------------
# Known-good RT-Core parts validated for visualization/ray tracing.
# Known-unsupported: data-center parts the i4h docs call out (A100, H100) and
# their close siblings that lack RT Cores for the Isaac ray tracer.
shopt -s nocasematch
if [[ "$NAME" == *"L40S"* || "$NAME" == *"L40"* || "$NAME" == *"L4"* \
      || "$NAME" == *"RTX"* || "$NAME" == *"A6000"* || "$NAME" == *"A40"* \
      || "$NAME" == *"A10"* ]]; then
  echo "RT-Core class  : KNOWN-GOOD"
  echo
  echo "RESULT: PASS — RT-Core GPU suitable for Isaac for Healthcare ray tracing."
  echo "On Nebius Serverless use --platform gpu-l40s-a (or gpu-rtx6000)."
  exit 0
elif [[ "$NAME" == *"A100"* || "$NAME" == *"H100"* || "$NAME" == *"H200"* ]]; then
  echo "RT-Core class  : UNSUPPORTED (data-center GPU, no RT Cores for the ray tracer)"
  echo
  echo "RESULT: FAIL — ${NAME} is a data-center GPU the i4h docs list as unsupported"
  echo "for ray tracing. Switch to --platform gpu-l40s-a or gpu-rtx6000."
  exit 3
else
  echo "RT-Core class  : UNVERIFIED for this part"
  echo
  echo "RESULT: CAUTION — compute capability is high enough, but RT-Core ray-tracing"
  echo "support for '${NAME}' has not been verified for Isaac for Healthcare."
  echo "Prefer the explicitly RT-Core parts on Nebius: gpu-l40s-a or gpu-rtx6000."
  exit 3
fi
