# GROMACS LibreChat workbench

This CPU Serverless endpoint serves LibreChat with two qualified Nebius Token
Factory chat models and the GROMACS Streamable HTTP MCP server already wired in.
The seeded `GROMACS GPU Workbench` agent can inspect capabilities and runs, submit
only the bounded workflow schema, monitor run IDs, and list artifacts. The actual
simulation continues to run on the separate NVIDIA GPU endpoint.

The image extends the public, live-tested BioNeMo LibreChat runtime at an immutable
digest. That runtime is built from LibreChat `v0.8.8-rc2`, includes an embedded
MongoDB for a self-contained pilot, and was reused here because it already passes
Nebius Serverless browser acceptance. No model or endpoint credential is present in
the image.

## Authentication model

Use Nebius **Token authentication** on the GPU REST/MCP endpoint. That single
Serverless-generated bearer token protects both `/v1/...` and `/mcp`; the GROMACS
application does not implement a second token.

Do not enable Serverless Token authentication on the LibreChat UI endpoint. The
Nebius gateway requires an `Authorization` header even for the first HTML request,
which a normal address-bar navigation cannot supply. LibreChat instead provides its
own email/password login and sends the GPU endpoint token only from its backend.

The wrapper has two credential modes:

- Set `NEBIUS_API_KEY` and `AUTH_TOKEN` as secret environment variables to
  share administrator-managed credentials with every LibreChat user.
- Omit either variable and LibreChat asks each signed-in user for that value, then
  encrypts it in its embedded database. This mode requires no pre-existing
  MysteryBox or SecretStash resource.

`GROMACS_MCP_URL` is not secret. Set it to the full managed HTTPS URL ending in
`/mcp`. It defaults to the retained filesystem-backed acceptance endpoint, so it
must be overridden when a customer deploys their own GROMACS endpoint.

## Create in Serverless

The native Console deep-link contract currently accepts image, platform, preset,
preemptible, command, and storage defaults. It does **not** accept environment
variables, secret values, authentication mode, or the application port as query
parameters. Those values cannot safely or reliably be encoded into a create URL.
The table below is therefore part of the deploy contract, not an optional set of
out-of-band assumptions.

Use this link to prefill the editable image tag and CPU shape:

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Flibrechat-gromacs%3Alatest&amp;platform=cpu-d3&amp;preset=4vcpu-16gb&amp;preemptible=false"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

Then set the remaining fields explicitly:

| Field | Value |
| --- | --- |
| Port | `3080` |
| Network | Public IP |
| Authentication | None |
| Container disk | `100 GiB` |
| `GROMACS_MCP_URL` | `https://<GPU-endpoint-host>/mcp` |
| `NEBIUS_API_KEY` | Optional secret; otherwise entered per user |
| `AUTH_TOKEN` | Optional secret containing the GPU endpoint's generated token; otherwise entered per user |

The Console can create a SecretStash entry inline when adding a secret environment
variable; customers do not need to prepare one in advance. Secret values must not
be put in the URL, image, ordinary environment variables, or source repository.

For a complete and reproducible deployment interface, use the CLI script:

```bash
export NEBIUS_PROJECT_ID="project-..."
export NEBIUS_SUBNET_ID="vpcsubnet-..."
export GROMACS_MCP_URL="https://<GPU-endpoint-host>/mcp"

# Optional administrator-managed credential mappings. Omit both to use the
# encrypted per-user setup screens inside LibreChat.
export TOKEN_FACTORY_SECRET_SELECTOR="<secret selector with NEBIUS_API_KEY>"
export GROMACS_AUTH_TOKEN_SECRET_SELECTOR="<secret selector with AUTH_TOKEN>"

./templates/hcls-librechat/scripts/deploy.sh
```

When mapping the already generated GROMACS Serverless token, reuse its secret: the
payload key is `AUTH_TOKEN`, and LibreChat sends that same value in the outbound
MCP `Authorization` header. It is not a second application credential.

## Image versions

`latest` is useful as an editable Console default, but an accepted deployment
should use a unique release tag. Moving `latest` makes demos convenient; a
versioned tag makes them reproducible.

Current accepted release:

```text
cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/librechat-gromacs:20260908-1e064ed
sha256:0cc3f0cab62e6e5af06840cbe066d4d56c77b69271e69003a8e4cf2349d9f119
```

The public `latest` tag currently resolves to the same digest.

There are two independent image choices:

- `IMAGE` in `scripts/deploy.sh` selects this deployable LibreChat wrapper tag.
- `LIBRECHAT_BASE` is a Docker build argument for changing the LibreChat base when
  building a new wrapper.

For the GPU endpoint, `GROMACS_BASE` in
[`../endpoint-hcls-gromacs/Dockerfile`](../endpoint-hcls-gromacs/Dockerfile) selects
the official NVIDIA base, for example
`nvcr.io/hpc/gromacs:2023.2`. A Serverless user cannot change that parent tag at
runtime: each supported NVIDIA tag needs a corresponding tested wrapper build,
because the raw NVIDIA image does not contain the REST/MCP service.

```bash
docker build --platform linux/amd64 \
  --build-arg LIBRECHAT_BASE="cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/ba:librechat-0.2.7-20260908@sha256:1eaa9a5e7dc7e7a141d6f452f46e5547646a7c6113e610348511f801e7b185d1" \
  -f templates/hcls-librechat/Dockerfile \
  -t hcls-librechat-gromacs:local .
```

## Test

The retained acceptance deployment is:

```text
Endpoint: aiendpoint-e00xz2grwmjn6yr2n1
URL: https://port3080-tsahyyy1dz4v3f8.tunnel.applications.eu-north1.nebius.cloud
```

Open the managed LibreChat URL, register an account, and choose `GROMACS
Workbench · GLM 5.2`. Start with:

```text
List the available GROMACS capabilities and explain the safety limits.
```

The response should show an MCP tool step and report the live engine version,
NVIDIA CUDA requirement, bounded inputs, queue/concurrency limits, and the
research-only disclaimer. A compute starter intentionally asks for confirmation
before `submit_run` is called.

Operational checks:

```bash
curl -fsS "https://<librechat-host>/health"
nebius ai endpoint logs <librechat-endpoint-id> --tail 200
```

The logs should include `GROMACS workbench agent is ready`, six initialized
GROMACS tools, and `Server readiness checks passing`. The embedded database and
generated LibreChat encryption keys live on the endpoint's container disk. For a
production multi-replica or durable service, use an external authenticated MongoDB
and managed application secrets rather than this single-node pilot topology.
