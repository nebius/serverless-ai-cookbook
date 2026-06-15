---
title: BioNeMo NIM Serverless Endpoint Examples
category: life-sciences
type: endpoint
runtime: nebius-ai-endpoints
frameworks:
  - nvidia-nim
  - bionemo
keywords:
  - bionemo
  - nvidia-nim
  - serverless-endpoints
  - structure-prediction
  - molecular-docking
  - molecule-generation
  - drug-discovery
  - research-only
difficulty: advanced
---

# BioNeMo NIM Serverless Endpoint Examples

This example pack shows how to adapt NVIDIA BioNeMo and HCLS NIM containers for Nebius Serverless AI Endpoints. It is written for conference demo engineers who need copy-ready commands, small nonclinical payloads, readiness and metrics checks, and cleanup steps.

These examples are **research-only**. Do not submit patient data, PHI, confidential sequences, proprietary compounds, or clinical decision-support workloads. The sample inputs below use public or synthetic protein and molecule examples only.

## What this example does

- Reuses the generic [NVIDIA NIM endpoint mirror pattern](../../inference/nim-endpoint/README.md) for large `nvcr.io` images.
- Deploys a Boltz-2 NIM structure-prediction endpoint from an in-region Nebius Container Registry mirror.
- Calls the `/biology/mit/boltz2/predict` API with a small public ubiquitin sequence.
- Checks `/v1/health/ready` and `/v1/metrics`.
- Cleans up the endpoint so it stops billing.
- Provides a candidate matrix for Boltz/OpenFold, DiffDock, GenMol/MolMIM, RFdiffusion, and ProteinMPNN.

> **Validation scope:** this cookbook includes a sandbox smoke attempt recorded on 2026-06-15. Image mirroring and endpoint creation were exercised, but the Boltz-2 endpoint did not reach readiness, so the sample inference request is not validated on Nebius Serverless Endpoints yet. Treat the commands as deployment-ready scaffolding until you run a green readiness and sample-response validation in your own Nebius project.

## Sandbox smoke attempt: 2026-06-15

The task branch was tested against the Nebius `sandbox` profile after explicit approval to consume GPU:

| Check | Result |
|---|---|
| Project | `project-i00xz31gpr00xp9jhp982v` |
| Platform / preset | `gpu-b200-sxm-a` / `1gpu-20vcpu-224gb` |
| Source image | Forge regional mirror for `nvcr.io/nim/mit/boltz2:1.7.0` |
| Sandbox registry copy | Passed. Copied to a sandbox Container Registry tag, then removed the temporary registry artifacts during cleanup. |
| Runtime NGC key handling | Passed. Used a temporary MysteryBox secret, then deleted it during cleanup. |
| Endpoint create | Partially passed. Endpoint was created and received public/private addresses. |
| Readiness | Failed. Endpoint remained `PROVISIONING`, its compute instance reported `STOPPED`, `/v1/health/ready` timed out, and no container logs were available. |
| Sample inference | Not run. The endpoint never reached readiness. |
| Cleanup | Passed. Endpoint deleted, temporary MysteryBox secret deleted, temporary registry artifacts removed. |

This is not a successful Serverless validation. The most likely follow-up is to rerun with a same-region registry or a fresh NIM endpoint compatibility check for B200 Serverless, then inspect platform-side startup diagnostics if the instance stops before container logs appear.

## Requirements

- Nebius CLI installed and authenticated to a project with Serverless AI Endpoints.
- Docker, `jq`, `curl`, and `openssl`.
- Nebius Container Registry and a subnet in the target region.
- NGC personal or service API key with access to the selected NIM image.
- Accepted NVIDIA/NGC terms for each selected NIM.
- GPU quota for the selected platform.

For the generic NIM setup details, including the large-image cold-start limitation and Container Registry workaround, start with [inference/nim-endpoint](../../inference/nim-endpoint/README.md).

## Cost controls

Serverless endpoints are persistent services and **bill while active**. Before you run a demo:

- Pick an owner who is responsible for deleting the endpoint.
- Use `timeout` around readiness and sample-request loops.
- Keep a terminal with the cleanup command ready.
- Delete the endpoint when the demo is done. Keeping the mirrored image is optional and does not keep the endpoint running.

