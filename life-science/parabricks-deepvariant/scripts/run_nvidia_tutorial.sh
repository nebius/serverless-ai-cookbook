#!/usr/bin/env bash
# Run NVIDIA's official Parabricks tutorials on Nebius AI Jobs.
#
# Usage: run_nvidia_tutorial.sh <get-sample-data|fq2bam|haplotypecaller> [--platform <p>] [--preset <p>]
#
# Authenticates to NGC inline by default. For a more secure flow, set
# NGC_REGISTRY_SECRET to a Nebius MysteryBox secret selector with
# REGISTRY_USERNAME=$oauthtoken and REGISTRY_PASSWORD=<NGC API key> as the
# payload, and the script will use --registry-secret instead.

set -euo pipefail

NGC_IMAGE="${NGC_IMAGE:-nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1}"
PLATFORM="${PLATFORM:-gpu-h200-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
DISK_SIZE="${DISK_SIZE:-500Gi}"
JOB_NAME_PREFIX="${JOB_NAME_PREFIX:-parabricks-tutorial}"

usage() {
    cat <<EOF
Usage: $(basename "$0") <tutorial> [--platform <p>] [--preset <p>]

Tutorials:
  get-sample-data    Download Parabricks sample data into the container scratch.
  fq2bam             Run pbrun fq2bam against the sample data.
  haplotypecaller    Run pbrun haplotypecaller against the fq2bam output.

NGC auth:
  Default: export NGC_API_KEY=<key> ; the key is passed inline via
           --registry-username '\$oauthtoken' --registry-password "\$NGC_API_KEY".
           Trade-off: the key lands in shell history and CLI audit logs.
  Secure:  export NGC_REGISTRY_SECRET=<MysteryBox-selector> ; the script uses
           --registry-secret instead.
EOF
}

if [[ $# -lt 1 ]]; then
    usage; exit 1
fi
case "$1" in
    -h|--help) usage; exit 0 ;;
esac
TUTORIAL="$1"; shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --platform) PLATFORM="$2"; shift 2 ;;
        --preset)   PRESET="$2";   shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

case "$TUTORIAL" in
    get-sample-data)
        # NVIDIA's docs: https://docs.nvidia.com/clara/parabricks/latest/tutorials/samplebrca.html
        CONTAINER_CMD="bash"
        ARGS='-c "set -e; mkdir -p /workdir && cd /workdir && wget -q https://s3.amazonaws.com/parabricks.sample/parabricks_sample.tar.gz && tar xzf parabricks_sample.tar.gz && ls -la parabricks_sample/"'
        ;;
    fq2bam)
        CONTAINER_CMD="pbrun"
        ARGS='fq2bam --ref /workdir/parabricks_sample/Ref/Homo_sapiens_assembly38.fasta --in-fq /workdir/parabricks_sample/Data/sample_1.fq.gz /workdir/parabricks_sample/Data/sample_2.fq.gz --out-bam /workdir/fq2bam_output.bam'
        ;;
    haplotypecaller)
        CONTAINER_CMD="pbrun"
        ARGS='haplotypecaller --ref /workdir/parabricks_sample/Ref/Homo_sapiens_assembly38.fasta --in-bam /workdir/fq2bam_output.bam --out-variants /workdir/output.vcf'
        ;;
    *)
        usage; exit 1 ;;
esac

JOB_NAME="${JOB_NAME_PREFIX}-${TUTORIAL}-$(date +%s)"

# Build the auth flag set conditionally.
AUTH_FLAGS=()
if [[ -n "${NGC_REGISTRY_SECRET:-}" ]]; then
    AUTH_FLAGS+=(--registry-secret "$NGC_REGISTRY_SECRET")
elif [[ -n "${NGC_API_KEY:-}" ]]; then
    # NGC requires the literal username '$oauthtoken' — single quotes are intentional.
    # shellcheck disable=SC2016
    AUTH_FLAGS+=(--registry-username '$oauthtoken' --registry-password "$NGC_API_KEY")
else
    echo "Error: set NGC_API_KEY (inline) or NGC_REGISTRY_SECRET (MysteryBox selector)." >&2
    exit 1
fi

set -x
nebius ai job create \
    --name "$JOB_NAME" \
    --image "$NGC_IMAGE" \
    --platform "$PLATFORM" \
    --preset "$PRESET" \
    --disk-size "$DISK_SIZE" \
    --container-command "$CONTAINER_CMD" \
    --args "$ARGS" \
    "${AUTH_FLAGS[@]}"
