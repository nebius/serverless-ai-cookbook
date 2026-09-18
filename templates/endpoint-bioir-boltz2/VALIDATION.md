# BioIR validation — 2026-09-18

Qualified image: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb26@sha256:98cd41bcc0a6eed1dcd106a59cc74c58a35e711138ad4ad06d482271da914668`.

## Build and local checks

- Linux amd64 Docker build passed with public `bionemo-ir==0.1.0` baked in.
- Base image, direct requirements, and the full Python dependency lock are pinned.
- `pip check`, non-root cache writes, notebook schema validation, Ruff, and shell syntax checks passed.
- `BIOIR_TEST_IMAGE=cookbook-review/bioir:20260918-r2 python -m pytest -q`: **7 passed**.
  Without `BIOIR_TEST_IMAGE`, the Docker integration test is skipped.
- Local Jupyter: anonymous and wrong-password notebook access denied; the correct
  password opened the bundled notebook.
- All three catalog/template links select this same digest, port 8888, the
  notebook command, and Jupyter password authentication (no bearer-token setting).
- Anonymous registry manifest reads confirmed that the pinned image is public.

## Live L40S checks

Both checks used one L40S, driver **580.173.02**, PyTorch **2.11.0+cu130**, and CUDA **13.0**.
They started from cold disks without NGC or Hugging Face credentials.

| Check | Result |
| --- | --- |
| All bundled notebook cells, executed with nbclient in a real Jupyter kernel | Passed |
| Cold notebook execution, including asset download and initialization | 165.91 seconds |
| Notebook model inference | 6.062 seconds |
| Notebook output | 78,821-byte mmCIF and five populated score fields |
| HTTP cold initialization and warmup | 157.68 seconds |
| Anonymous / authenticated HTTP health | 401 / 200 |
| Authenticated readiness / fold request | 200 / 200 |
| HTTP smoke inference / total request time | 2.843 / 2.983 seconds |
| Independent follow-up structure parse | One model, one chain, 95 residues, 787 atoms |

The independent follow-up used Gemmi to parse the returned mmCIF, confirmed the
residue sequence exactly matched the request, checked every coordinate was finite,
and recorded the CIF SHA-256. See [sanitized evidence](./validation/2026-09-18.json).

These runs caught and verified fixes for two issues beyond dependency pinning:
Jupyter's active event loop conflicted with the synchronous processor, and BioIR's
checkpoint cache needed a writable parent directory for UID 10001. Regression tests
cover both. The inline-MSA newline encoding and dictionary-style request ID access
are also corrected.

To rerun the notebook on a local NVIDIA GPU host:

```bash
export IMAGE_REFERENCE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb26@sha256:98cd41bcc0a6eed1dcd106a59cc74c58a35e711138ad4ad06d482271da914668'
docker run --rm --gpus all "$IMAGE_REFERENCE" \
  jupyter nbconvert --to notebook --execute \
  /workspace/notebooks/bir_boltz2_tutorial.ipynb \
  --output bioir-executed --output-dir /tmp \
  --ExecutePreprocessor.timeout=1800
```

For the deployed HTTP path, run `scripts/smoke-test.sh` with `ENDPOINT_URL`
and `AUTH_TOKEN` set as described in the README.

## Scope and limitations

These checks establish deployment and output consistency, not scientific accuracy.
The query-only MSA is a tutorial fixture. Public model assets are downloaded separately;
observed repository revisions are recorded in the JSON evidence. Timings include this
specific hardware/software combination and are not general benchmark claims.

The notebook job accepted the digest directly. Endpoint creation with CLI 0.12.206
rejected references longer than 64 characters in a VM label, so the HTTP endpoint
used `cb26:r0918b`, verified against the qualified digest. The README helper
verifies this mapping before deployment. Cloudflare returned HTTP 403 when the actual
Console create link was opened in a browser; Console form behavior is not claimed as
tested. No persistent storage mount was qualified.

Temporary GPU resources, the local notebook container, and the browser session were
removed after qualification. No existing user workloads were changed.
