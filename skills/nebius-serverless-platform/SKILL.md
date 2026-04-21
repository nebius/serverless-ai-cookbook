---
name: nebius-serverless-platform
description: Cross-cutting infrastructure for Nebius Serverless AI — authentication (profiles, service accounts for CI), project/subnet discovery, MysteryBox secrets (env, token, registry), volume mounts (bucket, filesystem, external S3), async operations, and `--dry-run` validation. Use when the user asks to set up non-interactive auth, configure a service account for CI, store secrets for jobs/endpoints, mount a bucket or filesystem into a container, look up a subnet ID, track a long-running create/delete operation, or validate a job/endpoint spec without spending GPU time.
allowed-tools: Bash(nebius *)
---

# Nebius Serverless AI — Platform primitives

The cross-cutting concerns that every non-trivial job or endpoint touches: auth, secrets, storage mounts, project/subnet lookup, async ops. Read this skill alongside `nebius-serverless-job` / `nebius-serverless-endpoint`.

## Authentication

### Interactive (laptop)

```bash
nebius profile create    # OAuth via browser; writes ~/.nebius/config.yaml
nebius profile list
nebius profile activate <name>
```

Each profile bakes in `parent-id` (the project), `endpoint`, and credential refs. Switch with `nebius --profile <name> ...` or `nebius profile activate`.

### Non-interactive (CI)

The CLI signs requests itself — **you do not normally call `nebius iam get-access-token`** (that returns a raw Bearer token for custom HTTP clients).

One-time setup (on a workstation):

```bash
# 1. Create a service account in the project.
SA_ID=$(nebius iam service-account create --name ci-runner \
  --parent-id $PROJECT_ID --format jsonpath='{.metadata.id}')

# 2. Generate a signing keypair locally.
openssl genpkey -algorithm RSA -out sa.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -in sa.pem -pubout -out sa.pub

# 3. Register the public key with the service account.
PUBKEY_ID=$(nebius iam auth-public-key create \
  --parent-id $SA_ID --data "$(cat sa.pub)" --format jsonpath='{.metadata.id}')

# 4. Grant it the roles the CI pipeline needs (e.g. editor on the project).
nebius iam role-binding create --parent-id $PROJECT_ID \
  --subject-id $SA_ID --role roles/editor
```

Keep `sa.pem` and `PUBKEY_ID` as CI secrets. In the CI runner:

```bash
echo "$NEBIUS_SA_KEY" > /tmp/key.pem
chmod 600 /tmp/key.pem
nebius profile create --name ci \
  --service-account-id "$SA_ID" \
  --private-key-file /tmp/key.pem \
  --public-key-id "$PUBKEY_ID" \
  --parent-id "$PROJECT_ID"
# Every subsequent `nebius ...` call in this shell uses the CI profile.
```

### Project / parent-id resolution order

1. Explicit `--parent-id` on the command (wins).
2. `parent-id` from the active profile in `~/.nebius/config.yaml`.

There is no `NEBIUS_PROJECT_ID` env var read at call time. Quickstarts sometimes export `NB_PROJECT_ID` before `profile create` for convenience — it's a shell var, not a CLI-read env.

## Project / subnet / registry discovery

```bash
# Current project ID from active profile
nebius iam whoami --format jsonpath='{.parent-id}'

# Subnets in a project (pick the default or a specific name)
nebius vpc subnet list --parent-id $PROJECT_ID
nebius vpc subnet get-by-name --name default-subnet --format jsonpath='{.metadata.id}'

# Container registries in a project (use the SHORT id in image URLs — strip `registry-`)
nebius registry v1alpha1 registry list --parent-id $PROJECT_ID
```

## Secrets — MysteryBox

All secrets for Serverless AI live in **MysteryBox**. There is no `nebius vault`.

A **secret** is a container. Each **secret-version** carries a JSON payload of `{key, string_value}` entries.

```bash
# Create a secret container.
SECRET_ID=$(nebius mysterybox secret create --name hf-token \
  --parent-id $PROJECT_ID --format jsonpath='{.metadata.id}')

# Create a version with the actual payload.
VER_ID=$(nebius mysterybox secret-version create \
  --parent-id "$SECRET_ID" \
  --payload-json '[{"key":"HUGGING_FACE_HUB_TOKEN","string_value":"hf_xxx"}]' \
  --format jsonpath='{.metadata.id}')
```

