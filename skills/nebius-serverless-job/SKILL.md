---
name: nebius-serverless-job
description: Submit, monitor, fetch logs for, cancel, SSH into, and debug jobs on Nebius Serverless AI via the `nebius ai job` CLI. Covers basic submission plus advanced scenarios (preemptible, restart policies, async operations, dry-run, post-mortem debug). Use when the user asks to run, launch, submit, smoke-test, monitor, debug, SSH into, cancel, or delete a Nebius AI job, or when they report empty/missing job logs, a stuck QUEUED job, a preempted training run, or an image that fails to pull.
allowed-tools: Bash(nebius *)
---

# Nebius Serverless AI — Jobs

A **job** is a non-interactive container run on a GPU or CPU VM that terminates on completion, failure, cancel, or `--timeout`. Billed per-second. Each job maps to exactly one VM — for multi-node training use Soperator/Managed Slurm, not Serverless AI. Docs: https://docs.nebius.com/serverless/jobs

Companion skills:
- `nebius-serverless-endpoint` — long-running services with an IP.
- `nebius-container-registry` — building and pushing images.
- `nebius-serverless-platform` — auth, secrets, volumes, subnets, async ops.
- `nebius-serverless-recipes` — end-to-end playbooks.

## Lifecycle

```
create → QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED
```

Resources (VM + disk) are released automatically at terminal state. `delete` only removes the record from listings (and its retained logs).

## Submitting a job

Minimum viable command:

```bash
nebius ai job create \
  --name my-job-$(date +%Y%m%d%H%M%S) \
  --image cr.eu-north1.nebius.cloud/<registry-short-id>/<image>:<tag> \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --subnet-id vpcsubnet-<id> \
  --timeout 30m \
  --args '--protein-id,1UBQ,--steps,100'
```

### Flag reference

Full reference: https://docs.nebius.com/cli/reference/ai/job/create

| Flag | Purpose | Notes |
|---|---|---|
| `--name` | Unique job name | Include a timestamp so reruns don't collide |
| `--image` | Container image URL | Full registry path (see `nebius-container-registry` skill) |
| `--platform` | VM family | `gpu-l40s-a`, `gpu-l40s-d`, `gpu-h100-sxm`, `gpu-h200-sxm`, CPU variants |
| `--preset` | Resource preset | `1gpu-8vcpu-32gb`, `8gpu-128vcpu-1600gb`, ... |
| `--subnet-id` | VPC subnet | **Required when the project has more than one subnet.** |
| `--timeout` | Max runtime, hard kill | `30m`, `4h`, max `168h`. Default 24h. SIGTERM then SIGKILL after a short grace. |
| `--container-command` | Override image `ENTRYPOINT` | Does not touch `CMD` |
| `--args` | Override image `CMD` | Comma-separated |
| `--working-dir` | Override WORKDIR | — |
| `--env KEY=VAL` | Plain env var | Repeatable |
| `--env-secret NAME=<secret-version-id>` | Secret-backed env var | MysteryBox. Payload key must equal `NAME`. |
| `--volume` | Mount bucket/filesystem/S3 | See platform skill |
| `--disk-size` | Root disk | Default `250Gi`. Format: `100Gi`, `1Ti`. |
| `--shm-size` | `/dev/shm` size | Default `16Gi` on GPU, `0` on CPU. **Bump explicitly for CPU presets if your framework needs shm (PyTorch DataLoader with `num_workers>0`).** |
| `--preemptible` | Cheaper, can be stopped any time | Combine with `--restart-policy on-failure` |
| `--restart-policy {never|on-failure}` | Relaunch on non-zero exit / preemption | — |
| `--restart-attempts <N>` | Cap retries, `-1` = unlimited | Pairs with `--restart-policy on-failure` |
| `--ssh-key` | Authorize SSH keys | Required at create time to use `job ssh` later |
| `--registry-username` / `--registry-password` | Inline registry creds | — |
| `--registry-secret <secret-version-id>` | MysteryBox-backed registry creds | Payload must contain `REGISTRY_USERNAME` + `REGISTRY_PASSWORD` |
| `--dry-run` | Validate spec server-side without spending | **Use in CI** to catch bad specs cheaply |
| `--async` | Don't block on the operation; return op ID | Pair with `nebius ai job operation wait` |

Multi-GPU single-node: use a multi-GPU preset (e.g. `8gpu-128vcpu-1600gb`) and `--container-command torchrun --args "--standalone,--nproc_per_node=8,<your_entry.py>"`.

## Monitoring state

One-shot:

```bash
nebius ai job get <aijob-id>
```

Poll until terminal state:

```bash
until nebius ai job get <aijob-id> 2>/dev/null \
  | awk '/^  State:/ {print $2}' \
  | grep -qE 'COMPLETED|FAILED|CANCELLED'; do
  sleep 30
done
```

