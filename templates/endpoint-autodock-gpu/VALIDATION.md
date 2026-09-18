# AutoDock-GPU validation — 2026-09-18

Image: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb22@sha256:5c81e5455f526e19ec0dd6a34cf3dad51816898ebef2d7797e181e7879760f71`.

- Docker build completed for Linux amd64. AutoDock-GPU v1.6 compiled from pinned source using official Ubuntu repositories.
- `python -m pytest -q`: 9 tests passed.
- Live Nebius Serverless shape: H100 (`gpu-h100-sxm`, `1gpu-16vcpu-200gb`), driver 580.173.02.
- Anonymous gateway requests returned HTTP 401; authenticated readiness returned HTTP 200.
- The 1STP CUDA startup probe passed. REST and MCP each completed five runs with 250,000 maximum evaluations and seed 17; best scores were -8.17 and -8.26 kcal/mol (AutoDock4 semantics). GPU stochastic results need not be bit-identical.
- Both result artifacts were downloaded and their SHA-256 checksums verified. MCP-created runs were also retrieved through REST.

The sanitized [test output](./validation/2026-09-18.json) records the runs and artifact hashes.
Reproduce with `scripts/test_endpoint.py "$BASE_URL" --payload '{"nrun":5,"max_evaluations":250000,"seed":17}'`
after installing `requirements-client.txt` and setting `HCLS_ENDPOINT_TOKEN`.

## Scope and limitations

These are small deployment smoke tests, not scientific qualification or comparative benchmarks.
This rerun used endpoint-local storage; persistent Object Storage/Shared Filesystem mounts were
not requalified. The button does not attach a volume.

All three deployment links are checked by the URL regression test. Browser validation of the
Console form was blocked by Cloudflare (HTTP 403), so form behavior is not claimed as tested.
CLI 0.12.206 rejected endpoint image references longer than 64 characters in the `vmapp-image`
label. Live tests used the published short `cb22:r0918` alias resolving to the exact digest above;
see the CLI section in the README. Temporary qualification endpoints were deleted after testing.
