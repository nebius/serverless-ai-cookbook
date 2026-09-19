# Integrated client v43 — immutable handoff

Built, pushed and qualified on 19 September 2026. This note does not claim
deployment or natural customer adoption of the new staging helper.

| Identity | Exact value |
| --- | --- |
| Source | `31ea81371b31a06cc9b7366963dcbcc9f72d7453` |
| Image | `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v43-31ea813` |
| Index | `sha256:6b03912b411c32c66bc22bdd1e0962f5c6e168962a5fd8077eae4f1cb0ada554` |
| amd64 | `sha256:60963f8a7837bbebb1b6670ef7fcf616e5cfc29b0432a799f97b4aefbdeefba5` |

Built from an exact Git archive, with official skills pinned to
`292c7e65a46d0c29994d2babfc19da129d16fa62`. Registry digest and local image
revision label were checked. The source moves the existing artifact publisher
to shared persistence, adds explicit seekable-file staging, and documents it in
the general agent instructions/tool description. No provider/model, permissions,
budget, timeout or concurrency setting changed. Healthy v42/v39/Rene endpoints
were not modified by this build.

## Installed and real-storage evidence

- All 14 installed runtime-file hashes match committed source.
- Five installed test groups pass: service/deadline tests, exact ToolSearch,
  clinical no-facts behavior, cross-runtime outcome identity, and four-format
  staging. Tests import installed runtime code, not mounted replacements.
- Five retained clinical report/measurement pairs regenerate byte-for-byte.
  This is deterministic helper reproducibility, not medical completeness.
- Compiled Runs labels remain present. MCP 2.2.0, httpx2 2.12.0, NumPy 2.2.6,
  RDKit 2025.3.6 and h5py 3.13.0 remain the top-level installed versions.
- Installed batch client recovered the original 683-byte result and
  1,988,267-byte zstd bundle in 10.643s; all nine extracted files matched the
  retained dataset. Same-operation resume and nonfinite-safe NumPy export pass.
  No inference, uploads or package installation occurred in that read-only gate.
- The exact candidate persistence module separately passed NPZ/ZIP/HDF5/closed
  SQLite publication on the actual provider bucket mount, followed by independent
  S3 reads/reopening. See [actual storage proof](../20260919-workspace-seekable-staging/README.md).

Protected campaign receipts:

- `workbench-v43-build.json`
- `browser-evidence/workbench-v43-installed/summary.json`, SHA256
  `7f5da1f6eccc0584eeb31e8e0c6609c44d8741dc7e663a3be6bbbdb8db9d94cb`
- `browser-evidence/workbench-v43-fresh-image/summary.json`
- `workspace-staging-v43/independent-verification.json`

Shared helper is installed at `/opt/bionemo/scientific_receipts.py`. Invoke
the scientific Python interpreter with `/opt/bionemo` in its import path, as
the agent guidance states; this is not a globally installed Python package.
Writers must close before publication. A bucket is not an atomic rename/shared
POSIX filesystem or live SQLite/WAL store.

## Deployment and remaining gates

Parent/root owns normal deployment through
`templates/hcls-librechat/demos/deploy-scientist-workbenches.py`; preserve the
original credentials, bucket and exact planner settings. Record the verified
tag-to-digest identity because this provider's full-digest label issue prevents
using that string directly in the create helper. Reconcile exact names before
retrying an uncertain Create. No additional deletion is authorized here.

The [fresh v42 natural robotics study](../20260919-robotics-natural-v42/README.md)
completed delivery after two ordinary continuations and four verified browser
downloads. Its storage failure, report-method errors and physical-fidelity
limitations remain. Those outputs are not relabeled as v43 results. A short
natural CPU-only file-writing task can test adoption of this new helper without
repeating completed GPU science; that is still a separate deployment gate.
