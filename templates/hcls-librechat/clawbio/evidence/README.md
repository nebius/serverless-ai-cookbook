# ClawBio source/image evidence — 2026-09-20

This directory records local candidate-image tests, not a production rollout.
Implementation source: `925e3b9de94de31feb0b950d7aebfbab2d66fe0c`.
Base workbench: `1250a00` (v61 source plus existing handover documentation).
ClawBio: `4848cc280c446093b1364a2445db3137d455cc17`.

Local candidate tag: `scientific-ai-librechat:clawbio-20260920-925e3b9`.
Image ID: `sha256:4479dfa47819181d46e961c96c2cefc062ce82bc32d84d62b1273ae7e451b7f8`.
Platform: `linux/amd64`; local uncompressed image size: 6,104,356,812 bytes.
No registry upload or change to running LibreChat instances was performed.

## Results

- **62 installed-image integration checks passed**, with network disabled and
  a 2-CPU/4-GiB limit. Includes genuine file inputs, independent FASTA/ABF expected
  results, known-direction RNA-seq contrasts, source/integration hashes, error
  propagation and actual MCP execute/read job recovery. See `image-integration.xml`.
- LibreChat's actual deployment-skill loader discovered **81 total skills**,
  including all **48 ClawBio selections** and their upstream method references.
  Existing gateway, clinical and Nebius skills remain present. No database,
  provider or live-user calls were required. See `skill-loader.json`.
- **44 of 45 local examples executed in the exact image**, with a 4-CPU/8-GiB
  limit. Includes actual public eQTL/GWAS retrieval, PLINK/1000G LD calculation
  and LD-colored regional rendering. Each result, duration, warning and output
  hash is retained in `image-probes/report.json`. This proves execution of those
  examples, not scientific validity for arbitrary datasets.
- Article retrieval has successful/failed-download and decompressed-path/hash
  adapter tests, but no live end-to-end retrieval claim. It remains explicitly
  `not-runtime-qualified`.
- The three hosted-App adaptations have **zero model calls** in this change.
  Their live schemas/grants and real LibreChat user journeys still need testing
  in a later authorized rollout.
- Source tests passed (61 before the additional removed-flag regression).
  The per-skill report embedded in the image is the conservative **host** report:
  it does not mark the host's missing PLINK as an image success. Installed-image
  evidence above supersedes that host-only observation without rewriting history.

## Upstream regression coverage and retained failures

The initial nine upstream offline suites ran 233 tests: 227 passed, six skipped
for optional SomaData. After installing SomaData and limiting RNA-seq workers,
all **42 affinity-proteomics/RNA-seq tests passed**, including those six formerly
skipped tests. The Scrublet-specific regression also passed. See the JUnit files.

The full scRNA suite subsequently completed: **33 passed, three failed**. These
failures are retained in `scrna-full-regression.xml`, not relabeled as passes:

1. A CellTypist test expects a missing-model error after importing CellTypist;
   this bundle explicitly does not install that optional annotation runtime, so
   the actual error correctly reports the missing dependency instead.
2. A test imports the excluded Bio-Orchestrator, which intentionally is not
   bundled because the existing Scientific AI agent owns orchestration.
3. The upstream generic dispatcher silently accepts a removed `--de-groupby`
   option. Our runner bypasses that dispatcher; an added installed-image test
   confirms the native CLI rejects the option instead of claiming it ran.

The full upstream suite is therefore **not** claimed as passing. The included
workflow examples and our explicit native-interface checks pass.

## Problems fixed during packaging

- Missing OTEL/RO-Crate dependencies and version mismatch.
- Generic dispatcher rejecting valid RNA-seq input arguments.
- Incorrect libcurl CA path for native tabix retrieval, with TLS verification
  retained.
- Interactive article download selection and false success from report-only or
  partial downloads; adapted headless arguments and verified artifact receipts.
- Initial image `clawbio-20260920-d6c13bd` exhausted its 8-GiB test allowance by
  spawning PyDESeq2 workers for host CPUs. That disposable test container was
  stopped. **Do not use that superseded image.** Explicit worker limits fix this;
  the final image passes the stricter 2-CPU/4-GiB check.
- Missing Scrublet/SomaData and Annoy build headers. Build tools are isolated,
  dependencies hash-locked, and Annoy's host-specific `-march=native` removed.

No test containers remain running. Existing deployments, account keys, buckets,
model Apps and the parent thread's work were not changed.

## Original feature-branch handoff (historical)

Repository: `rene-tech/serverless-ai-cookbook`.
Isolated detached worktree: `/home/tux/worktrees/scientific-ai-clawbio-20260920`.
No named branch, remote push or merge into an active worktree was made.
Implementation commits (in order): `d6c13bd`, `04a5e3e`, `925e3b9`, based on
`1250a00`; the subsequent evidence/test-only commit does not change image runtime.

Review `../selection.json` for every upstream skill's inclusion/exclusion and
`../README.md` for reproducible preparation/build steps. Integrate these commits
with the then-current workbench source before any later release. A customer
rollout still needs exact-image, per-user LibreChat and bucket-export checks;
none was requested or performed here.

## Main integration verification — 2026-09-20

Merged the feature tip `db8639f` with main `ff60255`, preserving main's
canonical public skills bundle and deferred endpoint rollout. The catalog now
lives only in `skills/scientific-ai`; its source bundle version is
`2026.09.20.2`. The full image adds 48 ClawBio extensions to the 31 public skills,
without restoring the private Nebius skill dependency. The Docker build context
includes the canonical bundle. No release archive or deployment default changed.

Local merged candidate: `scientific-ai-librechat:clawbio-main-merge-20260920`.
Image ID: `sha256:4c202735913718c9d604b75164c2d545892fa08e8ae3ecd30e7661204103fe87`.
Built from the merged runtime source; image revision label identifies the two
inputs as `merge-ff60255-db8639f`. This receipt was added after the local build.

- Public bundle/clinical helper tests: **114 passed, 31 subtests passed**.
- ClawBio source integration: **62 passed**.
- ClawBio integration in the merged image: **62 passed**, network disabled,
  2 CPUs and 4 GiB memory.
- Workbench, scientific batch client and clinical skill regressions in the merged
  image: **45 passed**. The host Python lacked `httpx2`; these checks were rerun
  using the image's existing scientific-client environment, not skipped.
- Both actual LibreChat loader checks passed: **79 skills**, including all
  **48 ClawBio** additions, **65 supporting resources** and **57 core file hashes**.
  The older 81-skill receipt above belongs only to the pre-merge candidate.
- Canonical bundle hash verification, skill frontmatter validation and
  `git diff --check` passed.

These are merge/build regression checks, not additional scientific qualification.
The upstream failures and hosted-App/customer-journey limitations above still
apply. The merged candidate remains local: no registry push, live inference,
tenant changes or running-instance deployment was performed.
