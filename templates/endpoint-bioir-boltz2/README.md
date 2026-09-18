---
title: BioNeMo Inference Runtime Boltz-2 Endpoint
category: life-sciences
type: endpoint
runtime: nebius-serverless-ai
frameworks: [bionemo-inference-runtime, pytorch, fastapi]
keywords: [protein-structure-prediction, boltz-2, biomolecular-ai, serverless-endpoints, gpu]
difficulty: advanced
---

# BioNeMo Inference Runtime: Boltz-2 tutorial

**Before creating the endpoint, replace the prefilled `JUPYTER_PASSWORD=bionemo-demo`
with your own strong password in the form. Anyone who knows the published demo
password can access the public notebook and run code on its GPU.**

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb26%40sha256%3A98cd41bcc0a6eed1dcd106a59cc74c58a35e711138ad4ad06d482271da914668&amp;targetPort=8888&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=false&amp;command=%2Fusr%2Flocal%2Fbin%2Fbioir-notebook&amp;env=JUPYTER_PASSWORD%3Dbionemo-demo"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

BioNeMo Inference Runtime (BIR) is NVIDIA's Python inference-acceleration library, not a model or a NIM. This one-click template launches a hands-on Boltz-2 tutorial notebook on one L40S, with an optional HTTP-serving example in the same image.

