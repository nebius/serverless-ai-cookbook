#!/usr/bin/env bash
# Submit a benchmark run on a specific Nebius GPU SKU and render a markdown
# report in bench/results/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECIPE_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/results"

usage() {
    cat <<'EOF'
Usage: bench/run_bench.sh

Run a Parabricks DeepVariant benchmark job, wait for completion, fetch
run_metadata.json, and write bench/results/<date>-<sku>.md.

Required environment:
  SKU_LABEL             Label for the report, e.g. l40s, rtx6000, h200, b200, b300
  PLATFORM              Nebius AI Jobs platform value
  PRESET                Nebius AI Jobs preset value
  PIPELINE_IMAGE        Pipeline image in Nebius Container Registry
  S3_BUCKET             Object Storage bucket name
  S3_ENDPOINT_URL       Object Storage endpoint URL
  AWS_ACCESS_KEY_ID     Object Storage access key ID
  AWS_SECRET_ACCESS_KEY Object Storage secret access key, or set
                        AWS_SECRET_ACCESS_KEY_SECRET to a MysteryBox selector
  PARENT_ID             Project ID used for polling with get-by-name

Optional environment:
  HOURLY_RATE_USD SAMPLE_ID S3_OUTPUT_PREFIX AWS_DEFAULT_REGION
  BENCH_POLL_SECONDS BENCH_TIMEOUT_SECONDS JOB_NAME
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

: "${SKU_LABEL:?SKU_LABEL required (e.g. l40s, rtx6000, h200, b200, b300)}"
: "${PLATFORM:?PLATFORM required (for example, gpu-h200-sxm)}"
: "${PRESET:?PRESET required}"
: "${PIPELINE_IMAGE:?PIPELINE_IMAGE required}"
: "${S3_BUCKET:?S3_BUCKET required}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required}"
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -z "${AWS_SECRET_ACCESS_KEY_SECRET:-}" ]]; then
    echo "Error: set AWS_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY_SECRET." >&2
    exit 1
fi
: "${PARENT_ID:?PARENT_ID required for polling with nebius ai job get-by-name}"

command -v nebius >/dev/null || { echo "nebius CLI is required" >&2; exit 127; }
command -v aws >/dev/null || { echo "aws CLI is required to fetch run_metadata.json" >&2; exit 127; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 127; }

HOURLY_RATE_USD="${HOURLY_RATE_USD:-0.00}"
SAMPLE_ID="${SAMPLE_ID:-HG002}"
S3_OUTPUT_PREFIX="${S3_OUTPUT_PREFIX:-parabricks/out}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-north1}"
BENCH_POLL_SECONDS="${BENCH_POLL_SECONDS:-30}"
BENCH_TIMEOUT_SECONDS="${BENCH_TIMEOUT_SECONDS:-21600}"
JOB_NAME="${JOB_NAME:-parabricks-bench-${SKU_LABEL}-$(date +%s)}"

export AWS_DEFAULT_REGION

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -n "${AWS_SECRET_ACCESS_KEY_SECRET:-}" ]]; then
    SECRET_ID="${AWS_SECRET_ACCESS_KEY_SECRET%@*}"
    VERSION_ID=""
    if [[ "$AWS_SECRET_ACCESS_KEY_SECRET" == *@* ]]; then
        VERSION_ID="${AWS_SECRET_ACCESS_KEY_SECRET#*@}"
    fi

    SECRET_PAYLOAD="$TMP_DIR/aws-secret-payload.json"
    SECRET_CMD=(nebius mysterybox payload get --secret-id "$SECRET_ID" --format json)
    if [[ -n "$VERSION_ID" ]]; then
        SECRET_CMD+=(--version-id "$VERSION_ID")
    fi
    "${SECRET_CMD[@]}" >"$SECRET_PAYLOAD"

    AWS_SECRET_ACCESS_KEY="$(
        python3 - "$SECRET_PAYLOAD" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)

for item in payload.get("data") or []:
    value = item.get("string_value") or item.get("stringValue")
    if item.get("key") == "AWS_SECRET_ACCESS_KEY" and value:
        print(value)
        raise SystemExit

raise SystemExit("MysteryBox payload must contain an AWS_SECRET_ACCESS_KEY string value")
PY
    )"
    export AWS_SECRET_ACCESS_KEY
fi

JOB_NAME="$JOB_NAME" \
PARENT_ID="$PARENT_ID" \
PLATFORM="$PLATFORM" \
PRESET="$PRESET" \
PIPELINE_IMAGE="$PIPELINE_IMAGE" \
SAMPLE_ID="$SAMPLE_ID" \
S3_OUTPUT_PREFIX="$S3_OUTPUT_PREFIX" \
AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
"$RECIPE_DIR/scripts/run_serverless.sh"

