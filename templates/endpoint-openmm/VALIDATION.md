# OpenMM validation — 2026-09-18

Image: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb24@sha256:4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184`.

- Docker build completed for Linux amd64. OpenMM 8.6.1 with its CUDA 12 plugin installed at build time.
- `python -m pytest -q`: 8 tests passed.
- Live Nebius Serverless shape: L40S (`gpu-l40s-a`, `1gpu-8vcpu-32gb`).
- Anonymous gateway requests returned HTTP 401; authenticated readiness returned HTTP 200.
- A real CUDA integration step gated readiness. REST and MCP each completed a 512-particle, 1,000-step LangevinMiddle simulation in mixed precision. Reported integration throughput was 10,810.157 and 10,910.102 ns/day; energies agreed between the two runs.
- Both result artifacts were downloaded and their SHA-256 checksums verified. MCP-created runs were also retrieved through REST.

The sanitized [test output](./validation/2026-09-18.json) records the runs and artifact hashes.
Reproduce with `scripts/test_endpoint.py "$BASE_URL" --payload '{"steps":1000}'`
after installing `requirements-client.txt` and setting `HCLS_ENDPOINT_TOKEN`.

## Scope and limitations

These are small deployment smoke tests, not scientific qualification or comparative benchmarks.
This rerun used endpoint-local storage; persistent Object Storage/Shared Filesystem mounts were
not requalified. The button does not attach a volume.

All three deployment links are checked by the URL regression test. Browser validation of the
Console form was blocked by Cloudflare (HTTP 403), so form behavior is not claimed as tested.
CLI 0.12.206 rejected endpoint image references longer than 64 characters in the `vmapp-image`
label. Live tests used the published short `cb24:r0918` alias resolving to the exact digest above;
see the CLI section in the README. Temporary qualification endpoints were deleted after testing.
