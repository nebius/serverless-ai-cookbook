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

This recipe shows how to run [NVIDIA Parabricks](https://docs.nvidia.com/clara/latest/) on [Nebius Serverless AI Jobs](https://docs.nebius.com/serverless/quickstart/jobs). It covers two flows: running NVIDIA's tutorial commands directly from the NGC Parabricks image, and building a small DeepVariant pipeline image that stages data from S3-compatible object storage.

Use the tutorial flow to verify NGC authentication and GPU job launch. Use the DeepVariant flow when you want a repeatable job that reads customer data from Object Storage and writes VCF, BAM, and run metadata back to the bucket.

## What You'll Learn

1. Run the official Parabricks sample-data, `fq2bam`, and `haplotypecaller` tutorials as Nebius AI Jobs.
2. Build a thin Parabricks DeepVariant image from the NGC base image.
3. Stage GRCh38 reference data and HG002 demo FASTQ files into Object Storage.
4. Submit a GPU DeepVariant job against S3 input and reference prefixes.
5. Optionally validate accuracy with `hap.py` and contribute benchmark results.

## Prerequisites

- Nebius CLI installed and authenticated. `nebius profile current` should show the project you want to use.
- Access to Serverless AI Jobs in a region with your target GPU SKU.
- Docker installed locally.
- AWS CLI installed locally for output inspection and benchmark result collection.
- An Object Storage bucket, S3 endpoint URL, and access keys.
- A Container Registry repository for Mode B and QA images.
- An NGC API key from [NGC](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/clara/containers/clara-parabricks). The Parabricks image is pulled from `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`.
- Local NGC login for Mode B image builds:

```bash
printf '%s' "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
```

Run all commands below from this recipe directory:

```bash
cd life-science/parabricks-deepvariant
```

Set the project and storage variables once and reuse them across the scripts:

```bash
export PARENT_ID="<project-id>"          # required by benchmark polling; optional for simple submits
export AWS_ACCESS_KEY_ID="<access-key-id>"
export AWS_SECRET_ACCESS_KEY="<secret-access-key>"
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="<bucket-name>"
```

For production runs, prefer storing the secret access key in MysteryBox and exporting a selector instead of the plaintext value:

```bash
export AWS_SECRET_ACCESS_KEY_SECRET="<secret-id>@<version-id>"
unset AWS_SECRET_ACCESS_KEY
```

`scripts/stage_demo_data.sh`, `scripts/run_serverless.sh`, and `scripts/run_qa.sh` use `--env-secret` when `AWS_SECRET_ACCESS_KEY_SECRET` is set.

If your project requires an explicit subnet, export it once and the helper scripts will pass it to `nebius ai job create`:

```bash
export SUBNET_ID="<subnet-id>"
```

## Mode A - Run NVIDIA's Tutorials on Nebius

Mode A uses the NGC Parabricks image directly. No Nebius image build is required. The helper script submits a standalone Nebius job for each tutorial step.

Each job is ephemeral, so the `fq2bam` and `haplotypecaller` helpers download the sample data inside the same job before running Parabricks. The `haplotypecaller` helper also runs `fq2bam` first so the BAM exists before variant calling.

### NGC Authentication

The low-friction path is to pass the NGC API key inline:

```bash
export NGC_API_KEY="<ngc-api-key>"
```

Then run a tutorial:

```bash
scripts/run_nvidia_tutorial.sh get-sample-data
```

This path passes `--registry-username '$oauthtoken' --registry-password "$NGC_API_KEY"` to `nebius ai job create`. It is convenient, but the key can appear in shell history, local process listings, and CLI audit logs.

For a safer path, store the NGC registry credentials in a Nebius MysteryBox secret with:

```text
REGISTRY_USERNAME=$oauthtoken
REGISTRY_PASSWORD=<ngc-api-key>
```

Then reference that secret selector:

```bash
export NGC_REGISTRY_SECRET="<secret-selector>"
scripts/run_nvidia_tutorial.sh get-sample-data
```

When `NGC_REGISTRY_SECRET` is set, the script uses `--registry-secret` and does not pass the NGC key inline. The selector can be a secret name, secret ID, version ID, or `SECRET_ID@VERSION_ID`; see the [`nebius ai job create` reference](https://docs.nebius.com/cli/reference/ai/job/create) for `--registry-secret` semantics.

Create the MysteryBox secret with the two required payload keys, or create it in the console. CLI example:

```bash
nebius mysterybox secret create \
  --parent-id "$PARENT_ID" \
  --name parabricks-ngc-registry \
  --secret-version-payload '[
    {"key":"REGISTRY_USERNAME","string_value":"$oauthtoken"},
    {"key":"REGISTRY_PASSWORD","string_value":"'"$NGC_API_KEY"'"}
  ]'

export NGC_REGISTRY_SECRET="parabricks-ngc-registry"
```

For more detail, see [How to create secrets in MysteryBox](https://docs.nebius.com/mysterybox/secrets/create).

### Getting the Sample Data

NVIDIA's sample-data tutorial downloads `parabricks_sample.tar.gz` and extracts the reference, FASTQ, and example files. The Nebius helper runs the same download inside the job and prints the extracted directory listing.

NVIDIA reference: [Getting The Sample Data](https://docs.nvidia.com/clara/latest/tutorials/gettingthesampledata.html)

```bash
scripts/run_nvidia_tutorial.sh get-sample-data
```

Override platform and preset if the defaults are not available in your project:

```bash
scripts/run_nvidia_tutorial.sh get-sample-data \
  --platform "<gpu-platform>" \
  --preset "<gpu-preset>"
```

### FQ2BAM Tutorial

The `fq2bam` helper downloads the sample data in the job, then runs Parabricks alignment against `sample_1.fq.gz` and `sample_2.fq.gz`.

NVIDIA reference: [FQ2BAM Tutorial](https://docs.nvidia.com/clara/latest/tutorials/fq2bam_tutorial.html)

```bash
scripts/run_nvidia_tutorial.sh fq2bam
```

Expected successful logs include Parabricks progress output and a final listing for `/workdir/fq2bam_output.bam`.

### HaplotypeCaller Tutorial

The `haplotypecaller` helper downloads the sample data, runs `fq2bam` to create `/workdir/fq2bam_output.bam`, then runs HaplotypeCaller to create `/workdir/output.vcf`.

NVIDIA reference: [HaplotypeCaller Tutorial](https://docs.nvidia.com/clara/latest/tutorials/haplotypecaller_tutorial.html)

```bash
scripts/run_nvidia_tutorial.sh haplotypecaller
```

Expected successful logs include both the `fq2bam` and `haplotypecaller` Parabricks progress sections.

## Mode B - Production DeepVariant Runs

Mode B builds a small customer-owned image from the NGC Parabricks base image. The Python wrapper downloads input and reference prefixes from Object Storage, runs `pbrun germline`, emits `run_metadata.json`, and uploads outputs back to S3.

### Stage Demo Data

Run this once per bucket to stage the GRCh38 reference bundle and HG002 FASTQ inputs under the default prefixes:

```bash
scripts/stage_demo_data.sh
```

Defaults:

```text
s3://$S3_BUCKET/parabricks/ref/grch38/
s3://$S3_BUCKET/parabricks/demo/hg002/
```

The staging job is CPU-only and uses `amazonlinux:2`. It downloads public reference and FASTQ files from Broad, Google-hosted reference data, and NIH GIAB mirrors, then uploads them into your bucket.

### Build and Push the Pipeline Image

Before pushing to Container Registry, create or choose a registry/repository path and configure Docker authentication. For local development, the usual setup is:

```bash
nebius registry configure-helper
```

See [Container Registry authentication](https://docs.nebius.com/container-registry/authentication) and the [`nebius registry` CLI reference](https://docs.nebius.com/cli/reference/registry) for registry creation and login options.

Build the image from this recipe directory:

```bash
docker build -t parabricks-deepvariant:dev .
```

Tag and push it to your Nebius Container Registry:

```bash
docker tag parabricks-deepvariant:dev \
  cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1

docker push cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1

export PIPELINE_IMAGE="cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1"
```

The image extends `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`, installs the Python S3 wrapper dependencies from `uv.lock`, and runs `python3 -m pipeline.cli`.

### Submit DeepVariant

With storage credentials and `PIPELINE_IMAGE` exported:

```bash
scripts/run_serverless.sh
```

The script passes these defaults:

```text
SAMPLE_ID=HG002
S3_INPUT_PREFIX=parabricks/demo/hg002
S3_REF_PREFIX=parabricks/ref/grch38
S3_OUTPUT_PREFIX=parabricks/out
DISK_SIZE=500Gi
```

Override them for your own data:

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

### Inspect Outputs

The output prefix is:

```text
s3://$S3_BUCKET/$S3_OUTPUT_PREFIX/$SAMPLE_ID/
```

For the default HG002 run:

```bash
aws s3 ls --endpoint-url "$S3_ENDPOINT_URL" \
  "s3://$S3_BUCKET/parabricks/out/HG002/"
```

Expected files include:

```text
HG002.vcf
HG002.bam
run_metadata.json
```

`run_metadata.json` records the sample ID, wall-clock seconds, GPU name from `nvidia-smi`, and Parabricks version from `pbrun --version`.

## GPU Recommendations

Exact platform and preset names can vary by region and project. Discover available values before running:

```bash
nebius compute platform list --parent-id "$PARENT_ID"
```

Use these SKU labels as a planning guide:

| GPU | Recommended use | Notes |
|---|---|---|
| L40S | Lowest-cost functional validation | Good first production smoke test. Expect longer WGS runtimes. |
| RTX6000 Ada | Cost-comparable validation to L40S | Useful if RTX6000 is more available in your region. |
| H200 | Balanced default for 35x HG002 | Good default for staging, smoke tests, and first benchmark runs. |
| B200 | Fast Blackwell baseline | Use for high-throughput production comparison. |
| B300 | Fastest target SKU in this recipe | Use for final benchmark coverage where available. |

Do not hardcode the table labels as CLI flags. Set `PLATFORM` and `PRESET` to the values returned by your project.

## Validate Accuracy (Optional)

The QA flow compares the produced VCF against GIAB HG002 v4.2.1 truth data with `hap.py`. It is CPU-only and reads the pipeline output from Object Storage.

Build and push the QA image:

```bash
docker build -t parabricks-qa:dev qa

docker tag parabricks-qa:dev \
  cr.eu-north1.nebius.cloud/<project>/parabricks-qa:0.1.0

docker push cr.eu-north1.nebius.cloud/<project>/parabricks-qa:0.1.0

export QA_IMAGE="cr.eu-north1.nebius.cloud/<project>/parabricks-qa:0.1.0"
```

Submit validation:

```bash
scripts/run_qa.sh
```

The validator downloads:

- your VCF from `s3://$S3_BUCKET/$S3_OUTPUT_PREFIX/$SAMPLE_ID/`
- GIAB HG002 v4.2.1 truth VCF, VCF index, and confidence BED from NIH public sources
- the GRCh38 FASTA and `.fai` reference used by `hap.py --engine=vcfeval`

It runs `hap.py` with the confidence BED and GRCh38 reference, then fails the job if SNP F1 is below `0.999`.

## Benchmark and Contribute Results

After the pipeline image is pushed and demo data is staged, run a benchmark for each target GPU SKU:

```bash
export PIPELINE_IMAGE="cr.eu-north1.nebius.cloud/<project>/parabricks-deepvariant:4.7.0-1"
export SKU_LABEL="h200"
export PLATFORM="<h200-platform>"
export PRESET="<h200-preset>"
export HOURLY_RATE_USD="0.00"
export PARENT_ID="<project-id>"

bench/run_bench.sh
```

The bench harness:

1. submits `scripts/run_serverless.sh`
2. polls `nebius ai job get-by-name`
3. downloads `run_metadata.json`
4. writes `bench/results/<YYYY-MM-DD>-<sku>.md`

Commit benchmark results with the SKU in the message, for example:

```bash
git add bench/results/2026-05-08-h200.md
git commit -m "Bench: H200 result for HG002 35x DeepVariant"
```

For this branch, the target matrix is L40S, RTX6000 Ada, H200, B200, and B300.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Pull access denied: nvcr.io/nvidia/clara/clara-parabricks` | NGC auth is missing or incorrect. | Export `NGC_API_KEY` or use `NGC_REGISTRY_SECRET`; for local builds, run `printf '%s' "$NGC_API_KEY" \| docker login nvcr.io -u '$oauthtoken' --password-stdin`. |
| Job stays in `Pending` | Platform or preset is unavailable in the selected region/project. | Discover available values with `nebius compute platform list --parent-id "<project-id>"`, then set `PLATFORM` and `PRESET`. |
| `S3 SignatureDoesNotMatch` | Endpoint URL, region, or credentials do not match the bucket. | Verify `S3_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, and access keys for the bucket region. |
| `pbrun: command not found` | The job is not using the Parabricks base image or the pipeline image was built from the wrong base. | Rebuild from this recipe's `Dockerfile` and confirm `FROM nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`. |
| `hap.py: vcfeval engine error` | QA reference or truth files were not fetched correctly. | Re-run the QA job and check network access to NIH GIAB sources. |
| OOM or disk errors during `fq2bam` | The preset or ephemeral disk is too small for sample data and intermediate BAMs. | Increase `DISK_SIZE` to at least `500Gi`; for larger WGS runs, use `1Ti` or more. |

## Local Development

Install dev dependencies and run tests from this directory:

```bash
uv run --extra dev pytest -v
uv run --extra dev ruff check .
shellcheck scripts/*.sh bench/*.sh
```

The pipeline and QA Dockerfiles are intentionally thin. Keep large reference data, FASTQ files, VCFs, and benchmark artifacts out of git except for small markdown reports under `bench/results/`.
