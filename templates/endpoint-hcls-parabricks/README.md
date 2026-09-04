# NVIDIA Parabricks DeepVariant API

Parabricks DeepVariant behind the HCLS asynchronous endpoint contract, intended for
large genomics inputs referenced from mounted storage or validated HTTPS URLs.

**Terms:** [NVIDIA AI product terms](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-ai-products/) ·
**Product docs:** [Parabricks](https://docs.nvidia.com/clara/parabricks/latest/)

The Dockerfile extends an existing public, immutable Nebius Parabricks 4.7.0-1 API
image used by the approved reference deployment. Direct NGC rebuild still requires
valid NGC access and acceptance of current NVIDIA terms. Do not assume that public
pull access grants unrestricted redistribution; verify terms for every release target.

```bash
docker build --platform linux/amd64 \
  -f templates/endpoint-hcls-parabricks/Dockerfile \
  -t hcls-parabricks-deepvariant-api:local .
```

NVIDIA recommends two GPUs and at least 24 CPU threads/100 GB RAM for current
Parabricks releases. Nebius Serverless presently exposes one- or eight-H100 presets,
so the bounded demo uses one H100 (`PARABRICKS_GPU_COUNT=1`) and production users
should qualify the eight-GPU preset for their throughput target. The guided chr20
smoke references the official public Google DeepVariant test fixtures by HTTPS URL
and SHA-256, so it works without bucket credentials. Mounted inputs remain supported
for private data. Signed URLs are accepted at execution time but are not persisted in
results or logs.

Results include compressed VCF output, Parabricks log, input hashes, GPU identity,
variant record count, and the common artifact manifest. This is research-only variant
calling, not a diagnosis; validate calls with an appropriate truth set and workflow.

## Private candidate deployment

The live-qualified adapter is intentionally not in the public HCLS registry. It is
stored under the same project in a registry verified to reject anonymous pulls:

```text
cr.eu-north1.nebius.cloud/e00j70hx633t3qcj0f/hcls/parabricks-deepvariant-api:20260904-deb6e34
sha256:8ed6541d80d99bc932020dbb9568449d5a1e743cd37f353b4c66c4ce70c23102
```

Serverless can pull a private Container Registry image from the same project without
embedding registry credentials. Set `PARABRICKS_GPU_COUNT=1`, expose port 8000, use
`gpu-h100-sxm` / `1gpu-16vcpu-200gb`, and enable token authentication. A public deploy
button is withheld until an authorized owner confirms NVIDIA redistribution terms;
recheck the current product version and terms before promotion.

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
