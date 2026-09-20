#!/usr/bin/env bash
# Cosmos 3 post-training (SFT) job launcher.
# Installs Cosmos Framework, runs NVIDIA's vision-generator SFT recipe (Nano / Edge / Super-LoRA)
# on all GPUs of the node, exports the result to Hugging Face safetensors, converts it to a
# Diffusers pipeline, and copies everything into the mounted bucket. Then exits.
#
# Image: nvidia/cuda:13.0.2-cudnn-devel-ubuntu24.04 (public). Env knobs (all optional):
#   RECIPE        nano | edge | super          (default nano)
#   MAX_ITER      training iterations          (default 500 = NVIDIA's recipe; 20 for a smoke test)
#   SAVE_ITER     checkpoint interval          (default 100)
#   NPROC         GPUs to use                  (default: all visible)
#   OUTPUT_DIR    where results are copied     (default /data/cosmos3-sft)
#   RUN_ID        result sub-folder            (default run-<timestamp>)
#   DATASET_PATH  your own JSONL dataset dir   (default: NVIDIA's BridgeData2 subset, downloaded)
#   FRAMEWORK_REF / COSMOS_REF   git refs to pin (defaults below)
#   HF_TOKEN      only needed for gated datasets/models
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
RECIPE="${RECIPE:-nano}"; MAX_ITER="${MAX_ITER:-500}"; SAVE_ITER="${SAVE_ITER:-100}"
OUTPUT_DIR="${OUTPUT_DIR:-/data/cosmos3-sft}"; RUN_ID="${RUN_ID:-run-$(date +%Y%m%d-%H%M%S)}"
FRAMEWORK_REF="${FRAMEWORK_REF:-96303bb0bdd1}"      # NVIDIA/cosmos-framework "Release 2026-09-20"
COSMOS_REF="${COSMOS_REF:-main}"                     # nvidia/cosmos (recipes)
NPROC="${NPROC:-$(nvidia-smi -L | wc -l)}"
export HF_HOME=/workspace/hf UV_CACHE_DIR=/workspace/uv-cache          # local NVMe, never the bucket
mkdir -p /workspace "$HF_HOME" "$UV_CACHE_DIR"; cd /workspace
log() { echo "$(date +%H:%M:%S) $*"; }

log "1/6 system packages"
apt-get update -qq && apt-get install -y -qq --no-install-recommends curl ffmpeg git git-lfs libgl1 libglib2.0-0 libx11-dev libxcb1 tree wget >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; export PATH="$HOME/.local/bin:$PATH"

log "2/6 Cosmos Framework @ $FRAMEWORK_REF"
export GIT_LFS_SKIP_SMUDGE=1
git clone -q https://github.com/NVIDIA/cosmos-framework.git cosmos-framework && (cd cosmos-framework && git checkout -q "$FRAMEWORK_REF")
git clone -q --depth 1 --branch "$COSMOS_REF" https://github.com/nvidia/cosmos.git cosmos
cd /workspace/cosmos-framework
uv sync --all-extras --group=cu130-train 2>&1 | tail -3
source .venv/bin/activate
python -c "import torch, cosmos_framework; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'gpus', torch.cuda.device_count())"

RECIPE_DIR=/workspace/cosmos/cookbooks/cosmos3/generator/audiovisual/finetune
cd "$RECIPE_DIR"
case "$RECIPE" in
  nano)  MODEL=Cosmos3-Nano;  TOML=toml/sft_config/vision_sft_nano.toml ;;
  edge)  MODEL=Cosmos3-Edge;  TOML=toml/sft_config/vision_sft_edge.toml ;;
  super) MODEL=Cosmos3-Super; TOML=toml/sft_config/vision_sft_super.toml ;;
  *) echo "unknown RECIPE=$RECIPE"; exit 2 ;;
esac