```bash
export MAX_READY_WAIT="60m"
export REQUEST_TIMEOUT_SECONDS=900

# After a demo, stop billing by deleting the endpoint.
nebius ai endpoint delete "$ENDPOINT_ID"
```

## Run: Boltz-2 structure prediction

Boltz-2 is the concrete structure-prediction example because NVIDIA documents a BioNeMo NIM image and API for protein structure prediction, including the `/biology/mit/boltz2/predict` endpoint. This recipe uses a small public ubiquitin sequence and does not assert biological validity of the output.

### 1. Mirror and deploy the NIM

Run this from the repository root. It reuses the generic NIM helper rather than duplicating the mirror-to-Container-Registry workflow.

```bash
cd inference/nim-endpoint

export PROJECT_ID="<project-id>"
export REGION="us-central1"
export NGC_API_KEY="<nvapi-key>"
export NIM_IMAGE="nvcr.io/nim/mit/boltz2:1.7.0"
export PLATFORM="gpu-h200-sxm"
export PRESET="1gpu-16vcpu-200gb"
export DISK="500Gi"
export AUTH_TOKEN="$(openssl rand -hex 16)"

# Optional when your project has multiple subnets.
# export SUBNET_ID="<subnet-id>"

./scripts/deploy-nim.sh
```

Notes:

- The helper mirrors the image to `cr.${REGION}.nebius.cloud/...` and creates the endpoint from that mirror.
- `DISK=500Gi` leaves room for image layers, model cache, and runtime artifacts. Adjust after validating the exact image version.
- Boltz-2 model assets can take a long time to hydrate from NGC on first boot. For event demos, validate and pre-stage the endpoint only when budget approval exists.

### 2. Resolve the endpoint URL

```bash
export NIM_NAME="boltz2"
export ENDPOINT_ID=$(nebius ai endpoint get-by-name \
  --parent-id "$PROJECT_ID" \
  --name "$NIM_NAME" \
  --format jsonpath='{.metadata.id}')

export ENDPOINT_IP=$(nebius ai endpoint get "$ENDPOINT_ID" \
  --format json | jq -r '.status.public_endpoints[0]')

export URL="http://${ENDPOINT_IP}"
```

### 3. Wait for readiness with a timeout

`RUNNING` means the container is up. The NIM may still be downloading model assets or warming the backend. Poll the NIM readiness route before sending inference traffic.

```bash
timeout "$MAX_READY_WAIT" bash -c '
  until curl -fsS --max-time 15 "$URL/v1/health/ready" \
    -H "Authorization: Bearer $AUTH_TOKEN"; do
    date
    sleep 30
  done
'
```

Expected readiness shape:

```json
{"status":"ready"}
```

Some NIM versions return a larger health object with `status` and `message` fields. Treat HTTP `200` plus a ready status as success.

### 4. Submit a nonclinical sample request

The input sequence below is the public 76-residue ubiquitin sequence commonly associated with PDB `1UBQ`. The request uses the minimum documented `sampling_steps` value to keep a demo request bounded. Increase sampling parameters only after you validate latency and cost.

```bash
cd ../../life-science/bionemo-nim-endpoints

cat > boltz2-ubiquitin.json <<'JSON'
{
  "polymers": [
    {
      "id": "A",
      "molecule_type": "protein",
      "sequence": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
    }
  ],
  "recycling_steps": 1,
  "sampling_steps": 10,
  "diffusion_samples": 1,
  "step_scale": 1.638,
  "output_format": "mmcif"
}
JSON

curl -fsS --max-time "$REQUEST_TIMEOUT_SECONDS" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d @boltz2-ubiquitin.json \
  "$URL/biology/mit/boltz2/predict" \
  | tee boltz2-ubiquitin-response.json \
  | jq '{
      structure_count: (.structures | length),
      first_structure_format: .structures[0].format,
      confidence_scores: .confidence_scores,
      metrics: .metrics
    }'
```

Expected response shape:

```json
{
  "structures": [
    {
      "structure": "data_...\n# mmCIF content omitted",
      "format": "mmcif",
      "name": "optional",
      "source": "optional"
    }
  ],
  "confidence_scores": [0.0],
  "metrics": {
    "request_time": "implementation-specific"
  }
}
```

