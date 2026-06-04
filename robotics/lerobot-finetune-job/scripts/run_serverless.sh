#!/bin/bash
# Submit a LeRobot fine-tuning job to Nebius AI Jobs.
#
# Usage:
#   ./scripts/run_serverless.sh [--debug] [POLICY] [DATASET] [STEPS]
#
# Positional arguments (all optional):
#   POLICY    act | diffusion  (default: act)
#   DATASET   HF dataset repo_id  (default: lerobot/pusht)
#   STEPS     Training steps  (default: 5000)
#
# Required environment variables:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
#   S3_BUCKET, S3_PREFIX, S3_ENDPOINT_URL
#
# Optional environment variables:
#   HF_TOKEN            HuggingFace token (for private datasets)
#   REGISTRY            Docker Hub user or org (default: mnrozhkov)
#   IMAGE_TAG           Image tag / version (default: v0.1.0)
#   IMAGE               Full image ref; overrides REGISTRY + IMAGE_TAG if set
#   SUBNET_ID           Nebius subnet ID (only needed when the project has multiple subnets)
#   JOB_PLATFORM        GPU platform  (default: gpu-h100-sxm)
#   JOB_PRESET          Resource preset  (default: 1gpu-16vcpu-200gb)
#   JOB_DISK            Disk size      (default: 450Gi)
#   JOB_TIMEOUT         Job timeout    (default: 6h)
#
# Options:
#   --debug   Warn on missing S3 env vars instead of exiting (results will be lost).
#   -h/--help Show this help.

set -e

DEBUG_MODE=false
POSITIONAL_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --debug)
            DEBUG_MODE=true
            ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            POSITIONAL_ARGS+=("$arg")
            ;;
    esac
done

POLICY="${POSITIONAL_ARGS[0]:-act}"
DATASET="${POSITIONAL_ARGS[1]:-lerobot/pusht}"
STEPS="${POSITIONAL_ARGS[2]:-5000}"

# Replace / with - for use in job name
DATASET_SLUG="${DATASET//\//-}"

# --- Image (override REGISTRY / IMAGE_TAG, or set IMAGE to the full ref) ---
REGISTRY="${REGISTRY:-mnrozhkov}"
IMAGE_TAG="${IMAGE_TAG:-v0.1.0}"
IMAGE="${IMAGE:-${REGISTRY}/lerobot-finetune:${IMAGE_TAG}}"

# --- Job configuration ---
JOB_PLATFORM="${JOB_PLATFORM:-gpu-h100-sxm}"
JOB_PRESET="${JOB_PRESET:-1gpu-16vcpu-200gb}"
JOB_TIMEOUT="${JOB_TIMEOUT:-6h}"
JOB_DISK="${JOB_DISK:-450Gi}"
SUBNET_ID="${SUBNET_ID:-}"

echo "LeRobot fine-tuning job"
echo "  Policy:   $POLICY"
echo "  Dataset:  $DATASET"
echo "  Steps:    $STEPS"
echo "  Platform: $JOB_PLATFORM / $JOB_PRESET"
echo "  Image:    $IMAGE"
if [ "$DEBUG_MODE" = true ]; then
    echo "  Mode:     debug (S3 vars optional — results may not persist)"
else
    echo "  Mode:     default (strict S3 validation)"
fi

# --- Validate required environment variables ---
echo ""
echo "Checking environment variables..."

required_vars=(
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_DEFAULT_REGION"
    "S3_BUCKET"
    "S3_PREFIX"
    "S3_ENDPOINT_URL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
        if [ "$DEBUG_MODE" = true ]; then
            echo "  WARNING: $var is not set"
        else
            echo "  MISSING: $var"
        fi
    else
        echo "  OK: $var"
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    if [ "$DEBUG_MODE" = true ]; then
        echo ""
        echo "Continuing in debug mode — checkpoint will be lost when the job VM is removed." >&2
    else
        echo ""
        echo "Missing required environment variables: ${missing_vars[*]}" >&2
        echo "Export them and re-run, or use --debug to skip validation." >&2
        exit 1
    fi
fi

# --- Build job create command ---
JOB_NAME="lerobot-${POLICY}-${DATASET_SLUG}-$(date +%Y%m%d%H%M%S)"
ARGS="--policy ${POLICY} --dataset ${DATASET} --steps ${STEPS}"

CREATE_CMD=(
    nebius ai job create
    --name "$JOB_NAME"
    --image "$IMAGE"
    --platform "$JOB_PLATFORM"
    --preset "$JOB_PRESET"
    --timeout "$JOB_TIMEOUT"
    --disk-size "$JOB_DISK"
    --args "$ARGS"
    --format "jsonpath={.metadata.id}"
)

# Append S3 env vars (only if set)
for var in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION \
           S3_BUCKET S3_PREFIX S3_ENDPOINT_URL; do
    if [ -n "${!var}" ]; then
        CREATE_CMD+=(--env "$var=${!var}")
    fi
done

# HuggingFace token (optional — lerobot/pusht is public)
if [ -n "${HF_TOKEN:-}" ]; then
    CREATE_CMD+=(--env "HF_TOKEN=$HF_TOKEN")
fi

# WANDB (optional)
if [ -n "${WANDB_API_KEY:-}" ]; then
    CREATE_CMD+=(--env "WANDB_API_KEY=$WANDB_API_KEY")
fi

# Multiple-subnet projects require an explicit subnet ID
if [ -n "$SUBNET_ID" ]; then
    CREATE_CMD+=(--subnet-id "$SUBNET_ID")
fi

echo ""
echo "Submitting job: $JOB_NAME"
JOB_ID=$("${CREATE_CMD[@]}")

echo ""
echo "Job submitted: $JOB_ID"
echo ""
echo "Follow logs:"
echo "  nebius ai logs $JOB_ID --follow"
echo ""
echo "Check status:"
echo "  nebius ai job get $JOB_ID"
echo ""
echo "After completion, download the checkpoint:"
echo "  aws s3 sync \"s3://\$S3_BUCKET/\$S3_PREFIX/${JOB_NAME}/\" \"./${JOB_NAME}/\""
