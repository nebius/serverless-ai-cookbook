---
title: OpenMM REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-l40s-a
frameworks: [openmm, fastapi, mcp]
keywords: [molecular-dynamics, simulation, cuda, rest, mcp, agent]
difficulty: intermediate
---

# OpenMM REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb24%40sha256%3A4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run bounded OpenMM molecular-dynamics workloads on an NVIDIA GPU through REST or MCP. The image contains OpenMM 8.6.1 and its CUDA 12 plugin. Attach Object Storage or Shared Filesystem to persist artifacts.

**License:** [MIT + LGPL-3.0-or-later](https://docs.openmm.org/latest/userguide/library/01_introduction.html#license) for OpenMM; Apache-2.0 for the API wrapper.

<!-- /factory:intro -->


## What you get

- A bounded asynchronous run API on port 8000 with OpenAPI docs at `/docs`.
- A Streamable HTTP MCP server at `/mcp` for agent/tool integrations.
- One shared queue, run ID, state, and artifact store across REST and MCP.
- OpenMM 8.6.1 and CUDA support installed when the image is built.
- Readiness gated by a real OpenMM CUDA integration step.
- Results under `/mnt/hcls/openmm-md/runs/<run-id>`; persistent only with an attached volume.

The image installs `openmm[cuda12]==8.6.1` on a digest-pinned CUDA base.
No NGC account or runtime download is needed. Startup completes a real CUDA
integration step before the API advertises readiness. Change versions by
rebuilding and validating a new image.

## Create the endpoint

The button does not attach storage. Manually attach Object Storage or Shared
Filesystem read-write at `/mnt/hcls` in the create form for persistent results.
Without that attachment, `/mnt/hcls` is on ephemeral disk and results can be lost
when the endpoint is replaced or deleted.

Click **Create Endpoint** above, select your project, and review the pre-filled
form. Before creating it:

1. Keep **Token authentication** enabled and copy the generated endpoint token.
   The same token protects REST and MCP; it is not an environment variable.
2. Manually attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`.

There are no required application environment variables or image-pull secrets.

## Storage

Attach either supported storage type read-write at `/mnt/hcls`:

- **Object Storage:** choose a bucket and its access credentials in the volume
  controls.
- **Shared Filesystem:** choose a filesystem in the project.

Runs execute on endpoint-local scratch and publish inputs, results, logs, hashes,
and status snapshots to the mount. Object Storage credentials belong to the
Serverless volume configuration; they are not application environment variables.
Without a persistent resource, `/mnt/hcls` is endpoint-local and can disappear
when the worker is replaced.

## Test REST and MCP

Set the managed URL and generated endpoint token:

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.<region>.nebius.cloud'
export TOKEN='<endpoint-token-generated-during-create>'
```

Startup probes the installed CUDA backend. Poll readiness:

```bash
until curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/v1/health/ready" >/dev/null; do echo 'waiting for OpenMM…'; sleep 15; done
```

Submit the bounded NVT argon smoke through REST:

```bash
RUN_ID="$({
  curl -sS -X POST "$BASE_URL/v1/runs" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{
      "input": {
        "particle_count": 512,
        "steps": 10000,
        "integrator": "LangevinMiddle",
        "precision": "mixed",
        "seed": 17
      },
      "client_request_id": "openmm-first-run",
      "research_use_acknowledgement": true
    }'
} | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/v1/runs/$RUN_ID" \
  | python3 -m json.tool
```

For a real end-to-end REST/MCP interoperability check:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-client.txt
export HCLS_ENDPOINT_TOKEN="$TOKEN"
.venv/bin/python scripts/test_endpoint.py "$BASE_URL" \
  --payload '{"particle_count":512,"steps":1000,"integrator":"LangevinMiddle","precision":"mixed","seed":17}'
```

Configure an MCP-capable agent with the managed URL plus `/mcp`, Streamable HTTP
transport, and the same bearer token. Available tools are `get_capabilities`,
`submit_run`, `get_run`, `list_runs`, `cancel_run`, and `list_run_artifacts`.
Install the included [`openmm-serverless` Agent Skill](./skills/openmm-serverless/SKILL.md)
to give the agent the scientific and operational workflow. Keep credentials in
the MCP client configuration, never in the skill.

## Expected output

A successful run reports the installed OpenMM version, CUDA
platform, precision, ensemble, energies, simulated time, wall time, and
`integration_ns_per_day`. Artifacts include the request, result, logs, positions
preview, and hashes.

See [validation results](./VALIDATION.md) for the tested image and workloads.

This endpoint implements a synthetic periodic argon system, not arbitrary
biomolecular inputs. `LangevinMiddle` is NVT; `Verlet` is NVE. Treat its
`ns/day` only as throughput for this exact synthetic system, not as biological
validation or predicted performance for another system.

## Build the wrapper

```bash
cd templates/endpoint-openmm
docker build --platform linux/amd64 \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t <your-registry>/openmm-rest-mcp:1 .
```

<!-- factory:cli -->

## CLI alternative

The tested image is `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb24@sha256:4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184`.
The qualification used Nebius CLI 0.12.206, which rejects endpoint image references
longer than 64 characters when creating a VM label. For that CLI, use the short
alias below and verify its digest with [crane](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
before creating the endpoint. Do not use an alias whose digest differs.

```bash
export IMAGE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb24:r0918'
test "$(crane digest "$IMAGE")" = 'sha256:4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184' || exit 1
```

Choose either a Shared Filesystem or Object Storage volume and create the service:

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export OPENMM_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or use: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name openmm-rest-mcp \
  --image "$IMAGE" \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --container-port 8000 \
  --disk-size 100Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --volume "$OPENMM_VOLUME"
```

<!-- /factory:cli -->

## Cost and cleanup

The link selects regular L40S for an interactive API. Use preemptible capacity
for disposable tests. The endpoint accrues GPU, disk, and attached-storage charges while
provisioned; stop or delete it when no longer needed.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Endpoint is running but returns 502 | Image startup or the CUDA probe is still in progress; poll readiness and inspect logs. |
| CUDA is unavailable | Use a GPU platform and an image compatible with its driver. |
| Results disappear after restart | Attach Object Storage or Shared Filesystem at `/mnt/hcls`. |
| REST works but MCP returns 401 | Send the same endpoint bearer token to `/mcp`. |
