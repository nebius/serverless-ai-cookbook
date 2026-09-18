# GROMACS validation — 2026-09-18

Image: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb21@sha256:c291e308591382e2114e7a43146b4e4af4e4c47326397f935059c5094d4932ba`.

- Docker build completed for Linux amd64. GROMACS 2025.3 compiled from checksum-verified source with CUDA.
- `python -m pytest -q`: 6 tests passed.
- Live Nebius Serverless shape: L40S (`gpu-l40s-a`, `1gpu-8vcpu-32gb`).
- Anonymous gateway requests returned HTTP 401; authenticated readiness returned HTTP 200.
- The startup CUDA probe passed. Two independent 1,000-step argon runs with `gpu_mode=gpu` succeeded through REST and MCP; reported 3,238.523 and 3,151.637 ns/day, respectively.
- Both result artifacts were downloaded and their SHA-256 checksums verified. MCP-created runs were also retrieved through REST.

The sanitized [test output](./validation/2026-09-18.json) records the runs and artifact hashes.
Reproduce with `scripts/test_endpoint.py "$BASE_URL" --steps 1000 --gpu-mode gpu`
after installing `requirements-client.txt` and setting `HCLS_ENDPOINT_TOKEN`.

## Scope and limitations

These are small deployment smoke tests, not scientific qualification or comparative benchmarks.
This rerun used endpoint-local storage; persistent Object Storage/Shared Filesystem mounts were
not requalified. The button does not attach a volume.

All three deployment links are checked by the URL regression test. Browser validation of the
Console form was blocked by Cloudflare (HTTP 403), so form behavior is not claimed as tested.
CLI 0.12.206 rejected endpoint image references longer than 64 characters in the `vmapp-image`
label. Live tests used the published short `cb21:r0918` alias resolving to the exact digest above;
see the CLI section in the README. Temporary qualification endpoints were deleted after testing.
