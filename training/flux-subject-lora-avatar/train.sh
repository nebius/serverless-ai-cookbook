#!/usr/bin/env bash
# Launch FLUX.2-dev subject-LoRA training as a Nebius Serverless AI Job.
#
# Operational defaults below come from a validated production run:
#   --preemptible            preemptible jobs schedule in ~90 s even when the
#                            on-demand GPU pool is tight (and cost less)
#   --restart-policy on-failure + checkpoint preseed = training resumes from
#                            the latest saved step after a preemption
#   --timeout 16h            the timeout is WALL CLOCK including preemption
#                            restarts and the ~90 GB model fetch - budget
#                            several times the pure training time (>= 12h)
#   --disk-size 400Gi        FLUX.2 model reconstruction is disk-hungry;
#                            TMPDIR and HF_HOME are redirected to /workspace
#
# Code-outside-image pattern: the ai-toolkit config and the entry script are
# uploaded to Object Storage and read by the job, so you can iterate without
# building any image.
#
# Required env: PARENT_ID, BUCKET_NAME, NB_REGION_ID, HF_TOKEN
# Optional env: SUBNET_ID, BUCKET_ID, PLATFORM, PRESET, JOB_TIMEOUT, PREFIX,
#               TRAIN_IMAGE, TRIGGER_WORD, WANDB_API_KEY, WANDB_ENTITY
set -euo pipefail

: "${PARENT_ID:?set PARENT_ID to your Nebius project id}"
: "${BUCKET_NAME:?set BUCKET_NAME to your Object Storage bucket}"
: "${NB_REGION_ID:?set NB_REGION_ID, e.g. eu-north1 or us-central1}"
: "${HF_TOKEN:?FLUX.2-dev is gated - export an HF token whose account accepted the model license}"

PLATFORM="${PLATFORM:-gpu-h200-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
JOB_TIMEOUT="${JOB_TIMEOUT:-16h}"
PREFIX="${PREFIX:-flux-avatar}"
TRIGGER_WORD="${TRIGGER_WORD:-TOK4ME}"
# Public ai-toolkit runtime image (MIT-licensed project). Pin a digest for
# reproducible reruns: docker.io/ostris/aitoolkit@sha256:<digest>
TRAIN_IMAGE="${TRAIN_IMAGE:-docker.io/ostris/aitoolkit:latest}"

SUBNET_ID="${SUBNET_ID:-$(nebius vpc subnet list --parent-id "$PARENT_ID" --format json | jq -r '.items[0].metadata.id')}"
BUCKET_ID="${BUCKET_ID:-$(nebius storage bucket get-by-name --name "$BUCKET_NAME" --parent-id "$PARENT_ID" --format json | jq -r '.metadata.id')}"

HERE="$(cd "$(dirname "$0")" && pwd)"
RUN_NAME="flux-avatar-$(date +%Y%m%d%H%M%S)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# ---- render the training config -------------------------------------------
sed "s/__RUN_NAME__/${RUN_NAME}/g" "$HERE/train_config.yaml" > "$STAGE/train.yaml"
# Guard: the trigger token must be set literally in the config (filename-based
# trigger inference is a known footgun - it lowercases and strips digits).
grep -q "trigger_word: \"${TRIGGER_WORD}\"" "$STAGE/train.yaml" || {
  echo "ERROR: train_config.yaml trigger_word does not match TRIGGER_WORD=${TRIGGER_WORD}." >&2
  echo "Edit the config (trigger_word + sample prompts) and your captions together." >&2
  exit 1
}

# ---- render the in-job entry script ---------------------------------------
cat > "$STAGE/entry.sh" <<'ENTRY'
#!/bin/bash
# In-job entry script. The job copies this file to local disk and execs it -
# never run a long-lived script directly from the S3 mount (the FUSE mount can
# return "Stale file handle" mid-run and crash-loop the job).
set -eu
export TMPDIR=/workspace/tmp HF_HOME=/workspace/hf-cache PYTHONUNBUFFERED=1
BUCKET=/workspace/bucket
DS="$BUCKET/__PREFIX__/dataset"
OUT="$BUCKET/__PREFIX__/output/__RUN_NAME__"
mkdir -p /workspace/tmp /workspace/hf-cache /workspace/work-dataset \
         /workspace/output "$OUT"

