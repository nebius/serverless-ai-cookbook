# Training on spot GPUs

This guide explains how to use preemptible (spot) GPUs on Nebius
Serverless AI for training, without losing work when one is taken away.
It walks through the example in this folder. The [README](README.md) has
the full list of files, commands and options.

## What preemptible VMs are

### Cheap and available, but can be stopped at any time

A preemptible VM costs less than an on-demand VM, and there are often more
of them free. The catch: the platform can stop it at any time, for example
when on-demand customers need the capacity. A job on such a VM ends, and
the platform does not restart it.

Before you start, check what is free right now:

```bash
TENANT_ID=$(nebius iam project get $(nebius config get parent-id) \
  --format jsonpath='{.metadata.parent_id}')
nebius capacity resource-advice list --parent-id "$TENANT_ID" --all --format json
```

Each entry is one platform and preset in one region, e.g. `gpu-h100-sxm`
with `1gpu-16vcpu-200gb` in `eu-north1`. For `on_demand` and `preemptible`
it shows:

- `available` of `limit`: how many VMs you could start now, within your
  quota.
- `availability_level`: `LOW`, `MEDIUM`, `HIGH` or `LIMIT_REACHED`.

The same data is in the console, under **Administration → Capacity
Dashboard** (`https://console.nebius.com/<tenant-id>/capacity-dashboard`).
It is a snapshot, not a reservation: a VM that is free now can be gone by
the time your job starts.

### Compare prices

- Spot prices: https://nebius.com/spot-prices
- On-demand prices: https://nebius.com/prices

## How a job learns it is interrupted

**Inside the job.** When the platform stops a spot VM, the container gets
`SIGTERM`, then about 60 seconds later `SIGKILL`. That minute is the time
to save a checkpoint.

The simplest way to use it in Python: the handler only sets a flag, and
the training loop saves after the current step.

```python
import signal
import time

stopping = False


def on_sigterm(signum, frame):
    # 60 seconds until termination
    global stopping
    stopping = True
    
    
signal.signal(signal.SIGTERM, on_sigterm)

for step in range(1, 1001):
    time.sleep(1)  # one training step
    if stopping:
        print(f"SIGTERM: saving a checkpoint at step {step}", flush=True)
        # save_checkpoint(step)
        break
```

Try it locally: start it, then run `kill -TERM <pid>` from another
terminal. `SIGTERM` goes to the container's main process only, so if it
starts training in a child process, it must pass the signal on.
`checkpoint_plugin.py` does the same inside the Hugging Face Trainer.

**Outside the job.** The job ends `FAILED` with code `Preempted`:

```bash
$ nebius ai job get <job-id> --format jsonpath='{.status.state} {.status.state_details.code}'
FAILED Preempted
```

A new job can also fail to start at all, when no spot VM is free. It then
ends `ERROR` with code `NotEnoughResources`.

Either way, to finish the training you must create a new job. So a
training job on spot GPUs needs three things:

1. **Save progress outside the VM.** Copy every checkpoint to an Object
   Storage bucket as soon as it is written.
2. **Resume on start.** A new job copies the latest checkpoint back and
   continues from it.
3. **Something that does not get preempted starts the new job.** A retry
   loop that waits for the job, and starts the next attempt when the last
   one ended `Preempted` or `NotEnoughResources`.

## Using spot jobs effectively

Points 1 and 2 are in the GPU job itself, the same for every way of
running it:

| File | Does |
|---|---|
| `src/axolotl/config.yaml` | Axolotl config: a checkpoint every 200 steps, resume from `output_dir` on start |
| `src/axolotl/checkpoint_plugin.py` | Copies each checkpoint to the bucket, then marks it complete; on `SIGTERM` saves one more |
| `src/axolotl/resumable_axolotl.py` | Copies the latest complete checkpoint from the bucket, runs `axolotl train`, saves the adapter |

All attempts of one run share a checkpoint folder in the bucket,
`spot-axolotl/<run-name>/`. That is how attempt 2 finds what attempt 1
saved.

