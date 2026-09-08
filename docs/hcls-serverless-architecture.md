# HCLS Serverless API and workbench architecture

Status: dynamic NVIDIA runtime baseline, 2026-09-08

## Product topology

The product is five independently deployable compute APIs plus one reusable
browser workbench:

| Service | Compute | Primary customer job |
| --- | --- | --- |
| OpenMM | 1x NVIDIA L40S | version-selectable official NVIDIA runtime; bounded periodic synthetic MD examples and API integration |
| GROMACS | 1x NVIDIA L40S | GPU-offloaded MD from a prepared TPR or guided public example |
| AutoDock Vina | CPU | familiar, low-cost interactive docking and small batches |
| AutoDock-GPU | 1x NVIDIA H100 for the source-build fallback | CUDA-accelerated batch screening; official NGC 2020.06 is blocked on current Serverless GPUs |
| Parabricks DeepVariant | 1x NVIDIA H100 bounded demo; 8x is the next available Serverless preset | version-selectable official NVIDIA runtime; bounded BAM/CRAM-to-VCF research workflow |
| HCLS Workbench | CPU | configure a compute endpoint, run guided examples, inspect results/artifacts |

AutoDock Vina and AutoDock-GPU are separate products. AutoDock-GPU accelerates
AutoDock 4.2.6 and is not described as GPU Vina. The workbench may offer both,
but it must not compare their scores as scientifically equivalent.

## Shared API

Every newly wrapped compute image exposes:

- `GET /healthz` and `GET /v1/health/ready`
- `GET /v1/capabilities`
- `POST /v1/runs`
- `GET /v1/runs`
- `GET /v1/runs/{run_id}`
- `POST /v1/runs/{run_id}/cancel`
- `GET /v1/runs/{run_id}/artifacts/{name}`

The shared layer owns bounded queueing, idempotency, state transitions, artifact
hashing, safe artifact paths, timestamps, error shaping, and research-use
acknowledgement. An engine adapter owns scientific inputs, execution, and
engine-specific result semantics. One process accepts at most one active run
and eight queued runs by default; these limits are configurable but never
unbounded.

Artifacts live on endpoint disk while the endpoint is retained. When a persistent
volume is configured, ordered immutable status snapshots, terminal records, and
their idempotency keys are restored after a worker restart; interrupted records
become explicit failures. Object Storage uses the credential-backed `s3://` mount
and Shared Filesystem uses its resource ID, but both appear at `/mnt/hcls` to the
same image. Storage credentials remain in MysteryBox and the Serverless mount layer;
they are never passed through the public API or MCP tools. Large-data workflows such
as Parabricks use separately validated HTTPS or mounted-storage inputs and never
persist signed URLs in metadata.

## Workbench trust boundary

The workbench is a CPU endpoint. Its own application-level access key is supplied as
a runtime secret, while its Nebius HTTPS edge is browser-reachable without requiring
a custom Authorization header. After login, a user enters a managed HTTPS compute
endpoint and its Nebius token into an HTTPS form. The server stores that connection
only in process memory under a random HttpOnly SameSite cookie. CSRF checks protect
mutating requests. Tokens do not appear in URLs, browser storage, templates,
analytics, access logs, or source. The browser talks only to the workbench; the
workbench performs authenticated compute calls.

The workbench discovers `/v1/capabilities`, renders guided forms from the
declared service identity, submits runs, polls status, and proxies artifact
downloads. Opening a page never starts compute.

## Deployment baseline

- Project: `project-e00z6b02t8ddk96c49` (`rene`)
- Region: `eu-north1`
- Subnet: `vpcsubnet-e00p701fa30cj5f7wq` (`default-subnet-uou7qfuh`)
- Public registry: `registry-e00jz93pkqx2m4vqj4`
- Private terms-gated registry: `registry-e00j70hx633t3qcj0f`
- Image namespace: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/`
- GPU qualification default: `gpu-l40s-a`, `1gpu-8vcpu-32gb`
- CPU default: `cpu-d3`, `4vcpu-16gb`
- Networking: public IP plus Nebius managed HTTPS
- Authentication: Nebius endpoint token for compute APIs; the browser workbench
  uses its own MysteryBox-backed login and a server-side compute-token proxy.
  Token values remain outside source, image layers, task files, logs, and URLs.
- Qualification: preemptible when available; final acceptance endpoints use
  regular capacity and remain running for user verification

OpenMM and Parabricks use lean public API wrappers. At endpoint startup each wrapper
uses a MysteryBox-injected `NGC_API_KEY` to authenticate to NGC, resolves its version
environment variable (`OPENMM_VERSION` or `PARABRICKS_VERSION`), records the official
digest, extracts the selected runtime, and runs a real CUDA probe before serving.
`latest` means the highest stable tag that passes the probe; exact tags fail closed.
The same Serverless token protects REST and MCP. The NGC key is pull-only and is never
used as an API credential.

NVIDIA recommends two GPUs and at least 24 CPU threads/100 GB RAM for Parabricks,
but the current H100 Serverless presets expose one or eight GPUs. The bounded public
chr20 test therefore starts with one H100; production users should qualify the
eight-GPU shape when its throughput justifies the cost.

The AutoDock-GPU wrapper implements the same dynamic contract, but NGC currently
offers only `nvcr.io/hpc/autodock:2020.06`. Its bundled binary fails a real docking
probe on the current Serverless GPU generations and the image contains no source to
rebuild. It therefore has no dynamic-NGC deploy button until NVIDIA publishes a
compatible tag; the separately labelled H100 source-build fallback remains available.

## Release and evidence gates

Images are built for `linux/amd64`, labelled with source revision/time, pushed
to unique candidate tags, resolved to immutable digests, and then subjected to
SBOM generation plus Grype, Trivy vulnerability, and Trivy secret checks.
Fixable critical vulnerabilities or detected secrets block promotion.

Acceptance records the immutable image, endpoint ID/URL, platform/preset,
actual accelerator identity, request payload, timestamps, output/artifact
hashes, and workload metric. OpenMM/GROMACS report `ns/day`; AutoDock-GPU
reports ligands/hour and GPU utilization; request latency is kept separate.

All supplied examples use public nonclinical data. Results are computational
research outputs, not diagnostic or clinical conclusions.