echo "== staging dataset to local disk =="
# Per-file cat + size verify: plain cp can trip on S3-FUSE metadata refresh,
# and the latent cache is written INTO the dataset folder, so training must
# run from a local copy anyway.
for f in "$DS"/*; do
  b=$(basename "$f"); ok=0
  for attempt in 1 2 3; do
    if cat "$f" > "/workspace/work-dataset/$b" 2>/dev/null && \
       [ "$(stat -c%s "$f")" = "$(stat -c%s "/workspace/work-dataset/$b")" ]; then
      ok=1; break
    fi
    sleep 2
  done
  [ "$ok" = 1 ] || { echo "failed to stage $b after 3 tries"; exit 1; }
done
NI=$(ls /workspace/work-dataset | grep -c '\.jpg$' || true)
NC=$(ls /workspace/work-dataset | grep -c '\.txt$' || true)
echo "staged pairs: images=$NI captions=$NC"
[ "$NI" -gt 0 ] && [ "$NI" = "$NC" ]

# Resume after preemption/restart: preseed checkpoints saved by an earlier
# attempt; ai-toolkit continues from the latest checkpoint it finds.
if [ -n "$(ls -A "$OUT" 2>/dev/null)" ]; then
  echo "== preseeding previous checkpoints (resume) =="
  cp -r "$OUT"/. /workspace/output/ || true
fi

cp "$BUCKET/__PREFIX__/jobs/__RUN_NAME__/train.yaml" /workspace/train.yaml

# The ai-toolkit image entrypoint location has moved between releases;
# discover run.py rather than hardcoding a path.
for c in /app/ai-toolkit /workspace/ai-toolkit /root/ai-toolkit /ai-toolkit /app /workspace; do
  if [ -f "$c/run.py" ]; then cd "$c"; break; fi
done
test -f run.py
echo "== ai-toolkit at $(pwd), starting training =="

# Train on local disk, sync artifacts to the bucket in the background and once
# more at the end - checkpoints survive preemption and timeouts this way.
sync_out() {
  ( cd /workspace/output 2>/dev/null || exit 0
    find . -type f | while IFS= read -r f; do
      d="$OUT/${f#./}"
      if [ ! -f "$d" ] || [ "$(stat -c%s "$f")" != "$(stat -c%s "$d")" ]; then
        mkdir -p "$(dirname "$d")" && cp -f "$f" "$d" && echo "[sync] $f"
      fi
    done ) || true
}
python -u run.py /workspace/train.yaml &
TRAIN_PID=$!
( while kill -0 "$TRAIN_PID" 2>/dev/null; do sleep 300; sync_out; done ) &
SYNC_PID=$!
RC=0
wait "$TRAIN_PID" || RC=$?
kill "$SYNC_PID" 2>/dev/null || true
echo "== training exited rc=$RC, final sync =="
sync_out
echo "== done rc=$RC =="
exit $RC
ENTRY
sed -i "s|__RUN_NAME__|${RUN_NAME}|g; s|__PREFIX__|${PREFIX}|g" "$STAGE/entry.sh"

# ---- upload job assets ------------------------------------------------------
aws --endpoint-url "https://storage.${NB_REGION_ID}.nebius.cloud" \
  s3 cp --recursive "$STAGE/" "s3://${BUCKET_NAME}/${PREFIX}/jobs/${RUN_NAME}/"

# ---- create the job ---------------------------------------------------------
# NOTE: --env values are visible to project members via `nebius ai job get`.
# In shared projects put HF_TOKEN / WANDB_API_KEY in a MysteryBox secret and
# use --env-secret KEY=<secret-selector> instead.
EXTRA_ARGS=()
if [ -n "${WANDB_API_KEY:-}" ]; then
  EXTRA_ARGS+=(--env "WANDB_API_KEY=${WANDB_API_KEY}")
  [ -n "${WANDB_ENTITY:-}" ] && EXTRA_ARGS+=(--env "WANDB_ENTITY=${WANDB_ENTITY}")
fi

echo "Creating job ${RUN_NAME} (create blocks until the workload is scheduled)..."
nebius ai job create \
  --name "$RUN_NAME" \
  --parent-id "$PARENT_ID" \
  --subnet-id "$SUBNET_ID" \
  --image "$TRAIN_IMAGE" \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --disk-size 400Gi \
  --shm-size 16Gi \
  --timeout "$JOB_TIMEOUT" \
  --preemptible \
  --restart-policy on-failure \
  --env "HF_TOKEN=${HF_TOKEN}" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} \
  --volume "${BUCKET_ID}:/workspace/bucket:rw" \
  --container-command bash \
  --args "-c \"cat /workspace/bucket/${PREFIX}/jobs/${RUN_NAME}/entry.sh > /workspace/entry.sh && exec bash /workspace/entry.sh\""

JOB_ID=$(nebius ai job get-by-name --parent-id "$PARENT_ID" --name "$RUN_NAME" \
  --format json | jq -r '.metadata.id')
cat <<EOF

Run name : $RUN_NAME
Job id   : $JOB_ID

Monitor:
  nebius ai job get $JOB_ID --format json | jq -r .status.state
  nebius ai logs $JOB_ID --follow

Artifacts land in:
  s3://${BUCKET_NAME}/${PREFIX}/output/${RUN_NAME}/${RUN_NAME}/
  (LoRA .safetensors checkpoints + sample image grids + the exact config)

After it completes, delete the job to free quota:
  nebius ai job delete $JOB_ID
EOF
