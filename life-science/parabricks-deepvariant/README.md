---
title: Parabricks DeepVariant on Nebius AI Jobs
category: life-sciences
type: batch-job
runtime: nebius-ai-jobs
frameworks: [nvidia-parabricks, deepvariant, python]
keywords: [genomics, germline-variant-calling, serverless-jobs, s3, gpu]
difficulty: advanced
---

# Parabricks DeepVariant on Nebius AI Jobs

This cookbook recipe shows how to run NVIDIA Parabricks on Nebius. It has two paths:

1. **Run NVIDIA's Parabricks tutorials on Nebius AI Jobs.** This is the fastest way to verify NGC authentication, GPU scheduling, and Parabricks itself. No Object Storage bucket or custom image is needed.
2. **Run a reusable DeepVariant pipeline.** This builds a thin customer-owned image that stages FASTQ and reference data from S3-compatible Object Storage, runs `pbrun germline`, and writes VCF, BAM, and metadata back to the bucket.

Start with Path A if this is your first Parabricks run on Nebius. Move to Path B when you want persistent outputs or want to run your own data.

## Contents

- [Choose a Path](#choose-a-path)
- [Prerequisites](#prerequisites)
- [Configure Common Variables](#configure-common-variables)
- [Path A: Run NVIDIA Tutorials](#path-a-run-nvidia-tutorials)
- [Path B: Run DeepVariant from Object Storage](#path-b-run-deepvariant-from-object-storage)
- [Validate Accuracy](#validate-accuracy)
- [Benchmark a GPU SKU](#benchmark-a-gpu-sku)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Local Development](#local-development)

## Choose a Path

| Goal | Use this path | What you need |
|---|---|---|
| Verify that Parabricks starts on Nebius | [Path A](#path-a-run-nvidia-tutorials) | Nebius CLI, NGC API key, GPU AI Jobs access |
| Run NVIDIA's `get-sample-data`, `fq2bam`, and `haplotypecaller` tutorials | [Path A](#path-a-run-nvidia-tutorials) | Same as above |
| Run DeepVariant against S3 FASTQ/reference prefixes | [Path B](#path-b-run-deepvariant-from-object-storage) | Path A prerequisites plus Object Storage and Container Registry |
| Validate HG002 output against GIAB truth data | [Validate Accuracy](#validate-accuracy) | Completed Path B run plus QA image |
| Produce wall-clock and cost data for a GPU SKU | [Benchmark a GPU SKU](#benchmark-a-gpu-sku) | Completed Path B setup |

## Prerequisites

Install and authenticate the local tools:

```bash
nebius profile current
docker --version
aws --version
```

You need:

- Nebius CLI installed and authenticated to the project where you will run AI Jobs.
- Access to Nebius Serverless AI Jobs and at least one GPU platform.
- Docker installed locally for building the Path B and QA images.
- AWS CLI installed locally for inspecting S3-compatible Object Storage outputs.
- An NGC API key for `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`.
- For Path B only: an Object Storage bucket, S3 access key, and Nebius Container Registry repository.

Run all commands from this recipe directory:

```bash
cd life-science/parabricks-deepvariant
```

## Configure Common Variables

Set the project first. `PARENT_ID` is optional for simple submissions if your Nebius CLI profile already points at the right project, but exporting it makes polling and repeat runs easier.

```bash
export PARENT_ID="<project-id>"
```

Find platform and preset names available in your project:

```bash
nebius compute platform list --parent-id "$PARENT_ID"
```

The scripts default to H200 for GPU jobs:

```text
PLATFORM=gpu-h200-sxm
PRESET=1gpu-16vcpu-200gb
DISK_SIZE=500Gi
```

If those values are not available in your project, export values from `nebius compute platform list`:

```bash
export PLATFORM="<gpu-platform>"
export PRESET="<gpu-preset>"
```

If your project requires an explicit subnet, export it once:

```bash
export SUBNET_ID="<subnet-id>"
```

## Path A: Run NVIDIA Tutorials

Path A uses the official NVIDIA Parabricks image directly. Jobs are ephemeral: they download sample data, run the tutorial command, print logs, and then exit. Outputs are useful for verification but are not persisted after the job ends.

### 1. Configure NGC Authentication

For the quickest path, export the NGC API key:

```bash
export NGC_API_KEY="<ngc-api-key>"
```

The helper passes the key to `nebius ai job create` as `--registry-password`. This is convenient for a first run, but the key may appear in local shell history, process listings, and audit logs.

For production or shared environments, store the registry credentials in MysteryBox with these payload keys:

```text
REGISTRY_USERNAME=$oauthtoken
REGISTRY_PASSWORD=<ngc-api-key>
```

Then use the selector instead of `NGC_API_KEY`:

```bash
export NGC_REGISTRY_SECRET="<secret-id>@<version-id>"
unset NGC_API_KEY
```

Example CLI creation:

```bash
nebius mysterybox secret create \
  --parent-id "$PARENT_ID" \
  --name parabricks-ngc-registry \
  --secret-version-payload '[
    {"key":"REGISTRY_USERNAME","string_value":"$oauthtoken"},
    {"key":"REGISTRY_PASSWORD","string_value":"'"$NGC_API_KEY"'"}
  ]'
```

### 2. Run the Sample-Data Tutorial

This verifies that the Parabricks container pulls and starts.

```bash
scripts/run_nvidia_tutorial.sh get-sample-data
```

The script prints a job name like:

```text
Submitting Nebius AI Job: parabricks-tutorial-get-sample-data-...
```

Copy the job ID from the `nebius ai job create` response and follow logs:

```bash
nebius ai job logs <job-id> --follow --timestamps
```

Expected result: the logs show `parabricks_sample/` contents after downloading and extracting NVIDIA's sample archive.

NVIDIA reference: [Getting The Sample Data](https://docs.nvidia.com/clara/latest/tutorials/gettingthesampledata.html)

### 3. Run the FQ2BAM Tutorial

```bash
scripts/run_nvidia_tutorial.sh fq2bam
```

Expected result: Parabricks progress logs and a final `/workdir/fq2bam_output.bam` listing.

NVIDIA reference: [FQ2BAM Tutorial](https://docs.nvidia.com/clara/latest/tutorials/fq2bam_tutorial.html)

### 4. Run the HaplotypeCaller Tutorial

```bash
scripts/run_nvidia_tutorial.sh haplotypecaller
```

This helper downloads the sample data, runs `pbrun fq2bam`, then runs `pbrun haplotypecaller`.

Expected result: Parabricks progress logs and a final `/workdir/output.vcf` listing.

NVIDIA reference: [HaplotypeCaller Tutorial](https://docs.nvidia.com/clara/latest/tutorials/haplotypecaller_tutorial.html)

### Override GPU Platform for a Tutorial

You can pass platform and preset directly:

```bash
scripts/run_nvidia_tutorial.sh haplotypecaller \
  --platform "<gpu-platform>" \
  --preset "<gpu-preset>"
```

Or export defaults once:

```bash
export PLATFORM="<gpu-platform>"
export PRESET="<gpu-preset>"
scripts/run_nvidia_tutorial.sh fq2bam
```

## Path B: Run DeepVariant from Object Storage

Path B is the reusable pipeline path. It builds a small image from the Parabricks base image, stages input/reference data from Object Storage into job scratch space, runs `pbrun germline`, and uploads outputs.

The default demo run uses:

```text
SAMPLE_ID=HG002
S3_INPUT_PREFIX=parabricks/demo/hg002
S3_REF_PREFIX=parabricks/ref/grch38
S3_OUTPUT_PREFIX=parabricks/out
```

### 1. Configure Object Storage

Export bucket and S3 endpoint details:

```bash
export AWS_ACCESS_KEY_ID="<access-key-id>"
export AWS_SECRET_ACCESS_KEY="<secret-access-key>"
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="<bucket-name>"
```

For production, store the secret access key in MysteryBox and export a selector instead:

```bash
# The MysteryBox payload key must be AWS_SECRET_ACCESS_KEY.
export AWS_SECRET_ACCESS_KEY_SECRET="<secret-id>@<version-id>"
unset AWS_SECRET_ACCESS_KEY
```

The Path B scripts use `--env-secret` when `AWS_SECRET_ACCESS_KEY_SECRET` is set.

### 2. Stage Demo Reference and FASTQ Data

Run this once per bucket:

```bash
scripts/stage_demo_data.sh
```

This submits a CPU AI Job that downloads public GRCh38 reference files and HG002 35x FASTQ files, then uploads them to:

```text
s3://$S3_BUCKET/parabricks/ref/grch38/
s3://$S3_BUCKET/parabricks/demo/hg002/
```

Follow the staging job logs:

```bash
nebius ai job logs <job-id> --follow --timestamps
```

Confirm the staged prefixes:

```bash
aws s3 ls --endpoint-url "$S3_ENDPOINT_URL" \
  "s3://$S3_BUCKET/parabricks/ref/grch38/"

aws s3 ls --endpoint-url "$S3_ENDPOINT_URL" \
  "s3://$S3_BUCKET/parabricks/demo/hg002/"
```

### 3. Build and Push the Pipeline Image

Log in to NGC locally so Docker can pull the Parabricks base image:

```bash
printf '%s' "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
```

Configure Docker for Nebius Container Registry:

```bash
nebius registry configure-helper
```

Build from this recipe directory:

```bash
docker build -t parabricks-deepvariant:dev .
```

Tag and push to your registry path:

```bash
docker tag parabricks-deepvariant:dev \
  cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1

docker push cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1

export PIPELINE_IMAGE="cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1"
```

### 4. Submit the DeepVariant Job

Run the default HG002 demo:

```bash
scripts/run_serverless.sh
```

The script submits one GPU AI Job with the image and S3 environment variables. Follow logs:

```bash
nebius ai job logs <job-id> --follow --timestamps
```

Expected successful logs include:

```text
Parabricks accelerated Genomics Pipeline
Variant caller done
run_metadata.json
```

### 5. Run Your Own FASTQ Data

Upload your FASTQ pair and matching reference bundle to Object Storage, then override the input variables:

```bash
SAMPLE_ID="sample-001" \
S3_INPUT_PREFIX="customers/sample-001/fastq" \
S3_REF_PREFIX="references/grch38" \
S3_OUTPUT_PREFIX="runs/sample-001" \
PLATFORM="<gpu-platform>" \
PRESET="<gpu-preset>" \
DISK_SIZE="1Ti" \
scripts/run_serverless.sh
```

The input prefix must contain a paired FASTQ set using common names such as:

```text
sample_1.fq.gz
sample_2.fq.gz
sample.R1.fastq.gz
sample.R2.fastq.gz
sample_R1.fastq.gz
sample_R2.fastq.gz
```

The reference prefix must contain the FASTA plus indexes needed by Parabricks.

### 6. Inspect Outputs

The output prefix is:

```text
s3://$S3_BUCKET/$S3_OUTPUT_PREFIX/$SAMPLE_ID/
```

For the default demo run:

```bash
aws s3 ls --endpoint-url "$S3_ENDPOINT_URL" \
  "s3://$S3_BUCKET/parabricks/out/HG002/"
```

Expected files:

```text
HG002.vcf
HG002.bam
run_metadata.json
```

Download metadata:

```bash
aws s3 cp --endpoint-url "$S3_ENDPOINT_URL" \
  "s3://$S3_BUCKET/parabricks/out/HG002/run_metadata.json" -
```

`run_metadata.json` includes sample ID, wall-clock seconds, detected GPU name, and Parabricks version.

## Validate Accuracy

The QA flow compares the DeepVariant VCF against GIAB HG002 v4.2.1 truth data with `hap.py`. It is CPU-only.

Build and push the QA image:

```bash
docker build -t parabricks-qa:dev qa

docker tag parabricks-qa:dev \
  cr.eu-north1.nebius.cloud/<project>/parabricks-qa:0.1.0

docker push cr.eu-north1.nebius.cloud/<project>/parabricks-qa:0.1.0

export QA_IMAGE="cr.eu-north1.nebius.cloud/<project>/parabricks-qa:0.1.0"
```

Submit validation for the default HG002 output:

```bash
scripts/run_qa.sh
```

For a custom output prefix, keep `SAMPLE_ID` and `S3_OUTPUT_PREFIX` aligned with the DeepVariant run:

```bash
SAMPLE_ID="sample-001" \
S3_OUTPUT_PREFIX="runs/sample-001" \
scripts/run_qa.sh
```

The validator downloads the VCF from Object Storage, fetches GIAB truth and confidence BED files from public NIH sources, runs `hap.py`, and fails the job if SNP F1 is below `0.999`.

## Benchmark a GPU SKU

After Path B is working, use the benchmark helper to submit a run, wait for completion, fetch `run_metadata.json`, and write a markdown report under `bench/results/`.

```bash
export SKU_LABEL="h200"
export PLATFORM="<h200-platform>"
export PRESET="<h200-preset>"
export HOURLY_RATE_USD="0.00"

bench/run_bench.sh
```

The benchmark helper writes:

```text
bench/results/<YYYY-MM-DD>-<sku>.md
```

Commit benchmark reports with the SKU in the commit message:

```bash
git add bench/results/2026-05-08-h200.md
git commit -m "Bench: H200 result for HG002 35x DeepVariant"
```

Bench reports land under `bench/results/` as `<YYYY-MM-DD>-<sku>.md`, one file per SKU per run. Reports are produced by `bench/run_bench.sh` on Nebius AI Jobs.

## Project Structure

```text
life-science/parabricks-deepvariant/
├── Dockerfile                  # Path B pipeline image
├── README.md                   # This cookbook
├── pipeline/                   # S3 staging and pbrun germline wrapper
├── qa/                         # hap.py validation image and script
├── scripts/
│   ├── run_nvidia_tutorial.sh  # Path A tutorials
│   ├── stage_demo_data.sh      # Stage GRCh38 + HG002 into Object Storage
│   ├── run_serverless.sh       # Submit Path B DeepVariant job
│   └── run_qa.sh               # Submit QA validation job
├── bench/
│   ├── run_bench.sh
│   └── results/
└── tests/
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Pull access denied: nvcr.io/nvidia/clara/clara-parabricks` | NGC auth is missing or incorrect. | Export `NGC_API_KEY` or use `NGC_REGISTRY_SECRET`; for local builds, run `printf '%s' "$NGC_API_KEY" \| docker login nvcr.io -u '$oauthtoken' --password-stdin`. |
| Job stays in `Pending` or `PROVISIONING` | Platform or preset is unavailable, or capacity is not currently schedulable. | Try another platform/preset from `nebius compute platform list --parent-id "$PARENT_ID"` or retry later. |
| `S3 SignatureDoesNotMatch` | Endpoint URL, region, or credentials do not match the bucket. | Verify `S3_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, and access keys for the bucket region. |
| `AccessDenied` or `Forbidden` from S3 | The Object Storage key cannot read or write the requested prefix. | Grant `ListBucket`, `GetObject`, and `PutObject` on the input, reference, and output prefixes. |
| `mysterybox secret ... is invalid, must have AWS_SECRET_ACCESS_KEY key` | The MysteryBox payload key does not match the environment variable requested by `--env-secret`. | Create the secret payload with key `AWS_SECRET_ACCESS_KEY`. |
| `pbrun: command not found` | The job is not using the Parabricks base image or the pipeline image was built from the wrong base. | Rebuild from this recipe's `Dockerfile` and confirm `FROM nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`. |
| FASTQ pair not found | The input prefix does not contain a supported paired FASTQ naming pattern. | Use names ending in `_1.fq.gz` / `_2.fq.gz`, `.R1.fastq.gz` / `.R2.fastq.gz`, or `_R1.fastq.gz` / `_R2.fastq.gz`. |
| OOM or disk errors during `fq2bam` | The preset or ephemeral disk is too small for sample data and intermediate BAMs. | Increase `DISK_SIZE` to at least `500Gi`; for larger WGS runs, use `1Ti` or more. |
| `hap.py` validation fails to fetch truth files | The QA job cannot reach NIH public sources. | Re-run after checking outbound network access, or stage truth files yourself and adapt `qa/validate.py`. |

## Local Development

Install dev dependencies and run checks from this recipe directory:

```bash
uv run --extra dev pytest -v
uv run --extra dev ruff check .
shellcheck scripts/*.sh bench/*.sh
```

The pipeline and QA Dockerfiles are intentionally thin. Keep reference data, FASTQ files, VCFs, BAMs, and runtime artifacts out of git except for small markdown reports under `bench/results/`.
