# OpenMM REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fopenmm-md-api%3A20260908-dynamic-v3&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true&amp;env=NGC_API_KEY&amp;env=OPENMM_VERSION%3Dlatest&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run bounded OpenMM molecular-dynamics workloads on an NVIDIA GPU through REST or MCP. A lean API image pulls the selected official NVIDIA OpenMM runtime at endpoint startup and persists artifacts to Object Storage or Shared Filesystem.

**License:** [MIT](https://github.com/openmm/openmm/blob/master/LICENSE) · **Runtime:** [`nvcr.io/nvidia/openmm`](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/openmm)

<!-- /factory:intro -->

---

title: OpenMM REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-l40s-a
frameworks: [openmm, fastapi, mcp]
keywords: [molecular-dynamics, simulation, nvidia-ngc, rest, mcp, agent]
difficulty: intermediate

---

## What you get

- A bounded asynchronous run API on port 8000 with OpenAPI docs at `/docs`.
- A Streamable HTTP MCP server at `/mcp` for agent/tool integrations.
- One shared queue, run ID, state, and artifact store across REST and MCP.
- Runtime selection with `OPENMM_VERSION=latest` or an exact NVIDIA tag.
- Readiness gated by a real OpenMM CUDA integration step.
- Persistent results under `/mnt/hcls/openmm-md/runs/<run-id>`.

The wrapper image contains the API and pull launcher, not OpenMM. At fresh endpoint
startup it authenticates to NGC with `NGC_API_KEY`, pulls
`nvcr.io/nvidia/openmm`, and starts the API only after the selected runtime passes
the CUDA probe. Restarting an endpoint configured with `latest` lets it select a
newer compatible stable release without publishing a new wrapper.

The pre-built wrapper tag in the button resolves to
`sha256:7d73bc0d6270e7bf2fcf04a6ee7544dc8a6527b7383d2e77408cb8d3f476d416`.

## Create the endpoint

Click **Create Endpoint** above, select your project, and review the pre-filled
form. Before creating it:

1. Paste your NVIDIA NGC API key into `NGC_API_KEY`. The launcher supplies NGC's
   fixed `$oauthtoken` username internally.
2. Leave `OPENMM_VERSION=latest`, or replace it with an exact NVIDIA tag such as
   `8.1.1`.
3. Keep **Token authentication** enabled and copy the generated endpoint token.
   The same token protects REST and MCP; it is not an environment variable.
4. Attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`.

The deployment URL declares every application environment variable but contains
no credential value. Storage is selected from the customer's own project.

### Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `NGC_API_KEY` | yes | empty | Pulls the official NVIDIA OpenMM runtime. |
| `OPENMM_VERSION` | no | `latest` | NVIDIA runtime tag or newest compatible stable tag. |

An explicitly pinned tag is never silently replaced with another version.

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

First boot can take several minutes while the official runtime is downloaded and
probed. Poll readiness:

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

A successful run reports the resolved NVIDIA tag/digest, OpenMM version, CUDA
platform, precision, ensemble, energies, simulated time, wall time, and
`integration_ns_per_day`. Artifacts include the request, result, logs, positions
preview, and hashes.

Qualification on 2026-09-08 used regular L40S. `latest` resolved to official
OpenMM `8.1.1` at digest
`sha256:f4943aef3df103f05d0e502ea0711fce4a32a92366585b0f5bd7a5b01c9b5b59`;
REST and MCP runs both succeeded and their result artifacts were hash-verified
through REST and in the mounted bucket.

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

Choose either a Shared Filesystem or Object Storage volume and create the service:

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export NGC_API_KEY='<your-ngc-api-key>'
export OPENMM_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or use: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name openmm-rest-mcp \
  --image cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/openmm-md-api:20260908-dynamic-v3 \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --container-port 8000 \
  --disk-size 100Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --env "NGC_API_KEY=$NGC_API_KEY" \
  --env 'OPENMM_VERSION=latest' \
  --volume "$OPENMM_VOLUME"
```

<!-- /factory:cli -->

## Cost and cleanup

The link selects regular L40S because this is a retained API and replacement
workers must pull the runtime again. Use preemptible capacity only for disposable
tests. The endpoint accrues GPU, disk, and attached-storage charges while
provisioned; stop or delete it when no longer needed.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| NGC returns 401/403 | Supply a valid `NGC_API_KEY`; do not use the endpoint token. |
| Endpoint is running but returns 502 | Runtime download/probing is still in progress; poll readiness and inspect logs. |
| CUDA is unavailable | Use a GPU platform and a runtime tag compatible with its driver. |
| Results disappear after restart | Attach Object Storage or Shared Filesystem at `/mnt/hcls`. |
| REST works but MCP returns 401 | Send the same endpoint bearer token to `/mcp`. |
| A pinned tag fails | Choose `latest` or another compatible official tag; pinned tags never fall back. |
