---
title: Fine-Tune on Spot GPUs with Automatic Retries
category: training
type: job
runtime: gpu
frameworks:
  - axolotl
  - prefect
keywords:
  - spot
  - preemption
  - checkpointing
  - qlora
  - qwen
difficulty: intermediate
---

# Fine-tune on spot GPUs with automatic retries

Spot GPUs are cheaper, but the platform can stop the VM at any time. This
example runs a QLoRA fine-tune of `Qwen/Qwen2.5-0.5B` on a spot H100 so
that a preemption costs only the steps since the last checkpoint:

1. A retry loop creates the GPU job with the `nebius` CLI and waits for it.
2. Inside the job, Axolotl copies every checkpoint to an Object Storage
   bucket. On SIGTERM it saves one more before the VM goes away.
3. If the job ends `Preempted`, the loop creates a new job. It copies the
   latest checkpoint from the bucket and continues from it. A new job that
   ends `NotEnoughResources` (no free spot VM) is retried the same way.

The retry loop can run in three places:

| Script | The loop runs on | Needs |
|---|---|---|
| `src/prefect/flow.py` | your machine, as a Prefect flow | nothing extra; it must stay on |
| `prefect_pipeline.py` | an on-demand CPU job, as a Prefect flow | a service account; a remote Prefect to watch it |
| `run_supervisor.py` | an on-demand CPU job, plain Python | a service account |

