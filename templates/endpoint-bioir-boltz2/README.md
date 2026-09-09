---
title: BioNeMo Inference Runtime Boltz-2 Endpoint
category: life-sciences
type: endpoint
runtime: nebius-serverless-ai
frameworks: [bionemo-inference-runtime, pytorch, fastapi]
keywords: [protein-structure-prediction, boltz-2, biomolecular-ai, serverless-endpoints, gpu]
difficulty: advanced
---

# BioNeMo Inference Runtime: Boltz-2

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fbionemo-inference-runtime-boltz2%3A0.1.0&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=false&amp;auth=true&amp;env=BIOIR_RELEASE%3Dlatest"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

BioNeMo Inference Runtime (BioIR) is NVIDIA's Python inference-acceleration library, not a model or a NIM. This one-click template wraps its public Boltz-2 quickstart in a small, token-protected HTTP service on one L40S.

**License:** [BioIR license](https://github.com/NVIDIA-BioNeMo/BioNeMo-Inference-Runtime) · [Boltz-2 MIT license](https://github.com/jwohlwend/boltz)

<!-- /factory:intro -->

Click **Create Endpoint** above, retain authentication, and create the endpoint.
The Nebius-managed public launcher image contains only this FastAPI adapter and
its bootstrapper. Its `entrypoint.sh`—not a notebook—installs the selected
public BioIR GitHub Release wheel from
`NVIDIA-BioNeMo/BioNeMo-Inference-Runtime` at first start. BioIR then retrieves
the public Boltz-2 assets and warms the model. The image contains no NVIDIA
early-access image, wheel, model weights, NGC credential, or Hugging Face
credential.

The published launcher is
`cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/bionemo-inference-runtime-boltz2@sha256:24a1409f8d41ea7e976b967d8c0e309fb6f531a9782f98de9eb285408e54a677`.

The deployment form is prefilled for port `8000`, one L40S, 500 GiB of disk,
and token authentication. Cold start includes Python dependencies, model assets,
and compilation, so wait for `/readyz` rather than treating endpoint `RUNNING`
as model-ready. The L40S is in BioIR's released support matrix; choose a
different compatible platform and preset if that better suits your project.

## What this demonstrates

This is a tutorial for integrating a library, rather than a prepackaged model
endpoint. The adapter follows NVIDIA's [BioIR quickstart](https://docs.nvidia.com/bionemo/inference-runtime/quickstart/):

1. Create `InputRequest`, `Polymer`, and an inline `MSARecord`.
2. Configure `EngineProcessorConfig(model_source="boltz-2")`.
3. Build and warm the `build_processor` pipeline once per GPU worker.
4. Serialize one request at a time, validate its mmCIF output, and return its
   decoded scores.

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

## Call the endpoint

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

## Choose and pin a BioIR release

The template defaults to `BIOIR_RELEASE=latest` so the public launch works
without credentials. For a repeatable environment, set this variable in the
endpoint form to a public GitHub release tag before creating the endpoint, for
example `BIOIR_RELEASE=vX.Y.Z`. The launcher selects the matching CUDA 13.2,
Python 3.12, x86_64 wheel from that release. `BIOIR_WHEEL_URL` is an advanced
override for a specific official release asset.

The package release and the public model assets are separate provenance
decisions. Record the selected release, endpoint image digest, asset revision,
GPU type, and warmup/inference measurements with scientific results. NVIDIA's
[model-weights reference](https://docs.nvidia.com/bionemo/inference-runtime/references/model-weights/)
describes the upstream weight sources and their terms.

## Build or mirror the launcher yourself

The prebuilt launcher is intentionally thin. Build it in your own public
registry if you need a different base-image policy or release process. This
does not copy BioIR or Boltz-2 into the image.

```bash
cd templates/endpoint-bioir-boltz2
export IMAGE_TAG='registry.example.org/your-team/bioir-boltz2-serverless:0.1.0'
scripts/build-image.sh
```

The script prints the pushed digest. Use that immutable reference with the
manual helper below, or replace the prefilled image in the Console form.

<!-- factory:cli -->

## CLI alternative

The Console button is the simplest route because it creates an endpoint token.
For a scripted deployment, first create a MysteryBox secret with an
`AUTH_TOKEN` payload key, then use a public image reference already pinned to a
digest:

```bash
export PARENT_ID='project-...'
export SUBNET_ID='vpcsubnet-...'
export IMAGE_REFERENCE='registry.example.org/your-team/bioir-boltz2-serverless@sha256:<digest>'
export AUTH_TOKEN_SECRET='<your-MysteryBox-selector>'

scripts/deploy-endpoint.sh
```

<!-- /factory:cli -->

## Troubleshooting

- **`RUNNING` but `/readyz` returns `503`** — normal during the first download
  and warmup. Check logs; a successful response has `{"status":"ready"}`.
- **Bootstrap cannot find a release wheel** — set `BIOIR_RELEASE` to the public
  launch tag or set `BIOIR_WHEEL_URL` to an official CUDA 13.2 / CPython 3.12
  / x86_64 release asset.
- **`401` or `403` calling the endpoint** — send the generated endpoint token
  as `Authorization: Bearer <token>`.
- **Out of memory or slow requests** — keep one worker per GPU, reduce input
  size or sampling steps, then profile on the target platform before scaling.

> When testing is complete, delete the endpoint in the Console so GPU billing
> stops. See [managing endpoints](https://docs.nebius.com/serverless/endpoints/manage).
