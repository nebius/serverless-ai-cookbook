---
title: Fine-Tune a Model with Axolotl
category: training
type: job
runtime: gpu
frameworks:
  - axolotl
  - pytorch
keywords:
  - finetuning
  - lora
  - qlora
  - qwen
difficulty: intermediate
---

## Fine-tune a model with Axolotl (Get Started)

Use this tutorial to run your first LoRA fine-tuning job on Serverless AI with Axolotl.

Official tutorial: [Fine-tuning a large language model by using a Serverless AI job and Axolotl](https://docs.nebius.com/serverless/tutorials/fine-tuning)

### What this example does

- fine-tunes `Qwen/Qwen2.5-0.5B` with LoRA
- runs Axolotl in a Serverless AI job
- stores checkpoints and adapters in Object Storage

### Why this is useful

This gives a practical baseline for adapter fine-tuning with managed GPUs and persistent artifact storage.

### Requirements

- you are in a tenant group with admin permissions
- Nebius CLI is installed and configured (see [Setup](../../README.md#setup))
- AWS CLI is installed and configured

### Runtime / compute

- image: `docker.io/axolotlai/axolotl:main-20260309-py3.11-cu128-2.9.1`
- platform: `gpu-l40s-a`
- preset: `1gpu-8vcpu-32gb`
- disk: `450Gi`
- workload: LoRA/QLoRA fine-tuning for `Qwen/Qwen2.5-0.5B`

## Quickstart

### 1) Prepare bucket and config

Create a bucket for config and outputs:

```bash
nebius storage bucket create --name fine-tuning-axolotl
```

Get bucket ID (used for volume mounting):

```bash
BUCKET_ID=$(nebius storage bucket get-by-name --name fine-tuning-axolotl --format json | jq -r '.metadata.id')
echo "$BUCKET_ID"
```

The training config is in [`src/config.yaml`](src/config.yaml):

```yaml
base_model: Qwen/Qwen2.5-0.5B

load_in_4bit: true
adapter: qlora

datasets:
  - path: Salesforce/wikitext
    name: wikitext-2-raw-v1
    split: "train[:2000]"
    type: completion
    field: text

sequence_len: 128
micro_batch_size: 1
gradient_accumulation_steps: 1

learning_rate: 2e-4
max_steps: 30
val_set_size: 0
logging_steps: 5

# Keep training output local, then copy to bucket after training.
output_dir: /workspace/output

lora_r: 8
lora_alpha: 16
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj
```

Upload config:

```bash
aws s3 cp src/config.yaml s3://fine-tuning-axolotl/config.yaml
```

### 2) Run fine-tuning job

Run the job:

```bash
nebius ai job create \
  --name "fine-tuning-axolotl-qwen-lora" \
  --image docker.io/axolotlai/axolotl:main-20260309-py3.11-cu128-2.9.1 \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --disk-size 450Gi \
  --volume "${BUCKET_ID}:/workspace/data" \
  --container-command bash \
  --args '-c "RUN_ID=run-$(date +%Y%m%d-%H%M%S); axolotl train /workspace/data/config.yaml && mkdir -p /workspace/data/output/$RUN_ID && cp -r /workspace/output/. /workspace/data/output/$RUN_ID"'
```

### 3) Check results

Get job ID:

```bash
nebius ai job get-by-name --name fine-tuning-axolotl-qwen-lora
```

Inspect status and logs:

```bash
nebius ai job get <job-id>
nebius ai logs <job-id>
```

Download adapter artifacts:

```bash
# Pick a run ID first (example):
aws s3 ls s3://fine-tuning-axolotl/output/
export RUN_ID=<run-YYYYMMDD-HHMMSS>

aws s3 cp --recursive s3://fine-tuning-axolotl/output/$RUN_ID ./download/output
```

## Expected output

- training job enters `RUNNING`, then `COMPLETED`
- job logs show Axolotl progress and checkpoints
- adapter artifacts are available under `s3://fine-tuning-axolotl/output/...`

## How to adapt it

- increase/decrease `max_steps` for quick validation vs fuller fine-tuning
- swap base model and dataset in `config.yaml`
- change platform/preset for larger models or faster turnaround

## Troubleshooting

### Debug session (keep container alive on failure)

Use this variant when you need to SSH in and inspect the environment after a failed run:

```bash
nebius ai job create \
  --name "fine-tuning-axolotl-debug" \
  --image docker.io/axolotlai/axolotl:main-20260309-py3.11-cu128-2.9.1 \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --disk-size 450Gi \
  --volume "${BUCKET_ID}:/workspace/data" \
  --ssh-key "$(cat ~/.ssh/id_rsa.pub)" \
  --container-command bash \
  --args '-c "RUN_ID=debug-$(date +%Y%m%d-%H%M%S); axolotl train /workspace/data/config.yaml && mkdir -p /workspace/data/output/$RUN_ID && cp -r /workspace/output/. /workspace/data/output/$RUN_ID || (echo FAILED; sleep 86400)"'
```

If training fails, the container sleeps for 24 hours so you can debug manually.

### S3 mount limitation (`debug.log` permission error)

### Symptom

You may see this error in job logs:

```text
PermissionError: [Errno 1] Operation not permitted: '/workspace/data/output/debug.log'
```

### Why this happens

Axolotl manages `debug.log` under `output_dir` (including delete/overwrite behavior during setup).
If `output_dir` points to an S3-backed mounted path such as `/workspace/data/output`, filesystem operations like `unlink` may fail because mounted object storage is not a full POSIX filesystem.

### Fix

Use a local path for Axolotl working output, then copy artifacts to the mounted bucket path after training.

In `config.yaml`:

```yaml
# Keep Axolotl writes on local filesystem.
dataset_prepared_path: /tmp/output/last_run_prepared
output_dir: /tmp/output
```

In job command args:

```bash
axolotl train /workspace/data/config.yaml && cp -r /tmp/output/. /workspace/data/output/
```

With debug wrapper (keep session open on failure):

```bash
-c "axolotl train /workspace/data/config.yaml && cp -r /tmp/output/. /workspace/data/output/ || (echo FAILED; sleep 86400)"
```

### Before / After

- before: `output_dir: /workspace/data/output`
- after: `output_dir: /tmp/output`
- additional step: copy local artifacts to bucket path after successful training

This keeps Axolotl file operations local and still persists checkpoints/adapters to Object Storage.

## See also

- [Official fine-tuning tutorial](https://docs.nebius.com/serverless/tutorials/fine-tuning)
- [Axolotl quickstart](https://docs.axolotl.ai/docs/getting-started.html)
- [Axolotl GitHub](https://github.com/axolotl-ai-cloud/axolotl)
