---
title: MONAI Medical Imaging on Nebius AI Jobs
category: life-sciences
type: batch-job
runtime: nebius-ai-jobs
frameworks: [monai, pytorch, python]
keywords: [medical-imaging, segmentation, synthetic-data, serverless-jobs, s3, gpu]
difficulty: intermediate
---

# MONAI Medical Imaging on Nebius AI Jobs

This recipe runs a small MONAI inference workflow as a run-to-completion Nebius AI Job. It generates a synthetic 3D medical-imaging phantom at runtime, runs MONAI sliding-window segmentation inference, and writes image, mask, metadata, preview, and log artifacts.

The example is intentionally bounded and nonclinical:

- It uses synthetic data only. No PHI, patient records, or clinical images are used.
- The predictor is a deterministic threshold model for a synthetic target, not a trained clinical model.
- Outputs are for education and research workflow validation only. They are not diagnosis, triage, treatment guidance, or clinical validation evidence.

## Contents

- [Run Profile](#run-profile)
- [Prerequisites](#prerequisites)
- [1. Run Locally](#1-run-locally)
- [2. Build and Validate the Container](#2-build-and-validate-the-container)
- [3. Push Your Image](#3-push-your-image)
- [4. Run on Nebius AI Jobs](#4-run-on-nebius-ai-jobs)
- [5. Add Object Storage Output](#5-add-object-storage-output)
- [Expected Outputs](#expected-outputs)
- [Cleanup](#cleanup)
- [Related NIM Routes](#related-nim-routes)
- [Troubleshooting](#troubleshooting)

## Run Profile

- Compute: start with `gpu-l40s-a`, preset `1gpu-8vcpu-32gb`.
  If your sandbox exposes only B200, use `gpu-b200-sxm-a` with
  `1gpu-20vcpu-224gb`.
- Timeout: `1h`, the minimum supported job timeout. The default synthetic run should finish much faster.
- Input data: synthetic 3D phantom generated inside the job.
- Output mode: local/job disk by default, optional S3-compatible Nebius Object Storage upload.
- Best for: validating MONAI container, job logs, artifact generation, and object-storage persistence.

The Dockerfile uses a PyTorch CUDA 13 runtime so the same recipe can run on
Blackwell/B200 GPUs as well as earlier CUDA-capable GPUs.

Use a larger GPU only after you increase volume size, use a trained model, or add a real public benchmark dataset.

## Prerequisites

Install and authenticate the local tools:

```bash
nebius profile current
docker --version
python3 --version
```

For the Serverless path, you also need:

- Access to Nebius Serverless AI Jobs.
- A container registry repository reachable by Nebius AI Jobs.
- Optional: Nebius Object Storage plus S3 credentials for persistent artifacts.

Run commands from this recipe directory:

```bash
cd life-science/monai-medical-imaging-job
```

## 1. Run Locally

Create a local Python environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Run a CPU smoke test with a smaller synthetic volume:

```bash
python -m monai_job.run \
  --case-id local-smoke \
  --shape 64,64,32 \
  --roi-size 32,32,16 \
  --device cpu \
  --output-dir outputs \
  --no-upload-s3
```

A successful run prints the selected device, inference time, and Dice score against the synthetic reference mask.

## 2. Build and Validate the Container

Build the image locally:

```bash
docker build --platform linux/amd64 -t monai-medical-imaging-job:0.1.0 .
```

Run the same bounded smoke test in Docker:

```bash
docker run --rm \
  -v "$PWD/results:/workspace/output" \
  monai-medical-imaging-job:0.1.0 \
  --case-id docker-smoke \
  --shape 64,64,32 \
  --roi-size 32,32,16 \
  --device cpu \
  --output-dir /workspace/output \
  --no-upload-s3
```

Or use the helper:

```bash
scripts/run_docker.sh --build \
  --case-id docker-smoke \
  --shape 64,64,32 \
  --roi-size 32,32,16 \
  --device cpu \
  --no-upload-s3
```

If your local Docker host has NVIDIA GPU support, set `USE_GPU=1` and use `--device cuda`.

## 3. Push Your Image

Tag and push the image to a registry available to Nebius AI Jobs. Example:

```bash
export IMAGE="cr.eu-north1.nebius.cloud/<project-id>/monai-medical-imaging-job:0.1.0"

docker tag monai-medical-imaging-job:0.1.0 "$IMAGE"
docker push "$IMAGE"
```

Pin a digest for repeated event demos or regulated review workflows.

## 4. Run on Nebius AI Jobs

Submit the default synthetic job:

```bash
nebius ai job create \
  --name "monai-synthetic-segmentation" \
  --image "$IMAGE" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --timeout "1h" \
  --disk-size "100Gi" \
  --args "--case-id synthetic-phantom-001 --shape 96,96,64 --device auto --output-dir /workspace/output --no-upload-s3"
```

If your project requires an explicit subnet, add:

```bash
--subnet-id "$SUBNET_ID"
```

Follow logs:

```bash
nebius ai logs <job-id> --follow --timestamps
```

The job automatically exits after writing artifacts. Without Object Storage, those artifacts live only on the job's ephemeral disk and are removed when the job is cleaned up.

You can also use the helper script:

```bash
export IMAGE="cr.eu-north1.nebius.cloud/<project-id>/monai-medical-imaging-job:0.1.0"
scripts/run_serverless.sh
```

Optional helper overrides:

```bash
export PLATFORM="gpu-l40s-a"
export PRESET="1gpu-8vcpu-32gb"
export TIMEOUT="1h"
export SHAPE="96,96,64"
export DEVICE="auto"
```

## 5. Add Object Storage Output

Configure Nebius Object Storage through S3-compatible credentials:

```bash
export AWS_ACCESS_KEY_ID="<access-key-id>"
export AWS_SECRET_ACCESS_KEY="<secret-access-key>"
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="<bucket-name>"
export S3_PREFIX="monai-medical-imaging"
```

For shared environments, store the secret access key in MysteryBox and pass it with `--env-secret`:

```bash
export AWS_SECRET_ACCESS_KEY_SECRET="<secret-id>@<version-id>"
unset AWS_SECRET_ACCESS_KEY
```

Run the persistent job:

```bash
scripts/run_serverless.sh
```

When `S3_BUCKET` is set, the helper passes Object Storage variables and enables `--upload-s3`. Outputs are written under:

```text
s3://$S3_BUCKET/$S3_PREFIX/<run-id>/
```

List completed runs:

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" --endpoint-url "$S3_ENDPOINT_URL"
```

Download a run:

```bash
aws s3 sync \
  "s3://$S3_BUCKET/$S3_PREFIX/<run-id>/" \
  "./results/<run-id>/" \
  --endpoint-url "$S3_ENDPOINT_URL"
```

## Expected Outputs

Each run creates a unique output directory:

```text
<run-id>/
├── synthetic_ct_phantom.nii.gz
├── synthetic_target_mask.nii.gz
├── predicted_segmentation_mask.nii.gz
├── preview.png
├── metadata.json
└── run.log
```

`metadata.json` records:

- synthetic data provenance
- no-PHI and nonclinical safety flags
- MONAI and PyTorch versions
- selected device and CUDA availability
- input shape, ROI size, seed, and threshold
- Dice score against the synthetic reference mask
- optional `s3_output_uri`

`run.log` mirrors the main runtime events shown by `nebius ai logs`.

## Cleanup

Nebius AI Jobs clean up compute after completion. You still own persistent resources:

- Delete unneeded Object Storage prefixes:

  ```bash
  aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/<run-id>/" \
    --recursive \
    --endpoint-url "$S3_ENDPOINT_URL"
  ```

- Remove old container tags or digests from your registry when no longer needed.
- Cancel a running job if you launched the wrong image or parameters:

  ```bash
  nebius ai job cancel <job-id>
  ```

## Related NIM Routes

This recipe is a MONAI framework example, not a validated NVIDIA NIM deployment.

Related medical-imaging NIM routes such as NVIDIA VISTA-3D and NVIDIA MAISI can be useful future paths for segmentation or synthetic imaging workflows, but they should be treated as separate deployments with their own license, safety, data governance, and validation gates. Do not present this MONAI threshold example as evidence that a VISTA-3D, MAISI, or clinical model route has been validated.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `CUDA was requested` error | Use `--device auto` or confirm the job ran on a GPU platform. |
| Job finishes but no S3 outputs appear | Confirm `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, and the secret key or MysteryBox selector. |
| Image pull fails | Confirm the pushed image path, registry permissions, and private registry credentials if needed. |
| Output only appears in logs | Re-run with Object Storage enabled; ephemeral job disk is removed after completion. |
| `nebius ai job create` fails on platform or preset | List available platforms with `nebius compute platform list --parent-id "$PARENT_ID"` and override `PLATFORM` or `PRESET`. |

## Validation Status

The local CPU path is intended to be smoke-tested before publishing changes. The Serverless job command is documented but should be run in your own Nebius project after pushing the image and setting any required subnet or registry credentials.
