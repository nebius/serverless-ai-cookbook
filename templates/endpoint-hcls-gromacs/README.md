# GROMACS GPU MD REST and MCP service

GROMACS 2023.2 molecular dynamics behind the HCLS asynchronous endpoint contract,
using NVIDIA GPU nonbonded offload. One process exposes both the REST API and an
MCP Streamable HTTP endpoint on port 8000. Nebius endpoint authentication protects
both protocols with the same bearer token.

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fgromacs-md-api%40sha256%3Aef1c0bd2670ecc2c57ff2c870efac2848c031bcc48a850538bec833fce2a9b7b&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;volumeMountPath=%2Fmnt%2Fhcls"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

Before creating the endpoint, enable token authentication in the Console. The link
uses the live-qualified, unique release tag and regular L40S capacity. Attach either
an Object Storage bucket or a Shared Filesystem at `/mnt/hcls` with read-write access.
Do not attach both resources at the same path.

**License:** [LGPL-2.1](https://gitlab.com/gromacs/gromacs/-/blob/main/COPYING) ·
**Source image:** `nvcr.io/hpc/gromacs:2023.2`, pinned by digest in the Dockerfile

```bash
docker build --platform linux/amd64 \
  -f templates/endpoint-hcls-gromacs/Dockerfile \
  -t hcls-gromacs-md-api:local .
```

## Persistent storage

The image always writes persistent state below
`/mnt/hcls/gromacs-md/runs/<run-id>`. The mounted resource may be either:

```bash
# Object Storage
--volume "storagebucket-<id>:/mnt/hcls:rw"

# Shared Filesystem
--volume "computefilesystem-<id>:/mnt/hcls:rw"
```

GROMACS executes on endpoint-local scratch storage. Completed inputs, outputs,
logs, hashes, and status are copied to the mounted resource, so the same image works
with the non-POSIX semantics of Object Storage and the POSIX semantics of Shared
Filesystem. The mount is configured by Serverless; no S3 credentials are passed to
the public API, MCP tools, or image.

Serverless currently presents both managed volume types as root-owned mounts and
does not expose a mount UID/GID option. The bounded API process therefore runs as
root in this pilot so it can write to either storage type. It does not accept shell
arguments or arbitrary commands. Revisit the runtime user when Serverless supports
mount ownership configuration.

For a reproducible CLI deployment, set the customer-owned project, subnet, storage
resource, endpoint-token secret, and published image, then run:

```bash
export NEBIUS_PROJECT_ID="project-..."
export NEBIUS_SUBNET_ID="vpcsubnet-..."
export HCLS_STORAGE_RESOURCE_ID="storagebucket-..." # or computefilesystem-...
export AUTH_TOKEN_SECRET_SELECTOR="mbsec-...@mbsecver-..."
# Optional: override the digest-pinned public image selected by deploy.sh.
# export HCLS_IMAGE="cr.eu-north1.nebius.cloud/...@sha256:..."
./templates/endpoint-hcls-gromacs/scripts/deploy.sh
```

The MysteryBox secret referenced by `AUTH_TOKEN_SECRET_SELECTOR` must contain a
payload key named `AUTH_TOKEN`. The token is endpoint access material; it is not an
NGC key and must not be embedded in a deployment link or image.

The guided argon smoke creates a TPR with `grompp`, runs `mdrun -nb gpu`, and returns
the TPR, coordinates, energies, checkpoint, log, command output, and result manifest.
Prepared TPR input is accepted as bounded base64; custom `.gro`, topology, and `.mdp`
text must be supplied together. Arbitrary command-line arguments are never accepted.

```json
{
  "input": {"steps": 10000, "gpu_mode": "gpu", "threads": 1},
  "research_use_acknowledgement": true
}
```

REST routes are described by `/docs` and include `/v1/capabilities`, `/v1/runs`,
run status/cancellation, and authenticated artifact downloads. Agents connect to:

```text
https://<managed-endpoint-host>/mcp
Authorization: Bearer <same endpoint token used by REST>
```

The MCP tools are `get_capabilities`, `submit_run`, `get_run`, `list_runs`,
`cancel_run`, and `list_run_artifacts`. MCP and REST call the same in-process run
manager; an MCP-created run is visible through REST with the same run ID.

To test both protocols after deployment:

```bash
python3 -m venv .venv-hcls-client
.venv-hcls-client/bin/pip install -r templates/endpoint-hcls-gromacs/requirements-client.txt
export HCLS_ENDPOINT_TOKEN="<endpoint token>"
.venv-hcls-client/bin/python templates/endpoint-hcls-gromacs/scripts/test_endpoint.py \
  "https://<managed-endpoint-host>"
```

Run the same client against a bucket-backed endpoint and a filesystem-backed
endpoint. It submits one real GPU run through REST and one through MCP, downloads
and hashes the result manifest with the same bearer token, and proves that the
MCP-created run is also visible through REST.

`ns_per_day` comes from GROMACS `Performance:` output. It describes only the supplied
system, settings, and GPU; it is not a universal hardware ranking. Validate the force
field, ensemble, equilibration, constraints, and sampling for real research.

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
