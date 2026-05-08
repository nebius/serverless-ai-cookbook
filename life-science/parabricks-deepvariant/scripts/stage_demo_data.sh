#!/usr/bin/env bash
# One-shot: stage the GRCh38 reference bundle and HG002 30x WGS FASTQ into
# the customer's Nebius Object Storage bucket. Runs as a CPU-only Nebius AI
# Job so the transfer happens inside Nebius (fast) rather than via the
# customer's laptop.

set -euo pipefail

: "${S3_BUCKET:?S3_BUCKET required}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required}"
: "${AWS_DEFAULT_REGION:=eu-north1}"

PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-16vcpu-64gb}"
JOB_NAME="parabricks-stage-demo-$(date +%s)"

# Inline staging script that runs inside the job container.
read -r -d '' STAGE_SCRIPT <<'EOF' || true
set -euo pipefail
yum install -y aws-cli wget tar
aws configure set region "$AWS_DEFAULT_REGION"
aws configure set endpoint_url "$S3_ENDPOINT_URL"
mkdir -p /scratch/ref /scratch/hg002 && cd /scratch

# 1) GRCh38 reference bundle from Broad's public bucket.
for f in \
    Homo_sapiens_assembly38.fasta \
    Homo_sapiens_assembly38.fasta.fai \
    Homo_sapiens_assembly38.dict \
    Homo_sapiens_assembly38.fasta.64.amb \
    Homo_sapiens_assembly38.fasta.64.ann \
    Homo_sapiens_assembly38.fasta.64.bwt \
    Homo_sapiens_assembly38.fasta.64.pac \
    Homo_sapiens_assembly38.fasta.64.sa ; do
    wget -q -O "ref/$f" "https://storage.googleapis.com/genomics-public-data/references/GRCh38/$f"
    aws s3 cp --endpoint-url "$S3_ENDPOINT_URL" "ref/$f" "s3://$S3_BUCKET/parabricks/ref/grch38/$f"
done

# 2) HG002 30x WGS FASTQ (paired) from NIST GIAB on NIH bucket.
for fq in \
    HG002.novaseq.pcr-free.30x.R1.fq.gz \
    HG002.novaseq.pcr-free.30x.R2.fq.gz ; do
    wget -q -O "hg002/$fq" "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/AshkenazimTrio/HG002_NA24385_son/NIST_HiSeq_HG002_Homogeneity-10953946/NHGRI_Illumina300X_AJtrio_novoalign_bams/$fq" || \
    # Some mirror paths differ. Fallback list:
    wget -q -O "hg002/$fq" "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data_indexes/AshkenazimTrio/sequence.index.AJtrio_Illumina_2x250bps_06012016/HG002/$fq"
    aws s3 cp --endpoint-url "$S3_ENDPOINT_URL" "hg002/$fq" "s3://$S3_BUCKET/parabricks/demo/hg002/$fq"
done

echo "Staging complete."
EOF

set -x
nebius ai job create \
    --name "$JOB_NAME" \
    --image amazonlinux:2 \
    --platform "$PLATFORM" \
    --preset "$PRESET" \
    --disk-size 500Gi \
    --env "S3_BUCKET=$S3_BUCKET" \
    --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL" \
    --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" \
    --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" \
    --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" \
    --container-command bash \
    --args "-c \"$STAGE_SCRIPT\""