Reference `$VER_ID` from jobs/endpoints:

| Flag | Payload key requirement |
|---|---|
| `--env-secret NAME=<ver-id>` | Payload key must equal `NAME` |
| `--token-secret <ver-id>` (endpoints) | Payload must contain `AUTH_TOKEN` |
| `--registry-secret <ver-id>` | Payload must contain `REGISTRY_USERNAME` and `REGISTRY_PASSWORD` |

### Example: private image pull via MysteryBox

```bash
nebius mysterybox secret-version create --parent-id $REG_SECRET_ID \
  --payload-json '[
    {"key":"REGISTRY_USERNAME","string_value":"my-user"},
    {"key":"REGISTRY_PASSWORD","string_value":"my-pass"}
  ]'
# Then on the job:
nebius ai job create ... --registry-secret $VER_ID ...
```

Docs: https://docs.nebius.com/cli/reference/mysterybox/

## Volumes — what can be mounted

`--volume` accepts three source types:

| Source | Syntax | Performance | Use case |
|---|---|---|---|
| Nebius bucket | `<bucket-name-or-id>:/container/path[:ro\|rw]` | FUSE-style, good for read-mostly | Models, datasets, artifacts output |
| Nebius filesystem | `<fs-id>:/container/path[:ro\|rw]` | POSIX semantics, best random I/O | Checkpoint-heavy training, shared scratch |
| External S3 | `s3://bucket:/container/path[:ro\|rw]` + auth | FUSE | When weights live in your own AWS account |

For checkpoint-write-heavy workloads, **prefer a filesystem mount** (bucket mounts struggle with small random writes).

External S3 auth goes via `S3Config` in the proto — in the CLI this maps to a MysteryBox secret ref alongside the `s3://` URL. See the proto:
https://github.com/nebius/api/blob/main/nebius/ai/v1/job.proto

### `--shm-size` (not a volume but related)

`/dev/shm` default is `16Gi` on GPU presets, `0` on CPU. **PyTorch DataLoader with `num_workers>0` needs shared memory** — bump this on CPU presets:

```bash
--shm-size 8Gi
```

## Disk sizing

`--disk-size` default `250Gi`, format `100Gi|1Ti`. Image layers count toward this. Rule of thumb: leave at least 2× your largest single file (checkpoint or dataset shard) free after image size.

Max is governed by Compute quotas (typically 4Ti+). Bigger disks get higher IOPS.

## Async operations

Every mutating call (`create`, `delete`, `cancel`, `start`, `stop`) returns an `Operation`. By default the CLI blocks client-side. For parallelism, use `--async`:

```bash
OP=$(nebius ai job create ... --async --format jsonpath='{.metadata.id}')
nebius ai job operation wait "$OP"                     # block until done
nebius ai job operation get  "$OP"                     # one-shot status
nebius ai job operation list --resource-id <job-id>    # all ops for a resource
```

Same three subcommands exist under `nebius ai endpoint operation`.

## Dry-run

Both `CreateJobRequest` and `CreateEndpointRequest` support `--dry-run`: the server validates the spec without provisioning anything. Use it in CI to catch bad specs without spending GPU minutes:

```bash
nebius ai job create --dry-run ... && echo "spec OK"
```

## Pricing / quotas

Serverless AI has **no dedicated price sheet** — rates inherit from Compute.

- VM / GPU pricing (incl. preemptible discount tier): https://docs.nebius.com/compute/resources/pricing
- GPU / vCPU / disk quotas: https://docs.nebius.com/compute/resources/quotas-limits
- Public IP quotas: https://docs.nebius.com/vpc/resources/quotas-limits
- Object storage: https://docs.nebius.com/object-storage/resources/pricing
- Serverless-specific notes: https://docs.nebius.com/serverless/pricing-quotas

## Reference

- CLI IAM index: https://docs.nebius.com/cli/reference/iam/
- Service accounts: https://docs.nebius.com/cli/reference/iam/service-account/
- Auth public keys: https://docs.nebius.com/cli/reference/iam/auth-public-key/
- VPC subnets: https://docs.nebius.com/cli/reference/vpc/subnet/
- MysteryBox: https://docs.nebius.com/cli/reference/mysterybox/
- Proto (jobs + volumes): https://github.com/nebius/api/blob/main/nebius/ai/v1/job.proto
