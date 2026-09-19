# Integrated v58: reporting and accepted-study replay

This is an immutable built-and-tested candidate, not a completed customer rollout.
Each user retains a dedicated LibreChat instance; a tenant bucket may be shared.
Backend release 190 remains deployed and unchanged.

The subsequent [customer-path result](customer-path.md) records four completed
studies, two reporting/narrative failures, the Cosmos interpretation limits and
six provider-blocked user deployments. It supersedes the preparation-only state
below, not the immutable build/local-test identities.

| Identity | Value |
| --- | --- |
| Source | `43957f6fa8a9bc023c193bc7a712adb94a0dfb92` |
| Image | `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v58-43957f6` |
| Index | `sha256:e1ad4357569e3565dd9af00164ca7c2e48ca4a4924d26aada2732391eccf7386` |
| amd64 runtime | `sha256:5b0f5ec91d451eafbf532fbe708a296ac35a4230de7ba6d01b31a825c233cc64` |

## Changes and original failures

- [Accepted-study replay](../20260919-admission-replay/README.md) returns the
  original saved admission while its worker holds the phase lock. It neither
  starts duplicate work nor tells the client a successful admission was rejected.
- [Structure confidence](../20260919-structure-confidence/README.md) retains
  native values only with exact structure/artifact bytes and a unique sample.
  Geometry, native scales and original files remain unchanged.
- [Completed MindEval summaries](../20260919-completed-study-summary/README.md)
  publish and display stored overall scores with exact profile/model/run IDs.
  Missing values remain unavailable; the chat is not a numerical authority.

All six provisioned v57 studies completed with independently checked downloads.
01, 05 and 07 passed their scientific/delivery checks; 04 omitted confidence,
08 incorrectly claimed no admission, and 09 misquoted a saved score in chat.
Those defects remain in the original records. Four other v57 users never
received instances because Serverless creation repeatedly returned Internal.
No complete ten-user or clean unchanged-release cohort is claimed.

## Exact-image evidence

- All 25 selected installed runtime files match the frozen source.
- 295 domain tests pass, retaining all 198 previous case identities and adding
  replay, confidence and saved-summary regressions. No domain test is skipped.
- Ten receipt/publication-lock tests and eleven real SDK integration cases pass.
- Seven CPU studies produce 41 nonempty independently verified files.
- Four React tests exercise candidate source with installed packages. A separate
  check confirms the summary branch in the final compiled bundle. Neither is
  a substitute for a fresh live Runs UI test.
- The exact retained 04 confidence replay is read-only and preserves geometry.
  Test containers have no network; no new model calls or runtime overlays occur.

Private installed receipt: `U/workbench-v58-installed.vyut_lkd/acceptance.json`,
SHA256 `cedfac3c85863dec40ab89d77ee67f3e338fa6b29a161062506a3a61f436db2f`.
U is the protected scientific-unattended-20260919 handoff directory.

The initial OCI export lacked the existing attestation wrapper and was retained
as `workbench-v58-runtime-only.*`, never published. Re-exporting cached layers
with the existing provenance setting preserved the exact runtime digest. The
published index, runtime and source label were read back and verified.

## State preservation and remaining work

Exact-image local migration preserves 49 collections, 81 documents, 334 index
definitions, two application-state files, eight seeded agent identities, and
the existing conversation/messages. Original-password login succeeds before and
after restart; post-login state matches exactly. The test container is stopped
and its data retained. Empty custom-agent/upload categories are not positive
coverage. Receipt `U/rene-replacement/v58-local-acceptance.json`, SHA256
`0d272f68c59f2446447135a78f3dec4e72ada8dddaeb55fade1f54517828de60`.

Rene's actual endpoint is unchanged. Fresh state capture and controlled cloud
cutover follow qualified customer-path runs; local replay is not cloud migration.
The v58/r10 ten-user protocol changes only output directories, not prompts,
scientific parameters, seeds, concurrency or token/retry/timeout budgets.
Superseded test previews are being archived before any scoped replacement.
Serverless Internal failures are reported to Rene with trace IDs; observed
quota headroom is not evidence of their cause, and no limits were raised.