Exact metric keys and confidence values vary by NIM version and backend. Record one real response artifact before using the endpoint in a live demo.

### 5. Inspect metrics

NIMs expose Prometheus-format metrics on `/v1/metrics` behind the same endpoint token.

```bash
curl -fsS --max-time 20 \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  "$URL/v1/metrics" | sed -n '1,40p'
```

Look for request counters, latency histograms, and GPU telemetry. Metric names can vary by NIM family.

## Optional docking storyboard: DiffDock

DiffDock is useful for protein-ligand docking demos, but do not present it as Serverless-validated from this cookbook. NVIDIA documents `/molecular-docking/diffdock/generate`; prior Forge context recorded a smoke probe, while the June readiness notes still called out missing stricter benchmark completion.

Representative request shape after deploying `nvcr.io/nim/mit/diffdock:2.2.0` with the same mirror pattern:

```bash
curl -fsS --max-time "$REQUEST_TIMEOUT_SECONDS" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "protein": "ATOM records from a public RCSB PDB file",
    "ligand": "public SDF content or a SMILES text file payload",
    "ligand_file_type": "sdf",
    "num_poses": 10,
    "time_divisions": 20,
    "steps": 18,
    "save_trajectory": false,
    "is_staged": false
  }' \
  "$URL/molecular-docking/diffdock/generate"
```

Expected response shape: JSON containing generated ligand pose records or encoded artifacts, usually post-processed into ranked SDF files with confidence labels.

## Candidate matrix

| Candidate | Public NIM image or family | Workflow fit | NGC/license gate | Suggested Nebius starting point | Validation status |
|---|---|---|---|---|---|
| Boltz-2 | `nvcr.io/nim/mit/boltz2:1.7.0` | Protein, ligand, DNA, and RNA structure prediction; good first structure demo. | NGC key and NVIDIA AI Product Agreement/EULA. | `gpu-h200-sxm` / `1gpu-16vcpu-200gb`, `500Gi` disk. NVIDIA docs require at least 48 GB GPU memory. Sandbox also exposed `gpu-b200-sxm-a` / `1gpu-20vcpu-224gb`, but the 2026-06-15 endpoint smoke did not reach readiness. | Concrete cookbook example, but not green on Serverless yet. The 2026-06-15 sandbox run mirrored the image and created an endpoint, then failed before readiness with the instance `STOPPED` and no logs. Task context records `boltz2-nim` as directly ready in Forge on 2026-06-05, which is not the same as Serverless endpoint validation. |
| OpenFold3 / OpenFold2 | `nvcr.io/nim/openfold/openfold3:<pin>` or OpenFold2 NIM tags from NGC. | AlphaFold/OpenFold-style structure prediction, often with MSA inputs. | NGC key and current NIM terms; pin a tag or digest before an event. | Start with `gpu-h200-sxm`; check current driver/CUDA requirements and MSA input requirements. | Storyboard/candidate for this pack. Forge context had OpenFold evidence, but this cookbook does not include current Serverless validation. |
| DiffDock | `nvcr.io/nim/mit/diffdock:2.2.0` | Protein-ligand docking and ranked pose generation. | NGC key and NVIDIA NIM terms. | `gpu-h200-sxm` or `gpu-l40s-a` after checking the current support matrix and endpoint image size. | Storyboard-ready here. Prior Forge smoke probe existed, but June readiness notes still required stricter benchmark completion. |
| GenMol | `nvcr.io/nim/nvidia/genmol:2.0.0` | Small-molecule generation from SAFE/SMILES templates. | NGC key and NVIDIA NIM terms. | `gpu-l40s-a`, `gpu-rtx6000`, or `gpu-h200-sxm`; the documented profile is one GPU and relatively small. | Candidate. Forge inventory shows active support, but no Serverless endpoint run was performed in this task. |
| MolMIM | `nvcr.io/nim/nvidia/molmim:1.0.0` | Controlled molecule generation, embedding, hidden-state, decode, sampling, and generate workflows. | NGC key and MolMIM NIM terms; verify current env var names in NVIDIA docs for the exact tag. | Start with `gpu-h200-sxm` or `gpu-l40s-a`; validate cache path and permissions for the selected image. | Candidate. Task context notes H200 Forge benchmark evidence during onboarding, but not Serverless validation here. |
| RFdiffusion | `nvcr.io/nim/ipd/rfdiffusion:2` or current tagged release. | Binder design, motif scaffolding, and protein backbone generation. | NGC key and NVIDIA AI Product Agreement/EULA. | Use `gpu-h200-sxm` or `gpu-l40s-a` first; avoid making B200 the only demo target until TensorRT cache/platform behavior is rechecked. | Risky candidate. Task context records default-request and B200 TensorRT cache/platform issues; do not use as the only live protein-design demo without a fresh green run. |
| ProteinMPNN NIM | `nvcr.io/nim/ipd/proteinmpnn:<pin>` | Inverse folding and sequence design from public PDB inputs. | Must accept ProteinMPNN NGC terms before pull. Task context recorded NGC license acceptance blocking mirroring. | Small enough for one GPU, but do not plan Serverless use until NGC pull and mirror work. | Unsupported for this pack until terms are accepted and mirrored. Use the Forge `dauparas-proteinmpnn-suite` fallback if it remains ready. |

