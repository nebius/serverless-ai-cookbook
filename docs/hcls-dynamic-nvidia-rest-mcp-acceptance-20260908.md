# HCLS dynamic NVIDIA REST/MCP acceptance — 2026-09-08

## Outcome

OpenMM and NVIDIA Parabricks now use lean public API wrappers that authenticate to
NGC at endpoint startup, resolve a selectable official runtime tag, record its
immutable digest, expose one shared REST/MCP run manager, and persist below
`/mnt/hcls` on either Serverless storage type. The final accepted endpoints use
regular capacity, integrated Serverless token authentication, and Object Storage.

AutoDock-GPU implements the same selection and probe path, but is not released as a
dynamic customer endpoint because NVIDIA currently publishes only an incompatible
2020 runtime. AutoDock Vina remains the separate CPU REST service.

Source commit: `41e8fde7b94de1f48a59b4166b886aac667439c8`

## Released wrappers and official runtimes

| Service | Public wrapper | Wrapper digest | Selected official runtime | Runtime digest |
| --- | --- | --- | --- | --- |
| OpenMM | `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/openmm-md-api:20260908-dynamic-v3` | `sha256:7d73bc0d6270e7bf2fcf04a6ee7544dc8a6527b7383d2e77408cb8d3f476d416` | `nvcr.io/nvidia/openmm:8.1.1` | `sha256:f4943aef3df103f05d0e502ea0711fce4a32a92366585b0f5bd7a5b01c9b5b59` |
| Parabricks | `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/parabricks-deepvariant-api:20260908-dynamic-v3` | `sha256:e76f3185a68c99bf979cecfc7be476e1debfe60c842814cbb104a00157eb19d0` | `nvcr.io/nvidia/clara/clara-parabricks:4.7.1-1` | `sha256:a748d86cbb850641a1e0afae6de2e7422f1375e4a0cce08a5c2cead9fa302237` |

Both wrapper digests were resolved with an empty Docker configuration, confirming
anonymous pull access. The NVIDIA runtimes are never embedded in the wrappers; the
endpoint retrieves them with the secret `NGC_API_KEY` and caches them by digest on
its boot disk. `latest` selects the highest stable tag that passes the real GPU
startup probe. An exact tag never silently falls back.

## Final endpoints left running

| Service | Endpoint | Managed HTTPS URL | Compute | Disk | Storage |
| --- | --- | --- | --- | --- | --- |
| OpenMM | `aiendpoint-e00gdgya1eex19zr7q` | `https://port8000-ezn2jvyf2jyfwfh.tunnel.applications.eu-north1.nebius.cloud` | regular `gpu-l40s-a` / `1gpu-8vcpu-32gb` | 100 GiB | `s3://parabricks-test` read-write at `/mnt/hcls` |
| Parabricks | `aiendpoint-e00f1zzqbwm95eftnp` | `https://port8000-r4e7df065b3b2zx.tunnel.applications.eu-north1.nebius.cloud` | regular `gpu-h100-sxm` / `1gpu-16vcpu-200gb` | 500 GiB | `s3://parabricks-test` read-write at `/mnt/hcls` |

Both endpoints use the same existing MysteryBox-backed Serverless token as the
accepted GROMACS endpoint. The value and selectors are intentionally absent from
source, URLs, logs, and this evidence. The only NVIDIA secret environment variable
is `NGC_API_KEY`; `OPENMM_VERSION=latest` and `PARABRICKS_VERSION=latest` are plain
environment variables.

## Live acceptance evidence

Unauthenticated `/healthz` requests returned 401/403 before every authenticated test.
MCP used Streamable HTTP at `/mcp`, protocol `2025-11-25`, and the same bearer token
as REST. MCP-created runs were fetched and their artifacts downloaded through REST.

### OpenMM

- Runtime probe: OpenMM `8.1.1`; `Reference`, `CPU`, and `CUDA` platforms; one real
  CUDA integration step passed on L40S.
