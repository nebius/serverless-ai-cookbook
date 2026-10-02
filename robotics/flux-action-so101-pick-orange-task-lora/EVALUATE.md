# Evaluate base and adapted SO-101 policies

Use a Linux host with an RTX GPU that can run Isaac Sim 5.1 and the FLUX policy service. Follow [LeIsaac's installation and kitchen-asset instructions](https://lightwheelai.github.io/leisaac/docs/getting_started/installation/). Keep its Python environment separate from the training image. Check out the pinned LeIsaac revision:

```bash
git clone --recursive https://github.com/LightwheelAI/leisaac.git
cd leisaac
git checkout --detach 24d3bcd
git submodule update --init --recursive
```

Copy this cookbook directory to the evaluation host. Set the same `NEBIUS_IMAGE`, bucket, region endpoint, and AWS profile used for training. Set `HF_TOKEN` if the SO-101 model requires it. Read `selected_checkpoint` from `TRAIN_COMPLETE.json`; in `checkpoints/060000/pretrained_model`, the step directory is `060000`. Download that checkpoint, including `COMPLETE.json`:

```bash
export RECIPE_DIR=/ABSOLUTE/PATH/TO/flux-action-so101-pick-orange-task-lora
export EVAL_DIR="$RECIPE_DIR/eval"
mkdir -p "$EVAL_DIR/checkpoint" "$EVAL_DIR/model-cache" "$EVAL_DIR/hf-cache"
export CHECKPOINT_STEP=060000
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/checkpoints/$CHECKPOINT_STEP/" \
  "$EVAL_DIR/checkpoint/" --recursive --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Run the synchronous policy service in one terminal. For the **base** run:

```bash
docker run --rm --gpus all --ipc host -p 127.0.0.1:8765:8765 \
  -e HF_TOKEN \
  -e MODEL_VARIANT=base \
  -v "$EVAL_DIR/model-cache:/workspace/work/models" \
  -v "$EVAL_DIR/hf-cache:/workspace/cache" \
  "$NEBIUS_IMAGE" python3 /app/recipe/policy_service.py
```

In another terminal, activate the LeIsaac/Isaac Sim environment, work from the pinned LeIsaac checkout, and run:

```bash
python "$RECIPE_DIR/evaluate.py" --model base \
  --output "$EVAL_DIR/base.json" --episodes 25 --seed 42000 \
  --episode_length_s 120 --device cuda --enable_cameras --headless
```

Stop the base service. Start the **adapter** service with the same image, GPU, and cached base weights:

```bash
docker run --rm --gpus all --ipc host -p 127.0.0.1:8765:8765 \
  -e HF_TOKEN \
  -e MODEL_VARIANT=adapter \
  -e CHECKPOINT_DIR=/workspace/checkpoint/pretrained_model \
  -v "$EVAL_DIR/checkpoint:/workspace/checkpoint:ro" \
  -v "$EVAL_DIR/model-cache:/workspace/work/models" \
  -v "$EVAL_DIR/hf-cache:/workspace/cache" \
  "$NEBIUS_IMAGE" python3 /app/recipe/policy_service.py
```

In the LeIsaac terminal, run the same seeds with the adapter:

```bash
python "$RECIPE_DIR/evaluate.py" --model adapter \
  --output "$EVAL_DIR/adapter.json" --episodes 25 --seed 42000 \
  --episode_length_s 120 --device cuda --enable_cameras --headless
```

The service checks the published adapter hash. The evaluator saves JSON reports and videos. To test EMA as well, restart the adapter service with `CHECKPOINT_DIR=/workspace/checkpoint/pretrained_model_ema` and write its evaluation to a separate file.

## Compare results

```bash
python3 "$RECIPE_DIR/summarize.py" "$EVAL_DIR/base.json" "$EVAL_DIR/adapter.json" \
  "$EVAL_DIR/quality.json"
```

`quality.json` reports oranges placed out of 75, full task successes, and paired improvement over the base. The recipe's quality gate is at least **25/75 placements**, at least **10 more placements than base**, and a paired bootstrap interval above zero. If it fails, the adapter is trained but has not shown the intended quality.