- **Requirements:** [Nebius CLI](https://docs.nebius.com/cli/install)
  with a configured profile, [uv](https://docs.astral.sh/uv/), an Object
  Storage bucket.
- **Compute:** 1× H100 spot per attempt, 2 h timeout each. Attempts are
  not counted; new ones start for up to 12 h (`--max-hours`). With
  `prefect_pipeline.py` or `run_supervisor.py`, also 1× on-demand `cpu-d3`
  VM for the whole run. Billable.

## Files

| File | Runs on | Does |
|---|---|---|
| `src/prefect/flow.py` | your machine or a CPU job | Prefect flow: creates the GPU job, retries it after preemption |
| `prefect_pipeline.py` | your machine | Runs `src/prefect/flow.py` on an on-demand CPU job |
| `run_supervisor.py` | your machine, then a CPU job | Starts a supervisor CPU job that retries the GPU job, without Prefect |
| `simulate_job_preemption.py` | your machine | Stops the VM under a running GPU job, as a spot preemption does |
| `src/nebius_jobs.py` | wherever the loop runs | Creates GPU and CPU jobs with the `nebius` CLI and waits for them |
| `src/prefect/cpu_job.sh` | the CPU job | Installs the `nebius` CLI, logs in as the service account, runs the loop |
| `src/axolotl/resumable_axolotl.py` | the GPU job | Restores the latest checkpoint, runs `axolotl train`, saves the adapter |
| `src/axolotl/checkpoint_plugin.py` | the GPU job | Copies each checkpoint to the bucket; saves one on SIGTERM |
| `src/axolotl/config.yaml` | the GPU job | Axolotl config: checkpoint every 200 steps, resume on start |

## Run

```bash
export BUCKET_ID=$(nebius storage bucket get-by-name --name <bucket> \
  --format jsonpath='{.metadata.id}')
```

Each run is named after its UTC start time, e.g.
`20261120-083035z-qwen05b-qlora`. Its jobs share the name: GPU attempts
are `...-qlora-1`, `...-qlora-2`, and the CPU job is `...-qlora-supervisor`
or `...-qlora-flow`. To continue an earlier run from its checkpoints, pass
its `--run-name` to any of the scripts.

### Prefect on your machine

```bash
uv run src/prefect/flow.py --bucket-id "$BUCKET_ID"
```

`uv` installs Prefect from the script header. By default, Prefect starts
a temporary local server.

To report to a remote Prefect instead, pass its API URL and put its
credentials in `~/.prefect/token` (or point `--prefect-token-file` at it):

```bash
echo "<credentials>" > ~/.prefect/token
chmod 600 ~/.prefect/token

uv run src/prefect/flow.py --bucket-id "$BUCKET_ID" \
  --prefect-api-url "https://<prefect-host>/api"
```

- **Prefect Cloud:** the URL is
  `https://api.prefect.cloud/api/accounts/<account-id>/workspaces/<workspace-id>`
  and the token is an API key.
- **Self-hosted server:** the token is the server's
  `PREFECT_SERVER_API_AUTH_STRING` (`user:password`). Without auth, skip
  the file.

The Prefect UI shows the flow's logs: job creation, state changes and
retries. Each attempt also adds an `attempt-<n>` link artifact to the
flow run, pointing to the GPU job in the Nebius console. Training logs stay
in `nebius ai job logs <id>`.

### Create a service account for CPU jobs

The loop on a CPU job creates GPU jobs with the `nebius` CLI, so it needs
a service account. Create one once, add it to the `editors` group, and
save its key:

```bash
export PROJECT_ID=$(nebius config get parent-id)
export TENANT_ID=<tenant-id>

export SA_ID=$(nebius iam service-account create --name spot-flow \
  --parent-id "$PROJECT_ID" --format jsonpath='{.metadata.id}')

export EDITORS_ID=$(nebius iam group get-by-name --name editors \
  --parent-id "$TENANT_ID" --format jsonpath='{.metadata.id}')
nebius iam group-membership create --parent-id "$EDITORS_ID" --member-id "$SA_ID"

nebius iam auth-public-key generate --service-account-id "$SA_ID" \
  --output ~/.nebius/spot-flow-credentials.json
```

### Prefect on a CPU job

```bash
uv run prefect_pipeline.py --bucket-id "$BUCKET_ID" \
  --credentials ~/.nebius/spot-flow-credentials.json \
  --prefect-api-url "https://<prefect-host>/api"
```

`prefect_pipeline.py` copies the code, the credentials and
`~/.prefect/token` into an on-demand CPU job named `<run-name>-flow`, and
prints its id. The job runs `src/prefect/flow.py`. Watch it in the
Prefect UI or with `nebius ai job logs <id> --follow`.

### Supervisor on a CPU job (no Prefect)

```bash
uv run run_supervisor.py --bucket-id "$BUCKET_ID" \
  --credentials ~/.nebius/spot-flow-credentials.json
```

`run_supervisor.py` creates an on-demand CPU job named
`<run-name>-supervisor` that runs the same script with `--supervise`.
There, a plain `for` loop runs the GPU attempts. Watch it with
`nebius ai job logs <id> --follow`.

### Simulate a preemption

Spot preemptions are rare, so to see a retry, cause one. Start a run with
any of the scripts above. Once attempt 1 has saved a checkpoint (its logs
show `copied checkpoint-200 to the bucket`), stop its VM:

```bash
uv run simulate_job_preemption.py <gpu-job-id>
```

The script stops the VM as the platform does: the container gets SIGTERM,
the checkpoint plugin saves a last checkpoint, and the job ends `FAILED
Preempted`. The retry loop then starts attempt 2, and its logs show
`resuming from checkpoint-N`.

## Expected output

Prefect flow, where attempt 1 is preempted:

```text
Task run 'fine_tune-...' - attempt 1: created aijob-...
Task run 'fine_tune-...' - aijob-... RUNNING
Task run 'fine_tune-...' - aijob-... FAILED
Task run 'fine_tune-...' - Task run failed with exception: SpotUnavailable(...) - Retry 1/360 will start in 120.0 seconds
Task run 'fine_tune-...' - attempt 2: created aijob-...
Task run 'fine_tune-...' - aijob-... RUNNING
Task run 'fine_tune-...' - aijob-... COMPLETED
Completed aijob-.... Logs: nebius ai job logs aijob-...
```

Supervisor logs, same case:

```text
attempt 1: created aijob-...
aijob-... RUNNING
aijob-... FAILED
aijob-... ended Preempted, retrying in 120 s
attempt 2: created aijob-...
aijob-... RUNNING
aijob-... COMPLETED
completed aijob-.... Adapter: spot-axolotl/<run-name>/final/
```

`nebius ai job logs <id>` of attempt 2 shows `resuming from
checkpoint-N`. The adapter is in the bucket under
`spot-axolotl/<run-name>/final/`.

## How to adapt

- **Model or data:** edit `src/axolotl/config.yaml`. Keep `output_dir`,
  `save_steps`, `auto_resume_from_checkpoints` and `plugins`.
- **GPU, disk, timeout:** the `nebius ai job create` flags in
  `create_gpu_job()` in `src/nebius_jobs.py`. The CPU job's are in
  `create_cpu_job()`.
- **Retries:** `--max-hours` is how long new attempts keep starting; their
  number is not limited. An attempt already running when time is up may
  still finish. The delay between attempts is `RETRY_DELAY_SECONDS`, and
  the retried reasons are `RETRY_REASONS`, both in `src/nebius_jobs.py`.

## Troubleshooting

- **Stopping the loop does not cancel the GPU job.** Run
  `nebius ai job cancel <id>`. On a CPU job, cancel both the `-flow` or
  `-supervisor` job and the running GPU job.
- **The CPU job fails at `nebius profile create` or `ai job create`.**
  Check that the service account is in the `editors` group and that the
  credentials file is the one from `auth-public-key generate`.
- **The loop stopped without a retry.** Only `Preempted` and
  `NotEnoughResources` are retried (`RETRY_REASONS` in
  `src/nebius_jobs.py`). Check `nebius ai job logs <id>` of the GPU job for
  the real error.
- **Attempts keep ending `NotEnoughResources`.** There is no free spot
  H100 right now. The loop keeps trying until `--max-hours` is up; check
  `nebius capacity resource-advice list` to see when capacity returns.
