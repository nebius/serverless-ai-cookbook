# GROMACS GPU MD REST and MCP service

GROMACS 2023.2 molecular dynamics behind the HCLS asynchronous endpoint contract,
using NVIDIA GPU nonbonded offload. One process exposes both the REST API and an
MCP Streamable HTTP endpoint on port 8000. Nebius endpoint authentication protects
both protocols with the same bearer token.

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fgromacs-md-api%3A20260908-2341ac7&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

Before creating the endpoint, enable token authentication in the Console. The link
uses the live-qualified, unique release tag and regular L40S capacity. Attach either
an Object Storage bucket or a Shared Filesystem at `/mnt/hcls` with read-write access.
Do not attach both resources at the same path. The Console link can prefill the image,
port, compute, disk, and mount path; authentication and a customer-owned storage
resource or secret must still be selected in the form. The image itself requires no
customer-supplied runtime environment variables and no registry credentials.

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
# Object Storage. The secret must contain S3_ACCESS_KEY_ID and
# S3_SECRET_ACCESS_KEY. The named local AWS profile supplies the region and
# endpoint when the Nebius CLI resolves the mount.
--volume "s3://<bucket>:/mnt/hcls:rw:<profile>@<s3-secret-selector>"

# Shared Filesystem
--volume "computefilesystem-<id>:/mnt/hcls:rw"
```

GROMACS executes on endpoint-local scratch storage. Completed inputs, outputs,
logs, hashes, and immutable status snapshots are copied to the mounted resource, so
the same image works with the non-POSIX semantics of Object Storage and the POSIX
semantics of Shared Filesystem. The S3 credentials stay in MysteryBox and are used
by the Serverless mount; they are not passed to the public API, MCP tools, image, or
application environment.

Use the explicit `s3://` form for Object Storage. Live acceptance found that a bucket
resource ID could be attached but did not preserve writes across a replacement VM.
The credential-backed `s3://` mount was independently verified through the S3 API
and across a stop/start cycle.

Serverless currently presents both managed volume types as root-owned mounts and
does not expose a mount UID/GID option. The bounded API process therefore runs as
root in this pilot so it can write to either storage type. It does not accept shell
arguments or arbitrary commands. Revisit the runtime user when Serverless supports
mount ownership configuration.

For a reproducible CLI deployment, set the customer-owned project, subnet, storage
resource, and published image, then run:

```bash
export NEBIUS_PROJECT_ID="project-..."
export NEBIUS_SUBNET_ID="vpcsubnet-..."
export HCLS_STORAGE_SOURCE="computefilesystem-..."
./templates/endpoint-hcls-gromacs/scripts/deploy.sh
```

The script enables integrated Serverless Token authentication and, by default,
generates a strong token and prints it once after creation. Store that value
securely and use it for both REST and MCP. No pre-existing MysteryBox secret is
required. To control the token explicitly, set exactly one optional variable:

```bash
# Reuse a managed secret whose payload key is AUTH_TOKEN:
export AUTH_TOKEN_SECRET_SELECTOR="mbsec-...@mbsecver-..."

# Or provide a token directly (do not commit or paste it into a URL):
export AUTH_TOKEN="$(openssl rand -hex 32)"
```

For Object Storage, configure a local AWS profile with its region and Nebius
Object Storage endpoint, then select the corresponding MysteryBox secret:

```bash
aws configure --profile hcls
aws configure set region eu-north1 --profile hcls
aws configure set endpoint_url https://storage.eu-north1.nebius.cloud --profile hcls
export HCLS_STORAGE_SOURCE="s3://<bucket>"
export S3_PROFILE="hcls"
export S3_CREDENTIAL_SECRET_SELECTOR="mbsec-...@mbsecver-..."
./templates/endpoint-hcls-gromacs/scripts/deploy.sh
```

The S3 MysteryBox payload keys are `S3_ACCESS_KEY_ID` and
`S3_SECRET_ACCESS_KEY`. The local profile must refer to the same credentials because
Nebius CLI 0.12 resolves the S3 endpoint and region client-side before it creates the
Serverless resource. Do not put either value in source, links, or environment
variables on the endpoint.

If `AUTH_TOKEN_SECRET_SELECTOR` is used, its MysteryBox payload key must be
`AUTH_TOKEN`. In every mode, the value is endpoint access material enforced by the
Serverless gateway; it is not an application or NGC credential and must not be
embedded in a deployment link or image.

The default public release is
`cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/gromacs-md-api:20260908-2341ac7`,
which resolves to
`sha256:e8e06b7657218226d19e90ccef37c72dff8197aca2f1c94314a2856eec9b7e34`.
The unique release tag is not overwritten. Serverless currently rejects the full
digest reference because the image string is also copied into a 64-character Compute
label, so the digest is recorded here and verified separately.

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