- Input: 512-particle periodic Lennard-Jones argon, 1,000 LangevinMiddle steps,
  mixed precision, seed 17.
- REST run `983863795b9541918b955c00f077d259`: 10,837.810 synthetic ns/day;
  `result.json` SHA-256 `8fe4acde30431fc572edb62bb154bc8516514689e7224976f9d9e9f83e8c5fe0`.
- MCP run `7a58cda2babd4a9da5be16e6a8e45057`: 10,820.829 synthetic ns/day;
  REST-verified `result.json` SHA-256
  `bfa9c3d512d82ddb9108b7bc2603d0166e8770215401bd795872fa0f68dcae5a`.
- Direct S3 inspection found nine objects and 9,472 bytes below each run prefix.

The ns/day values validate execution and plumbing only; this synthetic system is not
a biological or scientific benchmark.

### Parabricks DeepVariant

- Runtime probe: `nvidia-smi` enumerated `NVIDIA H100 80GB HBM3` from inside the
  selected NGC filesystem and `pbrun` reported version `4.7.1-1`.
- Input: the documented Google DeepVariant chr20 quickstart fixture set with all four
  input SHA-256 values enforced; interval `chr20:10000000-10010000`.
- REST run `7809979afad841a0b6e09d0e4156fbae`: 78 variant records;
  `result.json` SHA-256 `5103c4573ed9ebb36fc5e773a4c82034aa976cda733b480998b3099aab0d84a8`.
- MCP run `a6a1c83734da4a9d9f9580455a62011a`: 78 variant records;
  REST-verified `result.json` SHA-256
  `5cf1bf8563ad25cde00daa231a9b04b630b207323d673214a197ffde3a00d521`.
- Direct S3 inspection found 14 objects and about 72.2 MB below each run prefix,
  including normalized input, VCF output, logs, hashes, and immutable status records.

Variant calls are research outputs and require independent workflow validation.

## Build and static gates

- Shared runtime/API suite: 17 tests passed.
- Python compilation, `bash -n`, ShellCheck, Hadolint, and `git diff --check` passed.
- Trivy vulnerability plus secret scans found no fixed High/Critical findings and no
  embedded secrets in either release wrapper.
- SPDX JSON SBOMs were generated and retained for handoff at
  `/tmp/hcls-sbom-20260908/openmm-md-api-20260908-dynamic-v3.spdx.json` and
  `/tmp/hcls-sbom-20260908/parabricks-deepvariant-api-20260908-dynamic-v3.spdx.json`.

## AutoDock-GPU upstream blocker

NGC currently exposes only `nvcr.io/hpc/autodock:2020.06`, digest
`sha256:6170944542063c7417343bec5e4001239e4ce113c2faf7f5824cb20a08373d9c`.
The official executable reached a real 1STP docking invocation on H100 and aborted at
`performdocking.cpp:169`; the image inspection found no corresponding build source.
The failed dynamic probe was deleted. The previously qualified H100 source-build
fallback remains available but is explicitly not described as the dynamic NVIDIA
runtime pattern.

## Customer verification

The OpenMM and Parabricks template READMEs contain their complete Console links,
required environment and secret fields, Object Storage profile, Shared Filesystem
alternative, and CLI deploy helper. To verify a running endpoint, use the common
client with its engine-specific capabilities payload:

```bash
python3 -m venv .venv-hcls-client
.venv-hcls-client/bin/pip install -r templates/hcls-common/requirements-client.txt
export HCLS_ENDPOINT_TOKEN='<Serverless token>'
.venv-hcls-client/bin/python templates/hcls-common/scripts/test_endpoint.py \
  'https://<managed-endpoint>' --payload '<engine-specific JSON object>'
```

The first OpenMM start materializes a 24.1 GB OCI root filesystem and can remain in
`STARTING` for roughly 15 minutes. Do not interpret that quiet transfer as readiness;
the endpoint serves only after the real CUDA probe succeeds.
