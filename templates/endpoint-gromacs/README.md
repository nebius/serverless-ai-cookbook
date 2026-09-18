---
title: GROMACS REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-l40s-a
frameworks: [gromacs, fastapi, mcp]
keywords: [molecular-dynamics, simulation, cuda, rest, mcp, agent]
difficulty: intermediate
---

# GROMACS REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb21%40sha256%3Ac291e308591382e2114e7a43146b4e4af4e4c47326397f935059c5094d4932ba&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run bounded GROMACS molecular-dynamics workloads on an NVIDIA GPU through REST or MCP. The self-contained image compiles GROMACS 2025.3 with CUDA at build time. Attach Object Storage or Shared Filesystem for persistent artifacts.

**License:** [LGPL-2.1-or-later](https://gitlab.com/gromacs/gromacs/-/blob/v2025.3/COPYING) for GROMACS; Apache-2.0 for the wrapper; FFTW is GPL-2.0-or-later.

<!-- /factory:intro -->


## What you get

- A bounded asynchronous run API on port 8000 with OpenAPI docs at `/docs`.
- A Streamable HTTP MCP server at `/mcp` for agent/tool integrations.
- One shared queue, run ID, state, and artifact store across REST and MCP.
- GROMACS 2025.3 compiled with CUDA support at image build time.
- GPU readiness gated by a real one-step `grompp` + `mdrun -nb gpu` probe.
- Results under `/mnt/hcls/gromacs-md/runs/<run-id>`; persistent only with an attached volume.

The image compiles GROMACS 2025.3 from its checksum-verified source release
on a digest-pinned CUDA base. It includes the engine and corresponding source.
No NGC account, runtime image pull, or boot-time package installation is needed.
Change versions by rebuilding and validating a new image.

## Create the endpoint

The button does not attach storage. Manually attach Object Storage or Shared
Filesystem read-write at `/mnt/hcls` in the create form for persistent results.
Without that attachment, `/mnt/hcls` is on ephemeral disk and results can be lost
when the endpoint is replaced or deleted.

Click **Create Endpoint** above, select your project, and review the pre-filled
form. Before you create it:

1. Keep **Token authentication** enabled and copy the endpoint token. It protects
   both REST and MCP and is not an application environment variable.
2. Manually attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`.

There are no required application environment variables or image-pull secrets.

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

Startup probes the installed CUDA engine. Poll until readiness returns JSON:

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
includes the installed GROMACS version, wall-clock time,
and `ns_per_day`. Its artifact list includes the TPR, coordinates, energy,
checkpoint, GROMACS log, command logs, and `result.json`, each with a SHA-256 hash.

See [validation results](./VALIDATION.md) for the tested image and workloads.

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

To exercise a local CUDA host, mount a local output directory:

```bash
mkdir -p ./local-output
docker run --rm --gpus all -p 8000:8000 \
  -v "$PWD/local-output:/mnt/hcls" \
  <your-registry>/gromacs-rest-mcp:1
```

<!-- factory:cli -->

## CLI alternative

The tested image is `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb21@sha256:c291e308591382e2114e7a43146b4e4af4e4c47326397f935059c5094d4932ba`.
The qualification used Nebius CLI 0.12.206, which rejects endpoint image references
longer than 64 characters when creating a VM label. For that CLI, use the short
alias below and verify its digest with [crane](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
before creating the endpoint. Do not use an alias whose digest differs.

```bash
export IMAGE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb21:r0918'
test "$(crane digest "$IMAGE")" = 'sha256:c291e308591382e2114e7a43146b4e4af4e4c47326397f935059c5094d4932ba' || exit 1
```

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

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name gromacs-rest-mcp \
  --image "$IMAGE" \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --container-port 8000 \
  --disk-size 100Gi \
  --shm-size 16Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --volume "$GROMACS_VOLUME"
```

With `--auth token` and no explicit token, the CLI generates one and displays it
once. Copy it immediately; it cannot be recovered later.

<!-- /factory:cli -->

## Cost and cleanup

The one-click link selects regular L40S for an interactive API. Switch to
preemptible for a short disposable test if interruptions are acceptable. The endpoint accrues GPU,
boot-disk, and attached-storage charges while provisioned; stop or delete it when
testing is complete.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Endpoint is running but returns 502 | Image startup or the CUDA probe is still in progress. Follow endpoint logs and keep polling readiness. |
| Readiness reports no NVIDIA device | Verify the platform/preset is GPU-backed and that the worker obtained capacity. |
| Outputs disappear after restart | Attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`; an unmounted path is ephemeral. |
| REST works but MCP returns 401 | Send the same `Authorization: Bearer <endpoint-token>` header to `/mcp`. |
