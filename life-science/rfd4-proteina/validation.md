# Validation status — 21 October 2026

This contribution is a review draft. It uses vendor images directly and contains
no mirrored images, model weights, custom Dockerfiles or model-serving wrappers.

Checked without starting new GPU work:

- NVIDIA RFD4/OpenFold3 NIM, NVIDIA PyTorch and Alpine curl image manifests and pinned digests.
- All three NIM requests against NVIDIA's published OpenAPI schema.
- Public-package availability and resolution of the pinned Hugging Face
  dependency set with CUDA 13 wheels in an isolated Python 3.12 environment.
- The materialized PD-L1 OpenFold3 request against NVIDIA's published schema;
  target sequence, atom coordinates, query MSAs and absence of a binder template.
- Input provenance, hashes, launch-link parameters and shell syntax.

Run live on 9 November 2026 (eu-north1, `gpu-h100-sxm` / `1gpu-16vcpu-200gb`,
200 GiB disk, no Hugging Face token): the Hugging Face startup-installation job
COMPLETED for the monomer and PD-L1 inputs with the corrected command, and both
runs' CIFs reached the bucket non-empty (monomer 230,369 / 224,664 bytes;
PD-L1 638,840 / 638,861 bytes, 1,569 ATOM records each). The direct NVCR pull
stayed inside the cold-start window in that run.

The NIM endpoint, CPU bucket client and the optional OpenFold3 path have
**not** had live end-to-end acceptance. Results from earlier custom
images are not presented as validation or benchmarks for these configurations.
Signed-in console acceptance is also pending; automated console access received
Cloudflare 403.

The cookbook's existing [NIM guide](https://github.com/nebius/serverless-ai-cookbook/blob/main/inference/nim-endpoint/README.md)
records direct NVCR image pulls exceeding the Serverless cold-start window.
This contribution keeps direct NVIDIA references; it does not use that guide's
registry-mirror workaround. Direct-pull acceptance is a merge prerequisite.

Before merging, confirm readiness and authenticated requests, then check bucket
input/output and requested proposal counts for each example. Check the HF
runtime versions and model revision against images.json. Keep completed jobs'
outputs and remove their compute resources after acceptance.
