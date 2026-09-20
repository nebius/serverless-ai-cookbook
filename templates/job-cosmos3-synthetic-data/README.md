# Cosmos 3 Synthetic Data Generation

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/job/create?image=vllm%2Fvllm-omni%3Acosmos3&amp;command=curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftemplates%2Fjob-cosmos3-synthetic-data%2Fsrc%2Frun.sh%20-o%20%2Ftmp%2Frun.sh%20%26%26%20bash%20%2Ftmp%2Frun.sh&amp;platform=gpu-rtx6000-a&amp;preset=1gpu-24vcpu-218gb&amp;volume=%2Fdata&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-job.svg" alt="Create Job" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Renders a batch of Cosmos3-Nano videos — image-to-video from your robot or driving first frames, or text-to-video from prompts — straight into an Object Storage bucket, then exits. A preemptible RTX Pro 6000 job that resumes where it stopped.

**License:** [OpenMDW-1.1](https://openmdw.ai/license/1-1/) · **Source:** [Hugging Face](https://huggingface.co/nvidia/Cosmos3-Nano) · [NVIDIA Cosmos](https://github.com/nvidia/cosmos)

<!-- /factory:intro -->

## What you get

A Serverless **Job** that runs vLLM-Omni with Cosmos 3 inside the container, reads a
`prompts.jsonl`, renders each line as a 189-frame 720p clip (NVIDIA's canonical 7.9-second
setting), and writes into the bucket you mount at `/data`:

```text
/data/output/<run-id>/
  000-car_driving.mp4         one clip per prompt line, named by its id
  001-humanoid_robot.mp4
  000-car_driving.json        sidecar per clip: prompt, first frame, seed, sampling params, sha256, render seconds
  manifest.jsonl              all sidecars in one file, written when the batch finishes
  summary.json                counts, failures, elapsed time
```

The job ends when the batch is done, so you pay GPU time only while clips render. Because the
driver skips clips whose MP4 already exists, a **preempted** job (`--restart-policy on-failure`)
restarts and continues instead of starting over. Split a large batch across several jobs with
`SHARD=i/N` — each renders every N-th line into the same bucket.

The default deployment ships with a sample set (NVIDIA's three image-to-video assets: a
dashcam drive, a humanoid robot, a coastal road) so the first run needs no data at all.

## How to run it

1. **Click Create Job.** In the form, pick the **bucket** to mount at `/data` (any bucket in the
   same project; the job writes to `/data/output/`). Everything else is prefilled. Create.
2. **Watch progress** in the console log tab or:

   ```bash
   nebius ai job logs <aijob-id> --follow
   ```

   One line per clip: `clip 2/3 001-humanoid_robot 189f 1280x720 XXXs → /data/output/run-…/001-humanoid_robot.mp4`.
   The first ~10 minutes are image pull, weight download and warm-up.
3. **Collect results** from the bucket (console → Object Storage, or `aws s3 sync` against the
   bucket's S3 endpoint). Each MP4 pairs with its manifest line for dataset bookkeeping.

### Bring your own prompts

Upload a `prompts.jsonl` to the bucket and set env `PROMPTS=/data/prompts.jsonl` in the form
(or `PROMPTS=https://…` for a public URL). One JSON object per line:

```json
{"id": "ep042-frame0", "image": "/data/frames/ep042.jpg", "prompt": "The robot arm lowers, grasps the red cup and lifts it off the table.", "seed": 42}
{"id": "night-rain",  "prompt": "Dashcam view, city street at night in heavy rain, the car slows for a pedestrian crossing."}
```

- `image` (optional): a path under `/data` or a URL — present → image-to-video, absent → text-to-video.
- `prompt`: short prompts are fine; the Generator upsamples them. NVIDIA's dense "temporal captions" (see the sample set) give the most controllable motion.
- Optional per line: `seed`, `num_frames`, `size`, `fps`, `generate_sound`.

### Knobs (env vars in the form or `--env` in the CLI)

| Variable | Default | Notes |
| --- | --- | --- |
| `PROMPTS` | bundled sample set | path under `/data` or URL |
| `NUM_FRAMES` | `189` | 7.9 s at 24 fps; `81` renders ~2.5× faster for previews |
| `SIZE` | `1280x720` | `832x480` is ~4× faster |
| `GENERATE_SOUND` | `false` | `true` adds a synchronized AAC track (Nano/Super only) |
| `SHARD` | `0/1` | `i/N` for fan-out across N jobs |
| `CONCURRENCY` | `2` | jobs kept queued on the server; more does not speed up one GPU |
| `RUN_ID` | `run-<timestamp>` | output sub-folder |
| `MODEL` | `nvidia/Cosmos3-Nano` | `nvidia/Cosmos3-Edge` for a smaller, faster model |
| `GUARDRAILS` | `false` | `true` requires env `HF_TOKEN` with access to the gated `nvidia/Cosmos-1.0-Guardrail` |

> ⚠️ **Guardrails are off by default** for the same reason as in the
> [Generator endpoint template](../endpoint-cosmos3-generator/README.md): the guardrail
> repository is gated and the server exits without access. Set `GUARDRAILS=true` plus
> `HF_TOKEN` to enable them, and filter generated media before publishing it.

### Observed results

Validation run of the sample set (3 image-to-video clips, 189 frames, 720p) on a preemptible
RTX Pro 6000 in uk-south2, output to a mounted bucket:

| Stage | Measured |
| --- | --- |
| Job start → vLLM-Omni ready (image pull, 32.6 GiB weights, warm-up) | ~8 min |
| Render, 3 clips sequentially on one GPU | 17.9 min (≈ 6 min per clip) |
| Output | 3 × MP4 (h264 720p, 7.9 s), 3 sidecars, `manifest.jsonl`, `summary.json`; job `COMPLETED`, exit 0 |
| Resume after restart (earlier run) | driver skipped already-rendered clips and finished the rest |

`render_seconds` in the sidecars is wall time from submission, so with `CONCURRENCY=2` the
second clip in a pair shows ~2× the true render time; the GPU renders one clip at a time.

### Throughput and cost planning

| Clip | RTX Pro 6000 | H100 |
| --- | --- | --- |
| 720p, 189 frames (default) | ~6 min (measured) | ~3.5 min |
| 720p, 81 frames | ~1.8 min | ~1 min |
| 480p, 33 frames | ~15 s | ~10 s |

Plus ~10 minutes of start-up per job. For hundreds of clips, run N shards in parallel.

<!-- factory:cli -->

## CLI alternative

```bash
BUCKET=$(nebius storage bucket get-by-name --name <your-bucket> --format jsonpath='{.metadata.id}')

nebius ai job create \
  --name cosmos3-sdg-$(date +%Y%m%d-%H%M%S) \
  --image vllm/vllm-omni:cosmos3 \
  --platform gpu-rtx6000-a \
  --preset 1gpu-24vcpu-218gb \
  --preemptible \
  --restart-policy on-failure \
  --timeout 6h \
  --shm-size 32Gi \
  --disk-size 500Gi \
  --volume "$BUCKET:/data:rw" \
  --env PROMPTS=/data/prompts.jsonl \
  --container-command bash \
  --args '-c "curl -fsSL https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/main/templates/job-cosmos3-synthetic-data/src/run.sh -o /tmp/run.sh && bash /tmp/run.sh"'
```

Fan-out example — four jobs, four shards: add `--env SHARD=0/4` … `--env SHARD=3/4` and the
same `RUN_ID`. On H100 in eu-north1 use `--platform gpu-h100-sxm --preset 1gpu-16vcpu-200gb`.

<!-- /factory:cli -->

## Troubleshooting

- **Job FAILED right after start, log shows `curl: (22)`** — the launcher could not fetch `run.sh`; check egress and the URL.
- **`vLLM-Omni exited — last log lines` in the log** — the server died before serving; the lines that follow tell why (usually guardrails without `HF_TOKEN`, or out-of-memory on a smaller GPU).
- **Job restarted and repeated some clips** — a clip is only skipped once its MP4 is fully written; a clip interrupted mid-render is re-done. Expected.
- **`summary.json` lists failures** — the job exits 1 so that `on-failure` retries; a prompt that fails every time (e.g. unreadable `image`) will keep the job retrying until `--timeout`. Fix the line or remove it.
- **`PermissionError: Operation not permitted` writing under `/data`** — the bucket mount is object storage: files can be created but **not appended to or overwritten**. The driver writes every file exactly once (MP4, per-clip JSON sidecar, then `manifest.jsonl` and `summary.json` at the end); keep that rule if you modify it. Do not point `HF_HOME` or logs at the mount.
- **Want a live API instead of a batch?** — use the [Generator endpoint](../endpoint-cosmos3-generator/README.md).
