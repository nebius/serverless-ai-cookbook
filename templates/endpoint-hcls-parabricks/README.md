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

Deploy on a qualified 2-GPU NVIDIA shape with at least 24 CPU threads and 100 GB RAM,
matching NVIDIA's current recommendation, and mount the approved input bucket. The guided
chr20 smoke references four public/nonclinical fixtures by basename and SHA-256. A
remote source can instead provide `filename`, public `https` URL, and mandatory
SHA-256. Signed URLs are accepted at execution time but are not persisted in results
or logs.

Results include compressed VCF output, Parabricks log, input hashes, GPU identity,
variant record count, and the common artifact manifest. This is research-only variant
calling, not a diagnosis; validate calls with an appropriate truth set and workflow.

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
