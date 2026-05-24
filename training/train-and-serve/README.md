---
title: Train and Serve TinyLlama with Serverless
category: training
type: job
runtime: gpu
frameworks:
  - pytorch
  - transformers
  - vllm
keywords:
  - finetuning
  - lora
  - object-storage
  - endpoint
difficulty: intermediate
---

# Train and Serve TinyLlama with Nebius Serverless

This example shows an end-to-end Serverless workflow for ML engineers who want to fine-tune a model, persist the adapter in Object Storage, and serve it behind an API without managing cluster infrastructure first.

It uses:

- a Serverless AI Job for fine-tuning
- Object Storage as the handoff point between training and serving
- a Serverless AI Endpoint running `vLLM` with a LoRA adapter

## What this example does

- fine-tunes `TinyLlama/TinyLlama-1.1B-Chat-v1.0` with LoRA in a Serverless AI Job
- stores the adapter output in Nebius Object Storage
- serves the base model plus adapter through a Serverless AI Endpoint

## Why this is useful

This is a practical pattern for short, iterative ML work:

- you can start from public runtime images
- keep training and serving code outside the image
- update `fine_tune.py`, `start.sh`, or `serve.sh` without rebuilding a container
- move from training to inference with the same bucket-mounted artifacts

For production, Git is usually the better source of truth for scripts and configs. The core pattern still holds: keep your code separate from the base runtime image unless you have a reason to freeze them together.

## Files in this folder

```text
training/train-and-serve/
├── README.md
├── fine_tune.py
├── start.sh
└── serve.sh
```

## Requirements

- Nebius CLI installed and authenticated
- `jq`
- an S3-compatible client such as the AWS CLI
- an Object Storage access key and secret
- quota for:
  - one Serverless AI Job
  - one Serverless AI Endpoint
  - Object Storage

If you need Object Storage credentials, see:

- [Working with Object Storage buckets and objects using the AWS CLI](https://docs.nebius.com/object-storage/interfaces/aws-cli)
- [Create your first bucket](https://docs.nebius.com/object-storage/quickstart)

## Runtime / compute

- training image: `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel`
- serving image: `vllm/vllm-openai:v0.7.3`
- example platform: `gpu-h200-sxm`
- example preset: `1gpu-16vcpu-200gb`

## Quickstart

### 1. Set variables and create the bucket

```bash
export PARENT_ID=project-u00nkqg6pr00v6bhssycnr
export NB_REGION_ID=us-central1
export AWS_ACCESS_KEY_ID=<your-object-storage-access-key>
export AWS_SECRET_ACCESS_KEY=<your-object-storage-secret>
export BUCKET_NAME=<globally-unique-bucket-name>

export SUBNET_ID=$(
  nebius vpc subnet list \
    --parent-id "$PARENT_ID" \
    --format json \
  | jq -r '.items[0].metadata.id'
)

export BUCKET_ID=$(
  nebius storage bucket create \
    --name "$BUCKET_NAME" \
    --parent-id "$PARENT_ID" \
    --format json \
  | jq -r '.metadata.id'
)
```

### 2. Upload the example files to Object Storage

```bash
chmod +x start.sh serve.sh

aws \
  --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp fine_tune.py "s3://$BUCKET_NAME/fine_tune.py"

aws \
  --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp start.sh "s3://$BUCKET_NAME/start.sh"

aws \
  --endpoint-url "https://storage.$NB_REGION_ID.nebius.cloud" \
  s3 cp serve.sh "s3://$BUCKET_NAME/serve.sh"
```

### 3. Create the fine-tuning job

```bash
nebius ai job create \
  --name "tinyllama-ft-$(date +%Y%m%d-%H%M%S)" \
  --parent-id "$PARENT_ID" \
  --subnet-id "$SUBNET_ID" \
  --image pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel \
  --container-command bash \
  --args "/mnt/data/start.sh" \
  --volume "${BUCKET_ID}:/mnt/data:rw" \
  --platform gpu-h200-sxm \
  --preset 1gpu-16vcpu-200gb \
  --disk-size 200Gi
```

This job mounts the bucket at `/mnt/data`, installs dependencies at startup, runs `fine_tune.py`, and saves the adapter output back to the bucket under `output/tinyllama-lora`.

### 4. Watch the job

```bash
nebius ai job list --parent-id "$PARENT_ID"
nebius ai job get <job-id>
nebius ai logs <job-id>
```

### 5. Verify the adapter output

After the job completes, the bucket should contain:

```text
output/tinyllama-lora/
├── README.md
├── adapter_config.json
├── adapter_model.safetensors
├── special_tokens_map.json
├── tokenizer.json
├── tokenizer.model
├── tokenizer_config.json
└── training_args.bin
```

This is a LoRA adapter package, not a fully merged copy of the base model.

### 6. Delete the completed job if you need quota back

If you are tight on GPU quota, remove the job before creating the endpoint:

```bash
nebius ai job delete <job-id>
```

### 7. Create the `vLLM` endpoint

```bash
nebius ai endpoint create \
  --name "tinyllama-vllm-$(date +%Y%m%d-%H%M%S)" \
  --parent-id "$PARENT_ID" \
  --subnet-id "$SUBNET_ID" \
  --image vllm/vllm-openai:v0.7.3 \
  --auth none \
  --container-port 8000 \
  --container-command bash \
  --args "/mnt/data/serve.sh" \
  --volume "${BUCKET_ID}:/mnt/data:ro" \
  --platform gpu-h200-sxm \
  --preset 1gpu-16vcpu-200gb \
  --public
```

The endpoint downloads the TinyLlama base model from Hugging Face and loads the LoRA adapter from the mounted bucket path.

### 8. Wait for the endpoint

```bash
nebius ai endpoint list --parent-id "$PARENT_ID"
nebius ai endpoint get <endpoint-id>
```

Get the public endpoint URL:

```bash
export ENDPOINT_URL=$(
  nebius ai endpoint get <endpoint-id> --format json \
  | jq -r '.status.public_endpoints[0]'
)
```

### 9. Test the endpoint

Health check:

```bash
curl "$ENDPOINT_URL/health"
```

Completion request:

```bash
curl -X POST "$ENDPOINT_URL/v1/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "prompt": "Explain Nebius object storage in one short paragraph.",
    "max_tokens": 128,
    "temperature": 0.7
  }'
```

## Expected output

- the job reaches `COMPLETED`
- the bucket contains `output/tinyllama-lora/...`
- the endpoint reaches `READY`
- `/health` returns `200`
- `/v1/completions` returns valid JSON

## Notes

- This example uses a public base model, so `HF_TOKEN` is optional.
- `start.sh` installs Python dependencies at runtime. That keeps the example simple, but it is slower than baking them into a custom image.
- `build-essential` is installed in the training container because some dependency paths can trigger native compilation during startup.

## Cleanup

Delete the endpoint when you are done:

```bash
nebius ai endpoint delete <endpoint-id>
```

Delete the bucket if you no longer need it:

```bash
nebius storage bucket delete "$BUCKET_ID"
```
