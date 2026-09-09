# AutoDock-GPU REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fautodock-gpu-api%3A20260909-rest-mcp-sm80-sm90&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run CUDA-accelerated AutoDock-GPU redocking and bounded ligand screening through REST or MCP. This functional image builds AutoDock-GPU v1.6 from pinned upstream source for SM80, SM86, SM89, and SM90 GPUs and persists artifacts to Object Storage or Shared Filesystem.

**License:** GPL-2.0-only with LGPL components · **Source:** [AutoDock-GPU](https://github.com/ccsb-scripps/AutoDock-GPU) at `e63e6f6280ebfad18caa3e8f48afdc269e79e063`

<!-- /factory:intro -->

---

title: AutoDock-GPU REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-h100-sxm
frameworks: [autodock-gpu, cuda, fastapi, mcp]
keywords: [molecular-docking, virtual-screening, gpu, rest, mcp, agent]
difficulty: advanced

---

## What you get

- AutoDock-GPU v1.6 with native CUDA code for SM80/86/89/90.
- A bounded asynchronous REST API on port 8000 with `/docs`.
- A Streamable HTTP MCP server at `/mcp` using the same run manager.
- A real 1STP docking startup probe before application readiness.
- A public 1STP/biotin redocking smoke and up to 32 supplied ligands against the
  bundled 1STP affinity maps.
- Persistent runs under `/mnt/hcls/autodock-gpu/runs/<run-id>`.

This is GPU acceleration of AutoDock 4 scoring, not GPU-accelerated AutoDock
Vina. Their scores and rankings are not directly comparable.

## GPU compatibility

The image contains native cubins only for these CUDA compute capabilities:

| Target | Example GPUs | Status |
| --- | --- | --- |
| SM80 | A100, A30 | compiled, not acceptance-tested here |
| SM86 | A10, A40 | compiled, not acceptance-tested here |
| SM89 | L4, L40, L40S | compiled, not acceptance-tested here |
| SM90 | H100, H200, GH200 | compiled; H100 acceptance-tested |

**Blackwell is not supported by this image.** B200/GB200 require SM100 and
B300/GB300 require SM103. The container process might start on those GPUs, but
CUDA docking cannot execute; the real startup probe therefore keeps the API
unready instead of accepting doomed work. Rebuild and validate explicit Blackwell
targets before selecting a Blackwell Serverless platform.

The default is H100 because that exact binary completed a real acceptance run.

## Why this image is source-built

NVIDIA NGC currently exposes only `nvcr.io/hpc/autodock:2020.06`. Its executable
targets older GPU generations and failed a real docking probe on the available
Nebius Serverless GPUs. This template therefore uses the pinned upstream
AutoDock-GPU v1.6 source build rather than presenting the known-incompatible NGC
runtime as customer-ready. The image contains upstream license texts and its
corresponding source archive.

No NGC key is required because the engine is already compiled into this image.
Updating AutoDock-GPU or its target architectures requires publishing and testing
a new wrapper image; there is no misleading `AUTODOCK_VERSION` environment switch.

## Create the endpoint

Click **Create Endpoint**, select your project, then:

1. Keep H100 `1gpu-16vcpu-200gb` unless you deliberately choose another GPU from
   the supported table and validate it.
2. Keep **Token authentication** enabled and copy the generated token. It protects
   both REST and MCP and is not an environment variable.
3. Attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`.

The link contains every application setting and no credential. There are no
required environment variables.

## Storage

Docking executes on local scratch, then publishes inputs, DLG/XML output, score
tables, summaries, logs, and hashes to
`/mnt/hcls/autodock-gpu/runs/<run-id>`. Object Storage credentials are configured
on the Serverless volume; they are never sent to the API. Without a persistent
mount, outputs can disappear when the worker is replaced.

## Test REST and MCP

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.<region>.nebius.cloud'
export TOKEN='<endpoint-token-generated-during-create>'
```

Readiness succeeds only after the binary completes real CUDA docking:

```bash
until curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/v1/health/ready" >/dev/null; do echo 'waiting for AutoDock-GPU…'; sleep 15; done
```

Submit the public 1STP/biotin smoke through REST:

```bash
RUN_ID="$({
  curl -sS -X POST "$BASE_URL/v1/runs" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{
      "input": {"nrun": 5, "max_evaluations": 250000, "seed": 17},
      "client_request_id": "autodock-gpu-first-run",
      "research_use_acknowledgement": true
    }'
} | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
```

Test both interfaces and artifact interoperability:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-client.txt
export HCLS_ENDPOINT_TOKEN="$TOKEN"
.venv/bin/python scripts/test_endpoint.py "$BASE_URL" \
  --payload '{"nrun":5,"max_evaluations":250000,"seed":17}'
```

Configure an MCP-capable agent with the managed URL plus `/mcp`, Streamable HTTP
transport, and the same bearer token. Available tools are `get_capabilities`,
`submit_run`, `get_run`, `list_runs`, `cancel_run`, and `list_run_artifacts`.
Install the included
[`autodock-gpu-serverless` Agent Skill](./skills/autodock-gpu-serverless/SKILL.md)
for compatibility, scoring, submission, and artifact guidance. Credentials stay
in the MCP client, never in the skill.

## Custom ligand batch

Provide up to 32 objects with safe unique `id` and bounded ligand `pdbqt` text in
`ligands`. This template docks them only against the bundled 1STP affinity maps;
it does not accept arbitrary grid maps or shell commands. Parameters are bounded
by `/v1/capabilities`.

## Expected output

A successful run reports the GPU and driver, engine/source revision, scoring
semantics, requested runs/evaluations, and best estimated binding energy for each
ligand. Artifacts include DLG/XML output, score CSV, input copies, summary, logs,
and SHA-256 values. Qualification on 2026-09-09 used an H100 and the public image
at digest
`sha256:6e5090b387dfeef7a6a20fce6b12ed7d2d1b2d79675db8c7813dadb5a0087f77`.
Independent REST and MCP runs completed in about 0.6 seconds and reported best
AutoDock4 energies of `-8.26` and `-8.17 kcal/mol`; both result artifacts were
hash-verified through REST and all artifacts were confirmed in the mounted
bucket. Use these only as plumbing checks for this bundled case.

Docking scores are research heuristics, not experimental binding free energies.
Validate molecule preparation, grids, parameters, poses, and conclusions
independently.

## Build the image

The build uses pinned CUDA 12.8.1 devel/runtime images and compiles upstream
revision `e63e6f6` for targets `80 86 89 90`:

```bash
cd templates/endpoint-autodock-gpu
docker build --platform linux/amd64 \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t <your-registry>/autodock-gpu-rest-mcp:1 .
```

<!-- factory:cli -->

## CLI alternative

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export AUTODOCK_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name autodock-gpu-rest-mcp \
  --image cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/autodock-gpu-api:20260909-rest-mcp-sm80-sm90 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --container-port 8000 \
  --disk-size 100Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --volume "$AUTODOCK_VOLUME"
```

<!-- /factory:cli -->

## Cost and cleanup

The link selects retained regular H100 capacity because it is the accepted GPU.
Use preemptible only for disposable tests. GPU, disk, and attached-storage charges
accrue while the endpoint is provisioned; stop or delete it when finished.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Startup probe reports no kernel image | The GPU architecture is absent from this build; use SM80/86/89/90 or rebuild and test it. |
| Blackwell endpoint never becomes ready | This image deliberately rejects unsupported SM100/SM103 execution. |
| Ligand is rejected | Supply valid bounded PDBQT with a safe unique ID. |
| Score differs from Vina | AutoDock4 and Vina scoring are not interchangeable. |
| Results disappear after restart | Attach Object Storage or Shared Filesystem at `/mnt/hcls`. |
| REST works but MCP returns 401 | Use the same Serverless endpoint bearer token for `/mcp`. |
