# HCLS Serverless API and workbench architecture

Status: accepted implementation baseline, 2026-09-04

## Product topology

The product is five independently deployable compute APIs plus one reusable
browser workbench:

| Service | Compute | Primary customer job |
| --- | --- | --- |
| OpenMM | 1x NVIDIA L40S | bounded periodic synthetic molecular-dynamics examples and API integration |
| GROMACS | 1x NVIDIA L40S | GPU-offloaded MD from a prepared TPR or guided public example |
| AutoDock Vina | CPU | familiar, low-cost interactive docking and small batches |
| AutoDock-GPU | 1x NVIDIA L40S | CUDA-accelerated batch screening against prepared maps |
| Parabricks DeepVariant | 2x NVIDIA H100 candidate, at least 24 vCPU/100 GB RAM | bounded BAM/CRAM-to-VCF research workflow |
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
volume is configured, terminal records and their idempotency keys are restored after
a worker restart; interrupted records become explicit failures. The first
release deliberately avoids passing object-storage credentials through the
public API. Large-data workflows such as Parabricks use separately validated
HTTPS or mounted-storage inputs and never persist signed URLs in metadata.

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
- Registry: `registry-e00jz93pkqx2m4vqj4`
- Image namespace: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/`
- GPU qualification default: `gpu-l40s-a`, `1gpu-8vcpu-32gb`
- CPU default: `cpu-d3`, `4vcpu-16gb`
- Networking: public IP plus Nebius managed HTTPS
- Authentication: Nebius endpoint token; token values remain outside source,
  image layers, task files, logs, and URLs
- Qualification: preemptible when available; final acceptance endpoints use
  regular capacity and remain running for user verification

Parabricks starts with a two-H100 candidate that meets NVIDIA's documented CPU/RAM
recommendation and may need a larger preset after measured disk/memory qualification.
The initial build extends the immutable digest of
the existing public Nebius Parabricks 4.7.0-1 API image used by the approved reference
deployment because the direct NGC credential is currently unavailable. Promotion is
still conditional on the NVIDIA AI Product Agreement and an explicit distribution
review; public pull/use rights are not treated as blanket redistribution rights.

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
