# AutoDock Vina validation — 2026-09-18

Image: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb23@sha256:f80ba1d50f7bbbd6192f9695a71691bdd37390d3bfc0e6152d9cb0a80ef2f171`.

- Docker build completed for Linux amd64. AutoDock Vina 1.2.7; clean build with unpinned Debian patch-package versions.
- `python -m pytest -q`: 10 tests passed.
- Live Nebius Serverless shape: CPU (`cpu-d3`, `4vcpu-16gb`).
- Anonymous gateway requests returned HTTP 401; authenticated readiness returned HTTP 200.
- REST and MCP runs with exhaustiveness 8 and seed 17 both returned -13.263 kcal/mol best affinity, taking 32.817 and 32.488 seconds, respectively.
- Both result artifacts were downloaded and their SHA-256 checksums verified. MCP-created runs were also retrieved through REST.

The sanitized [test output](./validation/2026-09-18.json) records the runs and artifact hashes.
Reproduce with `scripts/test_endpoint.py "$BASE_URL" --payload '{"exhaustiveness":8,"seed":17}'`
after installing `requirements-client.txt` and setting `HCLS_ENDPOINT_TOKEN`.

## Scope and limitations

These are small deployment smoke tests, not scientific qualification or comparative benchmarks.
This rerun used endpoint-local storage; persistent Object Storage/Shared Filesystem mounts were
not requalified. The button does not attach a volume.

All three deployment links are checked by the URL regression test. Browser validation of the
Console form was blocked by Cloudflare (HTTP 403), so form behavior is not claimed as tested.
CLI 0.12.206 rejected endpoint image references longer than 64 characters in the `vmapp-image`
label. Live tests used the published short `cb23:r0918` alias resolving to the exact digest above;
see the CLI section in the README. Temporary qualification endpoints were deleted after testing.