Point 3, the retry loop, can be a supervisor job or a Prefect flow. Both
run on a regular (non-preemptible) CPU job, so they outlive any number of
preemptions, and your machine can be switched off. Both need a service
account that can create jobs; see
[Create a service account for CPU jobs](README.md#create-a-service-account-for-cpu-jobs).

Neither counts attempts. They keep starting new ones for up to
`--max-hours` (12 by default), 2 minutes apart.

### Supervisor job

`run_supervisor.py` is a plain Python loop with no other dependencies:

```text
your machine                 supervisor (CPU, on-demand)          GPU (spot)
─────────────                ───────────────────────────          ──────────
run_supervisor.py  ──create──▶ run_supervisor.py --supervise
                               loop:
                                 create attempt N  ─────────────▶ train, save checkpoints
                                 wait until it ends ◀───────────── Preempted
                                 wait 2 min, N += 1
                                 ...                ◀───────────── COMPLETED
                               exit
```

```bash
uv run run_supervisor.py --bucket-id "$BUCKET_ID" \
  --credentials ~/.nebius/spot-flow-credentials.json
```

Follow it with `nebius ai job logs <supervisor-job-id> --follow`:

```text
attempt 1: created aijob-...
aijob-... RUNNING
aijob-... FAILED
aijob-... ended Preempted, retrying in 120 s
attempt 2: created aijob-...
aijob-... COMPLETED
completed aijob-.... Adapter: spot-axolotl/<run-name>/final/
```

Use it when the fine-tune is the whole job and the logs are enough.

### Part of a Prefect pipeline

When the fine-tune is one step of a larger pipeline, run it as a Prefect
task. `src/prefect/flow.py` does this: the `fine_tune` task creates a GPU
job and waits for it, and Prefect retries the task when the job ended
`Preempted` or `NotEnoughResources`. Any other failure fails the flow.

Prefect adds what the supervisor's logs lack:

- every attempt, its state and its retries in the Prefect UI;
- a link artifact per attempt, `attempt-1`, `attempt-2`, ..., to the GPU
  job in the Nebius console;
- a place for the steps before and after the fine-tune.

#### Optional: run a Prefect server on a Nebius endpoint

Prefect works without a server: it then starts a temporary one for each
run, and the UI and history are gone when the run ends. To keep them,
run a Prefect server as an endpoint.

Choose a login for the server, `user:password`, and keep it in
`~/.prefect/token`. The flow reads it from there too:

```bash
echo "<user>:<password>" > ~/.prefect/token
chmod 600 ~/.prefect/token
```

Create the endpoint with that login:

```bash
nebius ai endpoint create \
  --name prefect-server \
  --image prefecthq/prefect:3.9.4-python3.12 \
  --container-command prefect \
  --args "server start --host 0.0.0.0 --port 4200" \
  --container-port 4200 \
  --platform cpu-d3 --preset 2vcpu-8gb --on-demand \
  --disk-size 50Gi \
  --env PREFECT_UI_API_URL=/api \
  --env PREFECT_SERVER_API_AUTH_STRING="$(cat ~/.prefect/token)"
```

`PREFECT_UI_API_URL=/api` lets the UI reach the API through the
endpoint's URL, whatever it turns out to be. Get the URL:

```bash
nebius ai endpoint get-by-name --name prefect-server \
  --format jsonpath='{.status.public_endpoints[0]}'
```

Open it in a browser for the UI. Its API is the same URL plus `/api`.

The server keeps its history in a SQLite file on the endpoint's disk.

#### How to run

Start the flow on a CPU job. It logs in to the server with
`~/.prefect/token`:

```bash
uv run prefect_pipeline.py --bucket-id "$BUCKET_ID" \
  --credentials ~/.nebius/spot-flow-credentials.json \
  --prefect-api-url "https://<prefect-endpoint-url>/api"
```

The flow run appears in the Prefect UI under the run name, e.g.
`20261123-092518z-qwen05b-qlora`.

To see a retry without waiting for a real preemption, stop the VM under
attempt 1 once it has saved a checkpoint:

```bash
uv run simulate_job_preemption.py <gpu-job-id>
```

## Outcome

We ran the Prefect flow and stopped attempt 1's VM with
`simulate_job_preemption.py`:

| Time (UTC) | Event |
|---|---|
| 09:28 | Attempt 1 created |
| 09:32 | Attempt 1 running: `no checkpoint in the bucket, starting fresh` |
| 09:33 | Checkpoint 200 in the bucket; VM stopped |
| 09:34 | Attempt 1 ends `FAILED Preempted`; Prefect: `Retry 1/360 will start 120 second(s) from now`. The container keeps training until it is killed and saves checkpoints 400 to 800. |
| 09:36 | Attempt 2 created |
| 09:40 | Attempt 2 running: `resuming from checkpoint-800` |
| 09:47 | Training done at step 3000; adapter in `spot-axolotl/<run-name>/final/`; flow `Completed` |

What it shows:

- **No training was lost.** Attempt 2 continued from the last checkpoint
  attempt 1 saved.
- **A preemption costs about 6 minutes:** 2 minutes of retry delay, and
  about 4 for the new VM to start and pull the image. On top of that, it
  can lose up to one checkpoint interval of training. Spot pays off when
  its discount outweighs both.
- **Do not rely on the last-minute checkpoint alone.** In this run the
  checkpoint on `SIGTERM` did not happen; the regular checkpoints every
  200 steps did the work. Keep checkpointing regularly.