log "3/6 data + base checkpoint ($MODEL)"
DATASET_DIR="$PWD/data/BridgeData2-Subset-Synthetic-Captions"
if [ -z "${DATASET_PATH:-}" ]; then
  [ -f "$DATASET_DIR/sft_dataset_bridge/train/video_dataset_file.jsonl" ] || \
    uvx hf@latest download --repo-type dataset nvidia/BridgeData2-Subset-Synthetic-Captions --revision 40d018ac1c1a2a4b9734f17fdb21f3d933c49a01 --local-dir "$DATASET_DIR" --quiet
  export DATASET_PATH="$DATASET_DIR/sft_dataset_bridge"
fi
VAE_PATH="$PWD/checkpoints/wan22_vae/Wan2.2_VAE.pth"
[ -f "$VAE_PATH" ] || uvx hf@latest download Wan-AI/Wan2.2-TI2V-5B Wan2.2_VAE.pth --local-dir "$(dirname "$VAE_PATH")" --quiet
CHECKPOINT_DIR="$PWD/checkpoints/$MODEL"
[ -d "$CHECKPOINT_DIR" ] || python -m cosmos_framework.scripts.convert_model_to_dcp -o "$CHECKPOINT_DIR" --checkpoint-path "$MODEL"
export BASE_CHECKPOINT_PATH="$CHECKPOINT_DIR" WAN_VAE_PATH="$VAE_PATH"

log "4/6 train: recipe=$RECIPE max_iter=$MAX_ITER save_iter=$SAVE_ITER gpus=$NPROC"
TOML_RUN="$PWD/toml/sft_config/run.toml"
python - "$TOML" "$TOML_RUN" "$MAX_ITER" "$SAVE_ITER" "$RUN_ID" <<'PY'
import re, sys
src, dst, max_iter, save_iter, run_id = sys.argv[1:]
t = open(src).read()
t = re.sub(r"(?m)^max_iter\s*=.*$", f"max_iter                = {max_iter}", t)
t = re.sub(r"(?m)^save_iter\s*=.*$", f"save_iter            = {save_iter}", t)
t = re.sub(r"(?m)^cycle_lengths\s*=.*$", f"cycle_lengths      = [{max_iter}]", t)
t = re.sub(r"(?m)^warm_up_steps\s*=.*$", f"warm_up_steps      = [{max(1, int(max_iter)//10)}]", t)
t = re.sub(r'(?m)^name\s*=.*$', f'name         = "{run_id}"', t, count=1)
open(dst, "w").write(t)
PY
OUTPUT_ROOT="$PWD/outputs/train"
cd /workspace/cosmos-framework
IMAGINAIRE_OUTPUT_ROOT="$OUTPUT_ROOT" torchrun --nproc_per_node="$NPROC" -m cosmos_framework.scripts.train --sft-toml="$TOML_RUN"

log "5/6 export + convert"
RUN_DIR=$(ls -d "$OUTPUT_ROOT"/cosmos3/sft/"$RUN_ID"* | head -1)
CKPT="$RUN_DIR/checkpoints/$(cat "$RUN_DIR/checkpoints/latest_checkpoint.txt")"
python -m cosmos_framework.scripts.export_model --checkpoint-path "$CKPT" --config-file "$RUN_DIR/config.yaml" -o "$RUN_DIR/model"
python -m cosmos_framework.scripts.convert_model_to_diffusers --checkpoint-path "$RUN_DIR/model" -o "$RUN_DIR/diffusers"

log "6/6 copy results → $OUTPUT_DIR/$RUN_ID"
DEST="$OUTPUT_DIR/$RUN_ID"; mkdir -p "$DEST"
cp -r "$RUN_DIR/diffusers" "$DEST/diffusers"
cp -r "$RUN_DIR/model" "$DEST/model"
cp "$RUN_DIR/config.yaml" "$DEST/config.yaml"; cp "$TOML_RUN" "$DEST/sft.toml"
find "$RUN_DIR" -maxdepth 2 -name "*.log" -exec cp {} "$DEST/" \; 2>/dev/null || true
du -sh "$DEST"/* | sed 's/^/  /'
log "done: fine-tuned $MODEL → $DEST/diffusers (serve with: vllm serve $DEST/diffusers --omni --model-class-name Cosmos3OmniDiffusersPipeline)"