echo "Waiting for job $JOB_NAME to finish..."
START_EPOCH="$(date +%s)"
EMPTY_STATUS_COUNT=0
while :; do
    STATUS_JSON="$TMP_DIR/status.json"
    STATUS_ERR="$TMP_DIR/status.err"
    if ! nebius ai job get-by-name \
        --name "$JOB_NAME" \
        --parent-id "$PARENT_ID" \
        --format json >"$STATUS_JSON" 2>"$STATUS_ERR"; then
        echo "Failed to poll job $JOB_NAME:" >&2
        cat "$STATUS_ERR" >&2
        exit 1
    fi

    STATUS="$(python3 -c '
import json
import sys

raw = open(sys.argv[1], encoding="utf-8").read().strip()
if not raw:
    print("")
    raise SystemExit
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print("")
    raise SystemExit
for path in (("status", "state"), ("status", "phase"), ("state",), ("phase",)):
    cur = payload
    for key in path:
        if not isinstance(cur, dict):
            cur = None
            break
        cur = cur.get(key)
    if cur:
        print(cur)
        break
else:
    print("")
' "$STATUS_JSON")"

    case "$STATUS" in
        Succeeded|SUCCEEDED|succeeded|Completed|COMPLETED|completed)
            echo "Final status: $STATUS"
            break
            ;;
        Failed|FAILED|failed|Cancelled|CANCELLED|cancelled|Canceled|CANCELED|canceled)
            echo "Final status: $STATUS"
            echo "Bench run failed; not writing results."
            exit 1
            ;;
    esac

    if [[ -z "$STATUS" ]]; then
        EMPTY_STATUS_COUNT=$((EMPTY_STATUS_COUNT + 1))
        if (( EMPTY_STATUS_COUNT >= 3 )); then
            echo "Unable to determine status for $JOB_NAME after ${EMPTY_STATUS_COUNT} polls." >&2
            echo "Last job payload:" >&2
            cat "$STATUS_JSON" >&2
            exit 1
        fi
    else
        EMPTY_STATUS_COUNT=0
    fi

    NOW="$(date +%s)"
    if (( NOW - START_EPOCH > BENCH_TIMEOUT_SECONDS )); then
        echo "Timed out waiting for $JOB_NAME after ${BENCH_TIMEOUT_SECONDS}s" >&2
        exit 1
    fi
    echo "Current status: ${STATUS:-unknown}; polling again in ${BENCH_POLL_SECONDS}s"
    sleep "$BENCH_POLL_SECONDS"
done

aws s3 cp --endpoint-url "$S3_ENDPOINT_URL" \
    "s3://$S3_BUCKET/${S3_OUTPUT_PREFIX%/}/$SAMPLE_ID/run_metadata.json" \
    "$TMP_DIR/run_metadata.json"

read_metadata() {
    python3 - "$TMP_DIR/run_metadata.json" "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)
value = payload.get(sys.argv[2], "")
print(value)
PY
}

WALL="$(read_metadata wall_clock_seconds)"
GPU="$(read_metadata gpu_name)"
PB_VER="$(read_metadata parabricks_version)"
COST="$(
    python3 - "$WALL" "$HOURLY_RATE_USD" <<'PY'
import decimal
import sys

wall = decimal.Decimal(str(sys.argv[1] or "0"))
rate = decimal.Decimal(str(sys.argv[2] or "0"))
print((wall / decimal.Decimal(3600) * rate).quantize(decimal.Decimal("0.01")))
PY
)"

DATE="$(date -u +%Y-%m-%d)"
REPORT="$RESULTS_DIR/${DATE}-${SKU_LABEL}.md"
mkdir -p "$RESULTS_DIR"

cat > "$REPORT" <<EOF
# Parabricks DeepVariant - ${SKU_LABEL} bench

- **Date:** ${DATE}
- **Sample:** ${SAMPLE_ID} (HG002 35x WGS)
- **Platform / preset:** ${PLATFORM} / ${PRESET}
- **GPU detected:** ${GPU}
- **Parabricks version:** ${PB_VER}
- **Wall clock:** ${WALL}s
- **Hourly rate (USD):** ${HOURLY_RATE_USD}
- **Sample cost (USD):** ${COST}
- **Pipeline image:** ${PIPELINE_IMAGE}
- **Job name:** ${JOB_NAME}
EOF

echo "Wrote $REPORT"
