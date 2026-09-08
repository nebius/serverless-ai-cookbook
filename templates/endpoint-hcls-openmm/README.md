# OpenMM GPU REST + MCP API

This template exposes the official NVIDIA OpenMM runtime through the shared HCLS
asynchronous API. The small wrapper image pulls `nvcr.io/nvidia/openmm` when the
endpoint starts, authenticates with `NGC_API_KEY`, and selects either the requested
tag or the highest stable tag when `OPENMM_VERSION=latest`.

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fopenmm-md-api%3A20260908-dynamic-v3&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

The Console URL can prefill only image, port, compute, disk, capacity type, and mount
path. Before selecting **Create**, add every item below; none is implied by the link:

| Setting | Value |
| --- | --- |
| Plain environment variable | `OPENMM_VERSION=latest` (or an exact NVIDIA tag such as `8.1.1`) |
| Secret environment variable | `NGC_API_KEY` from a MysteryBox payload key named `NGC_API_KEY` |
| Authentication | Serverless **Token authentication**, generated or backed by a MysteryBox token secret |
| Persistent storage | Object Storage or Shared Filesystem, read-write at `/mnt/hcls` |

At qualification time, `latest` resolved to NVIDIA tag `8.1.1` and digest
`sha256:f4943aef3df103f05d0e502ea0711fce4a32a92366585b0f5bd7a5b01c9b5b59`.
The endpoint publishes its requested tag, resolved tag, digest, and CUDA startup-probe
result in `/v1/health/ready` and `/v1/capabilities`. Changing `OPENMM_VERSION` on a new
endpoint changes the official runtime without rebuilding the API wrapper.

## Deploy from the CLI

The helper makes all otherwise-hidden inputs explicit and supports both storage lanes:

```bash
export NEBIUS_PROJECT_ID=project-...
export NEBIUS_SUBNET_ID=vpcsubnet-...
export NGC_API_KEY_SECRET_SELECTOR=mbsec-...@mbsecver-...
export HCLS_STORAGE_SOURCE=s3://customer-bucket
export S3_CREDENTIAL_SECRET_SELECTOR=mbsec-...@mbsecver-...
export S3_PROFILE=hcls
export AWS_CONFIG_FILE=/path/to/aws-config
# Or: export HCLS_STORAGE_SOURCE=computefilesystem-...

# Optional; defaults shown here.
export OPENMM_VERSION=latest
export AUTH_TOKEN_SECRET_SELECTOR=mbsec-...@mbsecver-...
templates/endpoint-hcls-openmm/scripts/deploy.sh
```

The named AWS profile must be explicit as well:

```ini
[profile hcls]
region=eu-north1
endpoint_url=https://storage.eu-north1.nebius.cloud
```

If neither `AUTH_TOKEN_SECRET_SELECTOR` nor `AUTH_TOKEN` is set, the helper generates
a strong token and shows it once. The NGC key authenticates the NVIDIA image pull; it
does not authenticate API users.

## API and MCP

REST and MCP share the endpoint URL, Serverless token, run queue, and artifacts:

- REST base: `https://<managed-endpoint>/v1`
- MCP Streamable HTTP: `https://<managed-endpoint>/mcp`
- Persistent runs: `/mnt/hcls/openmm-md/runs/<run_id>`

The guided workload is a bounded periodic Lennard-Jones argon system for integration
and GPU plumbing validation, not a biological simulation:

```json
{
  "input": {
    "particle_count": 512,
    "steps": 10000,
    "integrator": "LangevinMiddle",
    "precision": "mixed",
    "seed": 17
  },
  "research_use_acknowledgement": true
}
```

Test both interfaces and artifact interoperability:

```bash
python3 -m venv .venv-hcls-client
.venv-hcls-client/bin/pip install -r templates/hcls-common/requirements-client.txt
export HCLS_ENDPOINT_TOKEN='<Serverless token>'
.venv-hcls-client/bin/python templates/hcls-common/scripts/test_endpoint.py \
  'https://<managed-endpoint>' \
  --payload '{"particle_count":512,"steps":1000,"integrator":"LangevinMiddle","precision":"mixed","seed":17}'
```

The first start is intentionally slower because the wrapper downloads, verifies, and
extracts the selected NVIDIA runtime. Results report CUDA, precision, ensemble,
energies, simulated time, and ns/day. See [the common API](../hcls-common/README.md)
and [HCLS Workbench](../hcls-workbench/README.md).

**License:** [OpenMM MIT](https://github.com/openmm/openmm/blob/master/LICENSE)
