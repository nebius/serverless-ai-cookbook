# NVIDIA Parabricks DeepVariant API

Parabricks DeepVariant behind the HCLS asynchronous endpoint contract, intended for
large genomics inputs referenced from mounted storage or validated HTTPS URLs.

**Terms:** [NVIDIA AI Product Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-ai-product-agreement/) ·
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

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
