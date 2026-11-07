---
title: Train a Black Forest Labs FLUX 3 Action SO-101 Pick Orange task LoRA
category: robotics
type: batch-job
runtime: nebius-ai-jobs
frameworks: [pytorch, lerobot]
keywords: [robotics, black-forest-labs, flux-action, so101, lora, training]
difficulty: advanced
---

<p align="center">
  <a href="https://bfl.ai"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/black-forest-labs-white.svg">
    <img src="assets/black-forest-labs-black.svg" alt="Black Forest Labs" height="48">
  </picture></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://nebius.com"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/nebius-white.svg">
    <img src="assets/nebius-black.svg" alt="Nebius" height="48">
  </picture></a>
</p>

# Train a Black Forest Labs FLUX 3 Action SO-101 Pick Orange task LoRA

This demo trains a **task LoRA** on [Black Forest Labs' prepared SO-101 policy](https://docs.bfl.ai/flux_3/flux3_action_so101). It uses one Nebius GPU Job and 60 demonstrations from [LeIsaac Pick Orange](https://huggingface.co/datasets/LightwheelAI/leisaac-pick-orange) (Apache 2.0). The model uses the [FLUX Kommunity License](https://huggingface.co/black-forest-labs/flux-3-action-so101). To train full weights for a different robot, use the [new embodiment demo](../bfl-flux-action-new-embodiment-full-finetune/README.md).

The demo downloads pinned data and model revisions, converts LeIsaac's joint values into the model's SO-101 frame, trains 100 microsteps for a smoke test or 60,000 for the example full run, and publishes adapters to Nebius Object Storage. Preparation and training run inside the Serverless job; no local GPU or simulator is required. This cookbook ends with published adapters and a training receipt; it does not measure robot task success.

## Current policy and calibration

The recipe pins policy `e2584b2698e3b88368854976e354af87ec9893c6`. Its saved statistics expect the current SO-101 degree convention, not unconverted `-100..100` range values. The dataset remains the pinned LeIsaac recording; both measured states and absolute action targets are converted before training, and their episode statistics receive the same transform.

The conversion first inverts [LeIsaac's range mapping](https://github.com/LightwheelAI/leisaac/blob/24d3bcd/source/leisaac/leisaac/utils/robot_utils.py) using its [USD joint limits](https://github.com/LightwheelAI/leisaac/blob/24d3bcd/source/leisaac/leisaac/assets/robots/lerobot.py). The updated [SO-101 simulation app](https://huggingface.co/spaces/multimodalart/flux-3-action-so101-sim/blob/d7da38e032da0e136d6de21c218dc616982a8cc9/app.py) uses the exact `e2584b2` quantiles and passes [physical joint degrees directly](https://huggingface.co/spaces/multimodalart/flux-3-action-so101-sim/blob/d7da38e032da0e136d6de21c218dc616982a8cc9/sim.py). The old shoulder-lift sign flip and legacy model-frame offsets are therefore removed. The new coefficients are derived from those coordinate mappings, not fitted to quantiles.

For `policy_value = source_value * scale + offset`:

| Channel | Scale | Offset | Converted states outside new q01–q99 |
| --- | ---: | ---: | ---: |
| shoulder_pan | 1.1 | 0 | 17.46% |
| shoulder_lift | 1.0 | 0 | 11.90% |
| elbow_flex | 0.95 | -5 | 13.11% |
| wrist_flex | 0.95 | 0 | 0.07% |
| wrist_roll | 1.6 | 0 | 78.23% |
| gripper | 1.0 | 0 | 27.89% |

The gripper remains in percentage points. The November 4 audit checked all 60 episodes / 36,293 frames against the actual downloaded `e2584b2` state normalizer (SHA-256 `86b5d152c9df39a640248215469c97a3facf240d481ee0e3e29fd185b423e458`). Every joint has some overlap, so the coarse preflight passes; the large wrist-roll/gripper tail differences remain a distribution-shift risk. This audit does not establish held-out or robot task performance. Use `to_motor` for the inverse command mapping back to LeIsaac range values. This simulator-specific conversion cannot upgrade arbitrary legacy real-arm recordings: those require their original per-arm calibration or new recordings with current LeRobot and `use_degrees=True`.

## Current revision validation

On November 4, the rebuilt Linux AMD64 image passed all 15 SO-101 tests without skips; its recipe/runtime bytes matched the checkout. Smoke job `aijob-e00gy45pqcjpnsdyy3` reached `COMPLETED` with 100 microsteps / 25 optimizer updates on `e2584b2`, a 7m 49s container runtime, 29.83 GiB peak allocated GPU memory, and final reported training loss 0.334. Its cloud overlap report exactly matched the all-frame audit above. Both downloaded adapter hashes matched the receipt, and their saved history/target normalization tensors exactly matched the new policy package.

Fresh-process H200 job `aijob-e00g96sawhhcsna0qk` also reached `COMPLETED`. It reloaded the raw and EMA adapters with the new base, pinned encoders, and saved processors; both produced finite `[1, 42, 6]` normalized chunks and `[1, 6]` absolute commands across three ticks. All four downloaded action arrays passed independent shape/finite checks. Both validation instances were removed; artifacts were retained. This smoke did not measure task success; the separate evaluation below uses the full-budget adapters.

## Full-budget validation on e2584b2

The November 4–5, 2026 H200 run (`aijob-e00a7e2bv7rzehhx0v`, artifacts `runs/pr33-so101-e258-full-1104/`) reached `COMPLETED` with all 60,000 microsteps / 15,000 optimizer updates, all 60 demonstrations, and accumulation four. Container runtime was 15h 49m; peak allocated GPU memory was 29.83 GiB and final reported training loss was 0.146. The receipt binds policy `e2584b2`, the calibration ID above, and the exact state-normalizer checksum. The final `060000` completion marker matched the receipt; both 471,775,248-byte raw/EMA adapters were independently streamed and SHA-256 checked.

Fresh-process H200 inference job `aijob-e00qq9e75207xwfy10` reached `COMPLETED` after restoring the final raw and EMA adapters with the pinned base/encoders and saved processors. Both produced finite `[1, 42, 6]` normalized chunks and `[1, 6]` absolute commands over three ticks from recorded observations. All four downloaded arrays passed independent shape/finite checks; the inference receipt matched the source run, 60,000-step budget, adapter hashes, policy revision, calibration ID, and normalizer checksum. A paginated compute inventory confirmed no validation-owned instances remained; images and artifacts were retained. This verifies the training/publication/reload/inference path. That validation measured reload/inference only. The separate quality evaluation below measures held-out error and simulator task success; the wrist-roll/gripper distribution shift described above remains.

![SO-101 e2584b2 training loss across all 60,000 microsteps, with logged values and a ten-point trailing mean.](assets/full-training-loss.png)

The curve uses all 3,000 logged points from `runs/pr33-so101-e258-full-1104/train.log`; the line shows a ten-point trailing mean. [Download the logged losses](assets/full-training-loss.csv). This is training loss, not a held-out or robot success metric.

## Policy-quality evaluation (November 5–7, 2026)

A separate evaluation completed 25 paired PickOrange simulator seeds for each full-budget base/raw/EMA policy. Raw achieved **10/25 full-task successes**, EMA **9/25**, and base **0/25**. The frozen placement predicate counts whether each orange ever met its plate condition; it does not require final containment.

| Full-data policy | Ever-met placements | Full-task successes | Paired success-rate delta vs base, 95% seed-bootstrap interval |
| --- | ---: | ---: | --- |
| Base | 0/75 | 0/25 | Reference |
| Raw adapter | 52/75 | 10/25 (40%) | +40 percentage points [20, 60] |
| EMA adapter | 39/75 | 9/25 (36%) | +36 percentage points [16, 56] |

Separately, new adapters trained for the full 60,000 microsteps using only episodes 0–47 reduced normalized action MSE on 48 fixed windows from held-out episodes 48–59: base **0.34148**, raw **0.22230**, EMA **0.21364**. These are different adapters from the full-data simulator policies. Offline error is not task success. No held-out checkpoint selection or tuning was performed.

See [evaluation methods, provenance and limitations](QUALITY_EVALUATION.md), [all simulator seed outcomes and intervals](assets/paired-simulator-quality.json), and [held-out windows, per-channel errors and episode uncertainty](assets/heldout-quality.json). Physical-robot performance was not evaluated. The training helper still ends at artifact publication and records `quality_evaluation: "not_run"`; these results came from separate evaluation jobs.

## Historical smoke run (legacy base)

| Measured on 2026-11-03 | Result |
| --- | --- |
| GPU | One H200 |
| Training | 100 microsteps / 25 optimizer updates |
| Container runtime | 7m 53s |
| Peak allocated GPU memory | 29.83 GiB |
| Final reported training loss | 0.239 |
| Output | Raw and EMA adapters, about 472 MB each; both SHA-256 hashes verified |

Container runtime includes preparation, model downloads, training, and publication; it excludes local image build/push, scheduling, and image pull. These are historical observations using policy `c9e13b2` and calibration `leisaac-24d3bcd-to-flux-so101-hf-sim-73899a12`, not a time-to-first-run guarantee. Cost and peak scratch usage were not measured; GPU runtime, storage, and transfers can contribute to the bill. Smoke job `aijob-e00z1b0bd9770zj4jc` reached `COMPLETED`; the downloaded raw and EMA adapter hashes both passed `scripts/verify.py`. Its resolved config used all 60 episodes with `eval_split: 0.0` and four accumulation steps.

A separate fresh-process H200 job (`aijob-e00qk2padxhat759vd`) reloaded both raw and EMA adapters with their pinned base and saved processors. Each produced finite `[1, 42, 6]` chunks and postprocessed `[1, 6]` commands over three ticks from recorded observations; all four downloaded SO-101 action arrays passed shape/finite checks. The historical full run is verified below; it does not validate the current `e2584b2` base.

## Historical full-budget validation (legacy base)

The November 3–4, 2026 run on `c9e13b2` (`aijob-e00jwter5g13jjajrp`) reached `COMPLETED` with 60,000 microsteps / 15,000 optimizer updates, all 60 demonstrations, and accumulation four. Container runtime was 15h 47m; peak allocated GPU memory was 29.83 GiB and final reported training loss was 0.123. The final `060000` completion marker matched `TRAIN_COMPLETE.json`; both published adapters were independently streamed and SHA-256 checked against the receipt.

A fresh H200 process (`aijob-e00erfq13f3rj2n440`) restored the final raw and EMA adapters with the pinned base/encoders and saved processors, then reached `COMPLETED`. Each produced finite `[1, 42, 6]` normalized chunks and `[1, 6]` absolute commands over three ticks from recorded observations. All four action arrays were downloaded and independently checked. Validation compute was removed; images and artifacts were retained. This verifies the training/publication/reload/inference path; held-out policy quality and robot/simulator task success were not evaluated.

## Workflow

[![SO-101 training workflow: pinned Pick Orange data and model settings feed one Serverless GPU job for dataset preparation, joint calibration, and LoRA training. Object Storage holds complete adapter checkpoints, hashes, and the training receipt.](assets/workflow.png)](assets/workflow.png)

## Dataset preview

![First-frame scene and wrist views from the pinned LeIsaac Pick Orange dataset.](assets/dataset-preview.jpg)

Left: front camera, mapped to the policy's scene camera. Right: wrist camera. The task is “Grab orange and place into plate.” These are demonstration inputs, not a trained-policy rollout. Source: [LightwheelAI/LeIsaac Pick Orange, pinned revision](https://huggingface.co/datasets/LightwheelAI/leisaac-pick-orange/tree/fa6e0625d814352b8e6ee1c6d2482194e4da8ed3), Apache 2.0. Each run also publishes its first-frame `camera-preview.jpg`.

## Requirements and compute

- Local tools: authenticated Nebius CLI, Docker with Linux AMD64 build support, and AWS CLI configured for Object Storage. Python 3.11+ runs the local checks and artifact verification.
- Result verification needs about 1 GB of free local disk space, in addition to Docker build storage.
- A Nebius project, subnet, Object Storage bucket, container registry, and quota for the resources below. Keep the resources in the same region.
- Hugging Face model access: accept the linked model's access terms where required, and supply the token through `NEBIUS_HF_TOKEN_SECRET`.

| Stage | Resources | Work |
| --- | --- | --- |
| Training | Default: one H200, `1gpu-16vcpu-200gb`, 200 GiB scratch disk | Smoke: 100 microsteps; documented full run: 60,000. |

Cold-start time, download size, and peak scratch usage have not been benchmarked. The 72-hour job timeout is a ceiling, not an estimated duration. The training receipt records `train_seconds` for training and publication; it excludes data preparation and model downloads.

## Files

| Path | Purpose |
| --- | --- |
| `Dockerfile` | Build the pinned training environment. |
| `assets/` | Workflow diagram, official logos, and logo source URLs. |
| `configs/` | Pinned model, dataset, and training settings. |
| `scripts/job.sh` | Submit smoke and full-training jobs. |
| `scripts/verify.py` | Independently hash downloaded final weights and check completion markers. |
| `src/` | Dataset preparation, joint calibration, training, and checkpoint publication. |
| `tests/` | Local checks for job submission, calibration, dataset contracts, and publication. |

## 1. Configure and build

Clone the repository and enter this example:

```bash
git clone https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook
```

If you are reading an unmerged PR, check out that PR here. Then enter the example:

```bash
cd robotics/bfl-flux-action-so101-pick-orange-task-lora
```

Prepare the resources below once, then fill in the exports. Reuse a project-specific CLI profile and keep the bucket, registry, subnet, and GPU job in the same region.

| Requirement | Setup and value to copy |
| --- | --- |
| CLI profile and project | [Install](https://docs.nebius.com/cli/install) and [authenticate the CLI](https://docs.nebius.com/cli/configure); copy the profile name and `project-…` ID. |
| Subnet | [Find your subnet ID](https://docs.nebius.com/vpc/networking/resources), `vpcsubnet-…`, in the selected project/region. |
| Object Storage | [Create a bucket](https://docs.nebius.com/object-storage/quickstart) and [configure AWS CLI credentials](https://docs.nebius.com/object-storage/interfaces/aws-cli); copy both its S3 name and `storagebucket-…` resource ID. |
| Container Registry | [Create a registry and configure Docker authentication](https://docs.nebius.com/container-registry/quickstart); copy its `registry-…` ID. |
| Hugging Face token | Accept the model access terms. [Create a SecretStash/MysteryBox secret version](https://docs.nebius.com/mysterybox/secrets/create) with payload key `HF_TOKEN`; copy the secret and version IDs, not the token. |

```bash
export NEBIUS_PROFILE=YOUR_PROFILE
export NEBIUS_PROJECT_ID=YOUR_PROJECT_ID
export NEBIUS_SUBNET_ID=YOUR_SUBNET_ID
export NEBIUS_BUCKET=YOUR_BUCKET_NAME
export NEBIUS_BUCKET_ID=YOUR_STORAGEBUCKET_ID
export NEBIUS_REGISTRY_ID=YOUR_REGISTRY_ID
export NEBIUS_REGION=YOUR_REGION
export NEBIUS_GPU_PLATFORM=gpu-h200-sxm
export NEBIUS_S3_ENDPOINT="https://storage.$NEBIUS_REGION.nebius.cloud"
export AWS_PROFILE=YOUR_OBJECT_STORAGE_PROFILE
export NEBIUS_HF_TOKEN_SECRET="mbsec-YOUR_SECRET_ID@mbsecver-YOUR_VERSION_ID"
export NEBIUS_IMAGE="cr.$NEBIUS_REGION.nebius.cloud/${NEBIUS_REGISTRY_ID#registry-}/bfl-s:$(date -u +%m%d%H%M%S)"
# Read-only checks before building or submitting:
nebius iam project get "$NEBIUS_PROJECT_ID" --profile "$NEBIUS_PROFILE"
aws s3 ls "s3://$NEBIUS_BUCKET/" --endpoint-url "$NEBIUS_S3_ENDPOINT"
python3 -m unittest discover -s tests -v

docker build --platform linux/amd64 -t "$NEBIUS_IMAGE" .
docker push "$NEBIUS_IMAGE"
```

`NEBIUS_HF_TOKEN_SECRET` is a **secret/version selector**, not a Hugging Face token. The job receives the selected payload as `HF_TOKEN`; never put the token in the image or repository. SecretStash is the current product name; CLI/API commands still use `mysterybox`. W&B tracking is optional: set `WANDB_API_KEY` to a MysteryBox selector and `WANDB_PROJECT` to a project name before submitting.

## 2. Try a short run

```bash
export RUN_NAME="flux-orange-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/job.sh smoke dry-run
bash scripts/job.sh smoke
```

After submission, the helper prints the run name, artifact prefix, completion receipt, and commands to find and monitor the job. Save the returned job ID. Check the job and its durable result:

```bash
nebius ai job get SMOKE_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs SMOKE_JOB_ID --profile "$NEBIUS_PROFILE" --tail 50
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect `COMPLETED`, `microsteps: 100`, and an adapter hash in `TRAIN_COMPLETE.json`. Inspect `calibration-report.json` and `camera-preview.jpg` in the same run prefix before a long run. The report flags how far the demonstrations extend beyond the checkpoint's usual joint range. Use `bash scripts/job.sh smoke dry-run` to inspect a submission before sending it.

## Verify your result

First require the cloud job to report `COMPLETED`; the artifact checker does not query job state. The block stops on the first error and refuses an existing local results directory. To repeat a download, move the previous local results directory aside first, keeping the cloud `RUN_NAME` unchanged. The adapters total about 944 MB; optimizer state is excluded. Use the same steps for smoke and full runs:

```bash
(
set -euo pipefail
nebius ai job get JOB_ID --profile "$NEBIUS_PROFILE"
export RESULTS_DIR="results/$RUN_NAME"
mkdir -p results
mkdir "$RESULTS_DIR"
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" "$RESULTS_DIR/" \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
CHECKPOINT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["selected_checkpoint"].rsplit("/",1)[0])' "$RESULTS_DIR/TRAIN_COMPLETE.json")
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/$CHECKPOINT/" "$RESULTS_DIR/$CHECKPOINT/" \
  --recursive --exclude "training_state/*" --endpoint-url "$NEBIUS_S3_ENDPOINT"
python3 scripts/verify.py "$RESULTS_DIR"
)
```

A successful check prints the independently computed SHA-256 values and a final `PASS:` line. A missing marker or changed weight file exits nonzero. Hash verification establishes artifact integrity; it does not reload the policy or measure robot task success.

A smoke receipt contains these fields (other metadata omitted):

```json
{
  "status": "trained",
  "microsteps": 100,
  "optimizer_updates": 25,
  "selected_checkpoint": "checkpoints/000100/pretrained_model",
  "quality_evaluation": "not_run"
}
```

Expected smoke output layout:

```text
runs/$RUN_NAME/
├── TRAIN_COMPLETE.json
├── calibration-report.json
├── camera-preview.jpg
└── checkpoints/000100/
    ├── COMPLETE.json
    ├── pretrained_model/adapter_model.safetensors
    └── pretrained_model_ema/adapter_model.safetensors
```

## 3. Train the full adapter

```bash
export FULL_STEPS=60000 # Default; override explicitly for another budget.
export RUN_NAME="flux-orange-full-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/job.sh full
nebius ai job get FULL_JOB_ID --profile "$NEBIUS_PROFILE"
nebius ai job logs FULL_JOB_ID --profile "$NEBIUS_PROFILE" --tail 50
aws s3 cp "s3://$NEBIUS_BUCKET/runs/$RUN_NAME/TRAIN_COMPLETE.json" - \
  --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Expect a `COMPLETED` job and a `TRAIN_COMPLETE.json` with `microsteps: 60000`. The receipt names the final checkpoint; its `COMPLETE.json` records hashes for the raw and EMA adapters. Intermediate checkpoints are published every 5,000 microsteps. Use a fresh `RUN_NAME` for every run. If you choose `NEBIUS_PREEMPTIBLE=1`, completed checkpoints remain in Object Storage after interruption, but this demo does not automatically resume.

## Adapt and check locally

Edit [`configs/recipe.json`](configs/recipe.json) to change the pinned inputs. The calibration in [`src/calibration.py`](src/calibration.py) is specific to this dataset and SO-101 policy; verify joint units, signs, ranges, and camera order before substituting recordings. Use the [full fine-tuning example](../bfl-flux-action-new-embodiment-full-finetune/README.md) for a different embodiment.

Run the lightweight checks from this directory:

```bash
python3 -m unittest discover -s tests -v
```

The parquet/safetensors calibration check skips when its optional dependencies are absent locally; those dependencies are included in the training image.

## Storage, checkpoints, and interruption

Dataset preparation and training use local `/workspace/work` storage so video reads and training writes do not depend on the Object Storage mount. The bucket is mounted at `/workspace/data` for durable artifacts. Scratch disks and job timeouts are configured in `scripts/job.sh`; the defaults provide working room but are not measured minimums.

A background watcher checks for complete checkpoints every 30 seconds and copies them to the bucket. If publication fails, the runner stops the training process group and fails the job, preserving any checkpoints already published. For the documented 60,000-microstep run, checkpoints are saved every 5,000 microsteps. Publication records adapter hashes in `COMPLETE.json`; `TRAIN_COMPLETE.json` is written only after the requested final checkpoint is published. A completed checkpoint may survive an interrupted job even when the training receipt is absent.

`selected_checkpoint` in the receipt identifies **the final checkpoint**. Checkpoint selection is left to you: task quality can decrease during a longer LoRA run, so evaluate intermediate raw and EMA adapters before deployment. The runner does not rank checkpoints or run policy evaluation; `quality_evaluation: "not_run"` makes that limit explicit in the receipt.

The script and runner both default to 60,000 microsteps, with checkpoints every 5,000 (including shorter full runs). Accumulation is explicitly fixed at four microsteps per optimizer update, so the default run has 15,000 optimizer updates. `dataset.eval_split=0` uses all 60 demonstrations; evaluation is disabled. This is an example budget, not a claim that 60,000 steps is best for this task.

The Dockerfile retains public [LeRobot `f6c0f192`](https://github.com/huggingface/lerobot/tree/f6c0f192952d0dfe5a48805f9688711294461bff). The policy now pins `e2584b2698e3b88368854976e354af87ec9893c6`, recommended by the updated [FLUX Action guide](https://github.com/black-forest-labs/flux-action/blob/fc1145c/docs/so101-lora.md). Its saved processor configuration and conditioning settings are unchanged from the prior package, but its normalization tensors differ. A future model update must re-derive and validate the calibration; the runner rejects a mismatched policy revision or state-normalizer checksum.

Preemptible execution is opt-in with `NEBIUS_PREEMPTIBLE=1` and disables automatic restart. There is no resume path: after interruption, inspect published checkpoints, then use a fresh `RUN_NAME` for a new training run. Reusing a run name is rejected to prevent overwrites.

## Clean up

To stop an unfinished job, cancel that specific job:

```bash
nebius ai job cancel JOB_ID --profile "$NEBIUS_PROFILE"
```

After completion, scratch storage is ephemeral. Published run artifacts and registry images remain and can incur storage charges. Keep the final weights and receipt until you have saved what you need. Preview deletion of only this run's prefix:

```bash
aws s3 rm "s3://$NEBIUS_BUCKET/runs/${RUN_NAME:?set RUN_NAME}/" \
  --recursive --dryrun --endpoint-url "$NEBIUS_S3_ENDPOINT"
```

Inspect that list, then remove `--dryrun` only if you intend to delete those artifacts. Remove the local image with `docker image rm "$NEBIUS_IMAGE"`; delete the corresponding remote image/tag separately in Container Registry when it is no longer needed. Preserve shared buckets, registries, and secrets.

## Run with a coding agent

Paste this prompt into your coding agent from this example directory:

```text
Read README.md, Dockerfile, configs/, scripts/job.sh, and scripts/verify.py.
Use the existing NEBIUS_* and AWS_PROFILE environment settings. If required
resource IDs or the HF secret selector are missing, ask for them. Never search
other files for credentials, print token values, or put credentials in images.
Run local tests. Build and push the documented Linux AMD64 image, then run
bash scripts/job.sh smoke dry-run. Resolve validation errors before submitting one
smoke job. Record its ID and RUN_NAME; monitor that job to a terminal state
without submitting duplicates. Require COMPLETED, follow Verify your result,
and report steps, runtime, artifact locations, and independently checked hashes.
Do not launch full training or delete cloud resources. Do not claim policy
quality from finite loss or successful publication.
```

## Troubleshooting

Replace `JOB_ID` in the commands below with the ID returned by submission or the printed name lookup.

| Symptom | Diagnose and recover |
| --- | --- |
| Image label exceeds 64 characters | Use a short repository name and tag as above. If validation reports a `metadata.labels` length error, keep the complete image reference at most 64 characters. Long tags and full digest references exceed the limit in the current CLI/API path. |
| Model access denied | Inspect `nebius ai job logs JOB_ID --profile "$NEBIUS_PROFILE" --tail 80`. Accept the model access terms and set `NEBIUS_HF_TOKEN_SECRET` to a MysteryBox selector before a new submission. |
| Pending job or capacity error such as `NotEnoughResources` | Inspect `nebius ai job get JOB_ID --profile "$NEBIUS_PROFILE"` for scheduling details. Check the selected GPU quota and capacity in your region before retrying; a pending job is not evidence that training started. |
| `No space left on device` | Inspect the job logs for the failing path. Increase `--disk-size` in `scripts/job.sh` if scratch storage is exhausted, then submit a fresh run. |
| Interrupted job or timeout | Inspect job state and logs, then list `runs/$RUN_NAME/` in the bucket. Completed checkpoints can remain; a new training run starts from scratch under a fresh name. Increasing a timeout does not enable resume. |
| Run prefix already exists | Choose a fresh `RUN_NAME`; do not delete previous results just to reuse the name. |
| No `TRAIN_COMPLETE.json` | Inspect job state and logs. Individual checkpoints do not prove the requested training run finished; require both a completed job and its training receipt. |
| Calibration check fails | Inspect `calibration-report.json` if written, and the job logs. Verify joint units, signs, ranges, and camera order against `src/calibration.py` and the pinned dataset before retrying. Keep the calibration checks enabled. |