List jobs in a project:

```bash
nebius ai job list --parent-id <project-id>
```

`nebius ai get <id>` and `nebius ai list` (without `job`/`endpoint`) also work for scripts that don't know the resource type.

## Fetching logs — read this before debugging "empty logs"

**`nebius ai job logs` defaults `--since` to 1 hour.** A job that finished more than an hour ago produces zero output unless you widen the window. This is the #1 cause of "logs command returned nothing".

Historical logs for a completed job:

```bash
nebius ai job logs <aijob-id> --since 24h
```

Live stream while running:

```bash
nebius ai job logs <aijob-id> --follow
```

`--follow` and `--since` are orthogonal. For a completed job, **always pass `--since`**.

Other flags: `--until <time>`, `--tail <n>`, `--timestamps`. Reference: https://docs.nebius.com/cli/reference/ai/job/logs

### Logs in shell scripts

`--follow` on a completed job can hang:

```bash
# Preferred: no --follow, wide --since
nebius ai job logs <aijob-id> --since 24h > logs.txt 2>&1
```

```bash
# If you must follow, wrap in a timeout
timeout 30 nebius ai job logs <aijob-id> --follow --since 24h > logs.txt 2>&1 || true
```

**Log retention window is not documented** — logs disappear some time after the resource is deleted. For long training runs, stream `--follow` output into durable storage (a mounted bucket or your own log collector).

## Cancel / delete

```bash
nebius ai job cancel <aijob-id>   # stops a RUNNING job (no-op if already terminal)
nebius ai job delete <aijob-id>   # removes a terminal job from listings
```

`cancel` keeps the final status and any retained logs queryable; `delete` removes them.

## SSH into a running job

```bash
nebius ai job ssh <aijob-id>
# or with explicit key / shell:
nebius ai job ssh <aijob-id> --identity-file ~/.ssh/id_ed25519 --shell bash
```

**Requires `--ssh-key` at `create` time** and **only works while state is `RUNNING`**. The VM is destroyed on terminal state, so post-mortem SSH is impossible.

### Post-mortem SSH trick

Append `|| sleep 3600` to your entrypoint args so the container lingers after a crash:

```bash
nebius ai job create --name debug-... \
  --container-command bash \
  --args "-c,python train.py || sleep 3600" \
  --ssh-key ~/.ssh/id_ed25519.pub \
  ...
```

Then `nebius ai job ssh <id>` while it's still in the sleep window. Remember to `cancel` when done to stop billing.

## Async operations

Every mutating call (`create`, `cancel`, `delete`) returns a `common.v1.Operation`. By default the CLI blocks client-side. For parallel submission, use `--async`:

```bash
OP=$(nebius ai job create ... --async --format jsonpath='{.metadata.id}')
nebius ai job operation wait "$OP"
```

Other ops commands: `nebius ai job operation get <op-id>`, `nebius ai job operation list --resource-id <job-id>`.

## Common failure modes & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `logs` returns nothing | Job finished > 1h ago, `--since` default too narrow | `--since 24h` |
| `Error: multiple subnets found` | Project has > 1 subnet | Pass `--subnet-id` |
| Stuck in `QUEUED` | No capacity for that platform/preset in region | Try another preset, region, or `--preemptible` |
| Image pull fails at start | Arch mismatch (built arm64) or registry auth | Rebuild `--platform linux/amd64`; pass `--registry-username/--registry-password` or `--registry-secret` (see `nebius-container-registry`) |
| `FAILED` with preemption details | Spot VM reclaimed | Add `--restart-policy on-failure --restart-attempts -1` + checkpoint frequently |
| PyTorch DataLoader shm errors on CPU preset | `--shm-size` default is 0 on CPU | `--shm-size 8Gi` |
| `Error: rpc error ... operation timed out` on submit | Network to `api.*.nebius.cloud` flapping | Retry; not a spec issue |
| Can't SSH a crashed job | Terminal state destroys the VM | Use the `|| sleep 3600` trick above |
| Timeout fires mid-training | Default 24h too short | `--timeout 72h` (max 168h) + frequent checkpoints |

## Reference

- Overview: https://docs.nebius.com/serverless/overview
- Jobs guide: https://docs.nebius.com/serverless/jobs
- Quickstart: https://docs.nebius.com/serverless/quickstart
- CLI index: https://docs.nebius.com/cli/reference/ai/
- `job create`: https://docs.nebius.com/cli/reference/ai/job/create
- `job logs`: https://docs.nebius.com/cli/reference/ai/job/logs
- `job ssh`: https://docs.nebius.com/cli/reference/ai/job/ssh
- Proto: https://github.com/nebius/api/tree/main/nebius/ai/v1