**License:** [BioIR license](https://github.com/NVIDIA-BioNeMo/BioNeMo-Inference-Runtime) · [Boltz-2 MIT license](https://github.com/jwohlwend/boltz)

<!-- /factory:intro -->

Click **Create Endpoint** above and create the endpoint. It launches JupyterLab
on port `8888`, with the tutorial already at
`notebooks/bir_boltz2_tutorial.ipynb`. The image includes the public `bionemo-ir==0.1.0` release, Python 3.12,
JupyterLab, and the optional FastAPI adapter. Dependencies are installed at image
build time. The first prediction retrieves the public Boltz-2 assets. No NGC or
Hugging Face credential is required.

Use NVIDIA driver 580 or newer, as required by the
[released BioIR installation guide](https://docs.nvidia.com/bionemo/inference-runtime/install/).

The published image is
`cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb26@sha256:98cd41bcc0a6eed1dcd106a59cc74c58a35e711138ad4ad06d482271da914668`.

The deployment form is prefilled for port `8888`, one L40S, 500 GiB of disk,
and a `JUPYTER_PASSWORD` field. **Change its prefilled `bionemo-demo` value
before clicking Create.** Open the port-`8888` public endpoint URL, enter your
chosen password, then open `notebooks/bir_boltz2_tutorial.ipynb`.
Cold start pulls the image; the first processor-build cell downloads model assets. The L40S is in BIR's
released support matrix; choose a different compatible platform and preset if
that better suits your project.

## What this demonstrates

This is a tutorial for integrating a library, rather than a prepackaged model
endpoint. The included notebook follows NVIDIA's [BIR quickstart](https://docs.nvidia.com/bionemo/inference-runtime/quickstart/):

1. Create `InputRequest`, `Polymer`, and an inline `MSARecord`.
2. Configure `EngineProcessorConfig(model_source="boltz-2")`.
3. Build and warm the `build_processor` pipeline once per GPU worker.
4. Run the request and inspect its mmCIF output and decoded scores.

The notebook is deliberately authored for this public tutorial; it does not
copy the gated early-access notebook or any of its model-specific examples.

## Open the tutorial notebook

1. Open the one-click form and change `JUPYTER_PASSWORD` to your own strong password.
2. Create the endpoint and wait for it to become `RUNNING`.
3. In the Console, open the public port-`8888` endpoint URL, enter that
   password, then open `notebooks/bir_boltz2_tutorial.ipynb`.
4. Run the cells in order. The processor-build cell is the first one that
   fetches public Boltz-2 assets and can take several minutes on a cold disk.

The notebook starts with the BIR imports and shows the exact `InputRequest`,
`Polymer`, `MSARecord`, `EngineProcessorConfig`, and `build_processor` calls.
It then runs a query-only example and reads its mmCIF and score fields. That is
the teaching path; the HTTP service below is a companion deployment pattern.
The prediction cell uses `await asyncio.to_thread(...)` because BioIR's
synchronous processor manages an event loop of its own, while Jupyter already
has an active event loop.

## Optional HTTP service

The same image also contains a small FastAPI example on port `8000`. To deploy
it, create another endpoint using the same image, set target port `8000`, and
leave the command at its default (`uvicorn server:app --host 0.0.0.0 --port 8000`).
Enable endpoint token authentication for that service. It keeps one BIR
processor resident and maps a request to the same library objects used by the
notebook.

The resulting service exposes:

```text
GET  /healthz       process is alive
GET  /readyz        BioIR, assets, and warmup are complete
POST /v1/fold       one protein chain → mmCIF and scores
GET  /metrics       readiness and non-secret counters
```

Boltz-2 is deliberately the single worked example. BioIR can accelerate other
supported models, but each deserves a separate integration with its own input
schema, model-weight source, license review, memory profile, and output checks.
This is neither a replacement for NVIDIA NIMs nor a way to redistribute the
early-access multi-model container.

## Call the optional HTTP service

Copy the public HTTPS endpoint URL and generated token from the Nebius Console.
Keep the token out of shell history where possible; this example reads it from
your environment.

```bash
export BASE_URL='https://port8000-<endpoint>.tunnel.applications.<region>.nebius.cloud'
export TOKEN='<endpoint-auth-token>'

until curl -fsS -H "Authorization: Bearer $TOKEN" "$BASE_URL/readyz" | jq -e '.status == "ready"' >/dev/null; do
  echo 'waiting for BioIR, Boltz-2 assets, and warmup…'
  sleep 15
done

curl -sS -X POST "$BASE_URL/v1/fold" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"sequence":"ACKIENIKYKGKEVESKLGSQLIDIFNDLDRAKEEYDKLSSPEFIAKFGDWINDEVERNVNEDGEPLLIQDVRQDSSKHYFFILKNGERFDLLTR"}' \
  | jq '{model, model_inference_time_seconds, total_time_seconds, score_keys: (.scores | keys), cif_bytes: (.cif | length)}'
```

Expected output has `"model": "boltz-2"`, a positive `cif_bytes` value, and
one or more score keys. The structure, score values, and timings vary with the
selected BioIR release, GPU, model assets, and random seed.

The default is a query-only inline MSA so that the example is self-contained.
Pass `msa_a3m` with a production-quality alignment for scientific use. The
adapter enforces a 1,024-residue input limit and one in-flight request per GPU;
profile the exact model, input shapes, and hardware before raising either limit.

You can also use the supplied smoke test, which keeps the token out of curl's
command line:

```bash
cd templates/endpoint-bioir-boltz2
export ENDPOINT_URL="$BASE_URL"
export AUTH_TOKEN="$TOKEN"
scripts/smoke-test.sh
```

## Pinned BIR release

This image contains `bionemo-ir==0.1.0`; startup never installs or upgrades it.
`BIOIR_VERSION=0.1.0` verifies the baked version. Changing releases requires an
image rebuild and GPU validation, not an environment-variable update. Exact
Python dependency versions are recorded in `requirements.lock.txt`.

The package release and the public model assets are separate provenance
decisions. Record the selected release, endpoint image digest, asset revision,
GPU type, and warmup/inference measurements with scientific results. NVIDIA's
[model-weights reference](https://docs.nvidia.com/bionemo/inference-runtime/references/model-weights/)
describes the upstream weight sources and their terms.

## Build or mirror the image yourself

Build the pinned public runtime in your own registry. The Dockerfile installs
BioIR and its dependencies; model weights remain a first-prediction download.

```bash
cd templates/endpoint-bioir-boltz2
export IMAGE_TAG='registry.example.org/your-team/bioir-boltz2-serverless:0.3.0'
scripts/build-image.sh
```

The script prints the pushed digest. Use that immutable reference with the
manual helper below, or replace the prefilled image in the Console form.

<!-- factory:cli -->

## CLI alternative

The Console button launches the password-protected notebook. The helper below
launches the optional token-protected HTTP service on port 8000. For that service, first create a MysteryBox secret with an
`AUTH_TOKEN` payload key, then use the digest-pinned public image. CLI 0.12.206 rejects endpoint image
references longer than 64 characters when creating its VM label. Set
`DEPLOY_IMAGE_REFERENCE` to the short alias below; the helper uses
[crane](https://github.com/google/go-containerregistry/tree/main/cmd/crane) to
verify that alias against `IMAGE_REFERENCE` before deployment. Omit the alias
on a CLI/service version that accepts digest references:

```bash
export PARENT_ID='project-...'
export SUBNET_ID='vpcsubnet-...'
export IMAGE_REFERENCE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb26@sha256:98cd41bcc0a6eed1dcd106a59cc74c58a35e711138ad4ad06d482271da914668'
export DEPLOY_IMAGE_REFERENCE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb26:r0918b'
export AUTH_TOKEN_SECRET='<your-MysteryBox-selector>'

scripts/deploy-endpoint.sh
```

<!-- /factory:cli -->

See [validation results](./VALIDATION.md) for the tested image and GPU checks.

## Troubleshooting

- **Jupyter shows a password prompt** — use the `JUPYTER_PASSWORD` shown in
  the endpoint environment. Change the form's published demo password before
  creation.
  A manual deployment that omits the variable emits a generated value once in
  the endpoint logs.
- **BIR version mismatch at boot** — use `BIOIR_VERSION=0.1.0` with this image.
  Build and validate another image to change the installed release.
- **CUDA initialization fails** — confirm the worker has NVIDIA driver 580 or newer.
- **`RUNNING` but `/readyz` returns `503`** — applies to the optional HTTP
  service while it downloads assets and warms the processor. Check logs; a
  successful response has `{"status":"ready"}`.
- **`401` or `403` calling the endpoint** — send the generated endpoint token
  as `Authorization: Bearer <token>`.
- **Out of memory or slow requests** — keep one worker per GPU, reduce input
  size or sampling steps, then profile on the target platform before scaling.

> When testing is complete, delete the endpoint in the Console so GPU billing
> stops. See [managing endpoints](https://docs.nebius.com/serverless/endpoints/manage).