## How to adapt

- Change `NIM_IMAGE`, `PLATFORM`, `PRESET`, and `DISK` after checking the current NVIDIA NIM support matrix and Nebius platform availability.
- Keep all NIM images mirrored into the same-region Nebius Container Registry before creating endpoints.
- Use public PDB IDs, public ligand CCD/SDF files, or synthetic SMILES only.
- Store NGC keys and endpoint auth tokens in MysteryBox for shared or repeated demos.
- Record the exact image tag or digest, Nebius region, platform, preset, sample request, output artifact, and cleanup timestamp for every validated demo.

## Troubleshooting

- Endpoint reaches `ERROR` quickly with no container logs: mirror the NIM image into Nebius Container Registry first; direct `nvcr.io` pulls can exceed the cold-start window.
- `401`: missing or wrong `Authorization: Bearer $AUTH_TOKEN`.
- `502`: container is up but the NIM is not ready; keep polling `/v1/health/ready`.
- Readiness times out: check `nebius ai endpoint logs "$ENDPOINT_ID" --follow --timestamps`, GPU memory, disk size, NGC key validity, and NGC terms acceptance.
- Request times out: lower demo input size and sampling parameters, then rerun after readiness. Do not loop indefinitely on a billing endpoint.
- NGC pull denied: accept the model's NGC terms with the same account or organization used by the API key.

## Cleanup

Delete the endpoint after every demo window:

```bash
nebius ai endpoint delete "$ENDPOINT_ID"
```

Optional local cleanup:

```bash
rm -f boltz2-ubiquitin.json boltz2-ubiquitin-response.json
docker logout nvcr.io
unset AUTH_TOKEN NGC_API_KEY
```

The mirrored image remains in Container Registry for future demos. Delete it from the registry only if your project policy requires reclaiming registry storage.

## Sources

- [Generic Nebius NVIDIA NIM endpoint pattern](../../inference/nim-endpoint/README.md)
- [NVIDIA Boltz-2 NIM inference API](https://docs.nvidia.com/nim/bionemo/boltz2/latest/inference.html)
- [NVIDIA Boltz-2 NIM support matrix](https://docs.nvidia.com/nim/bionemo/boltz2/latest/support-matrix.html)
- [NVIDIA DiffDock NIM advanced usage](https://docs.nvidia.com/nim/bionemo/diffdock/latest/advanced-usage.html)
- [NVIDIA GenMol NIM getting started](https://docs.nvidia.com/nim/bionemo/genmol/latest/getting-started.html)
- [NVIDIA MolMIM NIM documentation](https://docs.nvidia.com/nim/bionemo/molmim/latest/index.html)
- [NVIDIA RFdiffusion NIM support matrix](https://docs.nvidia.com/nim/bionemo/rfdiffusion/latest/support-matrix.html)
- [NVIDIA ProteinMPNN NIM quickstart](https://docs.nvidia.com/nim/bionemo/proteinmpnn/latest/quickstart-guide.html)
