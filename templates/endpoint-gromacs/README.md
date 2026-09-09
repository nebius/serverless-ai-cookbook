# GROMACS REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fgromacs-md-api%3A20260908-6bd2a84-dynamic&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true&amp;env=NGC_API_KEY&amp;env=GROMACS_VERSION%3Dlatest&amp;env=GROMACS_CPU_BUILD%3Davx2_256&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run bounded GROMACS molecular-dynamics workloads on an NVIDIA GPU through REST or MCP. A lean API image pulls the selected official NVIDIA GROMACS runtime at endpoint startup, and persists artifacts to Object Storage or Shared Filesystem.

**License:** [LGPL-2.1](https://gitlab.com/gromacs/gromacs/-/blob/main/COPYING) · **Runtime:** [`nvcr.io/nvidia/gromacs`](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/gromacs)

<!-- /factory:intro -->

---

title: GROMACS REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-l40s-a
frameworks: [gromacs, fastapi, mcp]
keywords: [molecular-dynamics, simulation, nvidia-ngc, rest, mcp, agent]
difficulty: intermediate

---

## What you get

- A bounded asynchronous run API on port 8000 with OpenAPI docs at `/docs`.
- A Streamable HTTP MCP server at `/mcp` for agent/tool integrations.
- One shared queue, run ID, state, and artifact store across REST and MCP.
- Runtime selection with `GROMACS_VERSION`: use `latest` or an explicit official
  NVIDIA tag without rebuilding this API image.
- GPU readiness gated by a real one-step `grompp` + `mdrun -nb gpu` probe.
- Persistent results under `/mnt/hcls/gromacs-md/runs/<run-id>`.

The wrapper image contains the API and pull launcher, not GROMACS. On every fresh
endpoint boot it authenticates to NGC with `NGC_API_KEY`, resolves the requested
tag, pulls `nvcr.io/nvidia/gromacs`, and starts only after that runtime passes the
GPU probe. Restarting an endpoint configured with `latest` lets it adopt a newer
compatible NVIDIA release without publishing a new wrapper image.

The pre-built wrapper tag in the button resolves to
`sha256:a0b690e75c3859e65f5299ae97f12f977136d5e6e05058f6355081f5bbfa0671`.

## Create the endpoint

Click **Create Endpoint** above, select your project, and review the pre-filled
form. Before you create it:

1. In **Environment variables**, paste your NVIDIA NGC API key into
   `NGC_API_KEY`. No NGC username or password is needed; the launcher supplies
   NGC's fixed `$oauthtoken` username internally.
2. Leave `GROMACS_VERSION=latest` to select the newest stable tag that passes the
   GPU probe, or replace `latest` with an older NVIDIA tag such as `v2025.1`.
3. Keep `GROMACS_CPU_BUILD=avx2_256` unless you have verified another build on the
   selected worker CPU.
4. Keep **Token authentication** enabled and generate/copy the endpoint token.
   This token protects both REST and MCP. It is not an environment variable and
   is never placed in the deployment URL.
5. In the pre-opened volume row, attach either **Object Storage** or **Shared
   Filesystem** read-write at `/mnt/hcls`.

The link intentionally contains the empty `NGC_API_KEY` field and every safe
default, but no credential value. The attached storage resource is also selected
in the customer's project rather than hard-coded in a public URL.

### Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `NGC_API_KEY` | yes | empty | Pulls the official NVIDIA runtime from NGC. |
| `GROMACS_VERSION` | no | `latest` | NVIDIA image tag, or newest stable GPU-compatible tag. |
| `GROMACS_CPU_BUILD` | no | `avx2_256` | GROMACS CPU dispatch build inside the NVIDIA image. |

`latest` is a selection policy rather than Docker's mutable `:latest` tag: stable
version tags are tried newest-first, and incompatible GPU/CUDA builds are rejected.
An explicitly pinned tag is never silently replaced with another version.

## Storage: choose either lane

Both supported Serverless storage types use the same application mount path:

- **Object Storage:** choose a bucket and its access credentials in the volume
  controls, then mount it read-write at `/mnt/hcls`.
- **Shared Filesystem:** choose a filesystem in the project and mount it
  read-write at `/mnt/hcls`.

GROMACS runs on endpoint-local scratch disk, then copies input files, output files,
logs, hashes, `result.json`, and ordered status snapshots to the mounted resource.
Object Storage access belongs to the Serverless volume configuration; the S3 key is
not an application environment variable and is not exposed to REST or MCP.

Serverless currently presents both managed volume types as root-owned mounts and
does not expose a mount UID/GID setting. The bounded API process therefore runs as
root so it can write either storage type. It does not expose a shell or accept
arbitrary command-line arguments.

If no persistent resource is attached, `/mnt/hcls` falls back to endpoint-local
storage and its contents can disappear when the worker is replaced.

## Test through REST and MCP

Wait for the managed endpoint URL to appear, then set the two client-side values:

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.<region>.nebius.cloud'
export TOKEN='<endpoint-token-generated-during-create>'
```

The public gateway should reject an unauthenticated request and accept the same
request with the token:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE_URL/v1/health/ready"
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/v1/health/ready" \
  | python3 -m json.tool
```

First boot can take several minutes because the wrapper downloads and probes the
official NVIDIA image. Nebius can show the endpoint as running before the API binds
port 8000; poll until readiness returns JSON:

```bash
until curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/v1/health/ready" >/dev/null; do echo 'waiting for GROMACS…'; sleep 15; done
```

Submit the guided argon GPU smoke through REST:

```bash
RUN_ID="$({
  curl -sS -X POST "$BASE_URL/v1/runs" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{
      "input": {"steps": 10000, "gpu_mode": "gpu", "threads": 1},
      "client_request_id": "gromacs-first-run",
      "research_use_acknowledgement": true
    }'
} | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

while :; do
  STATUS="$(curl -sS -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/v1/runs/$RUN_ID" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  echo "$STATUS"
  case "$STATUS" in succeeded|failed|cancelled) break;; esac
  sleep 2
done
```

For one end-to-end check of both protocols, use the included client. It submits a
real GPU run through REST, another through MCP, downloads and hashes each result,
and confirms the MCP run is visible through REST with the same token:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-client.txt
export HCLS_ENDPOINT_TOKEN="$TOKEN"
.venv/bin/python scripts/test_endpoint.py "$BASE_URL"
```

An MCP-capable agent uses:

```text
URL: https://<managed-endpoint-host>/mcp
Authorization: Bearer <the same endpoint token used by REST>
Transport: Streamable HTTP
```

Available tools are `get_capabilities`, `submit_run`, `get_run`, `list_runs`,
`cancel_run`, and `list_run_artifacts`.

For an agent that supports the portable Agent Skills format, install the included
[`gromacs-serverless` skill](./skills/gromacs-serverless/SKILL.md). The skill
teaches the agent how to select an input mode, submit idempotently, monitor runs,
verify artifacts, and interpret GROMACS output without treating a smoke test as a
scientifically validated workflow. Configure the MCP URL and bearer token in the
agent or MCP client; never copy credentials into the skill file.

## Expected output

A successful run reaches `status: succeeded`, reports `gpu_selected: true`, and
includes the resolved NVIDIA tag/digest, actual GROMACS version, wall-clock time,
and `ns_per_day`. Its artifact list includes the TPR, coordinates, energy,
checkpoint, GROMACS log, command logs, and `result.json`, each with a SHA-256 hash.

Validation on 2026-09-09 used a regular L40S. `latest` selected official NVIDIA
tag `v2025.1` at digest
`sha256:d045e411eb3197ab2474b9b6376bc7abf58ca38a978e5f6582498acb32b17316`;
1,000-step REST and MCP runs both succeeded with GPU offload, and both result
artifacts were downloaded and hash-verified. The same wrapper has passed
replacement-worker persistence checks with both Object Storage and Shared
Filesystem mounted at `/mnt/hcls`.

The default argon system is a deployment smoke test, not a scientifically validated
simulation protocol. For research inputs, submit either a prepared TPR as bounded
base64 or provide `.gro`, topology, and `.mdp` text together, and independently
validate the force field, ensemble, equilibration, constraints, and sampling.

## Build the wrapper image

This directory is self-contained. From a checkout of the cookbook:

```bash
cd templates/endpoint-gromacs
docker build --platform linux/amd64 \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t <your-registry>/gromacs-rest-mcp:1 .
docker push <your-registry>/gromacs-rest-mcp:1
```

To exercise a local CUDA host, mount a local output directory and provide your NGC
key at runtime:

```bash
mkdir -p ./local-output
docker run --rm --gpus all -p 8000:8000 \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e GROMACS_VERSION=latest \
  -v "$PWD/local-output:/mnt/hcls" \
  <your-registry>/gromacs-rest-mcp:1
```

<!-- factory:cli -->

## CLI alternative

Choose one volume value before creating the endpoint:

```bash
# Shared Filesystem
export GROMACS_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'

# Or Object Storage. Configure the local AWS profile for the bucket region and
# endpoint; the selected MysteryBox version contains S3_ACCESS_KEY_ID and
# S3_SECRET_ACCESS_KEY for the Serverless mount.
export GROMACS_VOLUME='s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>'
```

Then create the same service from the CLI:

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export NGC_API_KEY='<your-ngc-api-key>'

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name gromacs-rest-mcp \
  --image cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/gromacs-md-api:20260908-6bd2a84-dynamic \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --container-port 8000 \
  --disk-size 100Gi \
  --shm-size 16Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --env "NGC_API_KEY=$NGC_API_KEY" \
  --env 'GROMACS_VERSION=latest' \
  --env 'GROMACS_CPU_BUILD=avx2_256' \
  --volume "$GROMACS_VOLUME"
```

With `--auth token` and no explicit token, the CLI generates one and displays it
once. Copy it immediately; it cannot be recovered later.

<!-- /factory:cli -->

## Cost and cleanup

The one-click link selects regular L40S capacity because this is a long-running API
and a replacement worker must pull the runtime again. Switch to preemptible for a
short disposable test if interruptions are acceptable. The endpoint accrues GPU,
boot-disk, and attached-storage charges while provisioned; stop or delete it when
testing is complete.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| NGC returns 401/403 | Paste a valid NGC API key into `NGC_API_KEY`; do not enter a username or the endpoint token. |
| `no stable NVIDIA GROMACS tag passed` | The newest tags are incompatible with the current GPU driver. Use `latest` for automatic fallback, or pin a known-compatible tag. |
| Endpoint is running but returns 502 | The NVIDIA image is still downloading/probing and port 8000 is not bound yet. Follow endpoint logs and keep polling readiness. |
| Readiness reports no NVIDIA device | Verify the platform/preset is GPU-backed and that the worker obtained capacity. |
| Outputs disappear after restart | Attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`; an unmounted path is ephemeral. |
| REST works but MCP returns 401 | Send the same `Authorization: Bearer <endpoint-token>` header to `/mcp`. |
| A pinned tag fails immediately | Explicit tags do not fall back. Select `latest` or another official tag compatible with the current Serverless driver. |
