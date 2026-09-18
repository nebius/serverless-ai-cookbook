# Parabricks validation — 2026-09-18

Private qualification image:
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/cb25@sha256:2f9e405ac5eda786fa28124af4acaa82eb72865c52ba5be98f5adcfe7894d412`.
This is not a public deployment image. The README describes building and publishing
the NVIDIA-licensed wrapper in the user's own registry.

- Linux amd64 Docker build passed using a private mirror of the exact upstream base:
  `nvcr.io/nvidia/clara/clara-parabricks:4.7.1-1@sha256:a748d86cbb850641a1e0afae6de2e7422f1375e4a0cce08a5c2cead9fa302237`.
  The mirrored OCI manifest digest matched upstream.
- `python -m pytest -q`: 11 tests passed, including the one-GPU default and
  direct execution of the baked tools. Ruff passed.
- Live H100 endpoint: Parabricks 4.7.1-1, one GPU required and detected.
- Anonymous gateway access returned HTTP 401; authenticated readiness returned 200.
- Independent REST and MCP runs of the public, nonclinical chr20 smoke each produced
  78 variant records. Wall times were 13.030 and 12.182 seconds.
- Both result artifacts were downloaded and SHA-256 verified. The MCP-created run
  was also visible through REST. See the [sanitized results](./validation/2026-09-18.json).

Reproduce using the capabilities-provided `deepvariant-chr20-smoke` payload and
`scripts/test_endpoint.py` as described in the README.

## Scope and limitations

These are deployment smoke tests, not scientific or clinical qualification.
The rerun used endpoint-local storage; Object Storage/Shared Filesystem persistence
was not requalified. No PHI or clinical genomes were used.

All three deployment links are covered by the URL test. They intentionally contain
an example image name that must be replaced after building. Browser inspection of the
Console form was blocked by Cloudflare (HTTP 403), so form behavior is not claimed
as tested. CLI 0.12.206 rejected image references over 64 characters in its VM label;
the live endpoint used the private short alias `cb25:r0918`, verified against the
digest above. Temporary compute resources and the temporary registry credential
secret were deleted after testing.
