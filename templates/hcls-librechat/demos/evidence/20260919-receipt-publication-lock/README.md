# Dedicated-owner receipt publication

Scope: source-level availability repair, not a new admission/retry policy or a
customer-ready claim. The original natural v52 failures remain unchanged.

## Incident and reproduction

At 2026-09-19 17:16:17.475838 UTC a LibreChat Study-detail GET returned HTTP 503
after its observer child exited. A separate GET subsequently returned 200/running.
This was the client route, not evidence of a platform MCP failure. Its original
child stderr was discarded; therefore the exact incident cause is **unproven**.
The retained 225 journal records, plan and canonical receipt all later parsed.

Exact v52 source `e4005cea9e8dd4429064104a53861e8a877016a9` has a reproducible
publication race: a final-name journal becomes visible before its JSON write
finishes; an independent observer selects it and fails parsing. The same race
affects mutable non-journal health records. Four deterministic inter-process
regressions fail against that original source and pass with this repair.

## Repair and invariants

`scientific_receipts.save/load` now share a short, local, per-path flock.
Save holds it exclusively across journal sequencing, full journal publication,
canonical publication and existing readback checks. Load holds it shared across
newest-record selection and parsing. Serialization occurs before acquiring the
write lock. The lock has a distinct namespace from the long-running operation
lock, so observing a running stage does not wait for that stage to finish.

This uses the approved **one writer instance per user** architecture. The
predecessor must be stopped before replacement. API, supervisor and observer
must share UID/local lock root; this is not distributed locking, bucket atomic
rename, or support for overlapping instances. No bucket lock files, new journal
format, commit markers, old-snapshot fallback, longer timeout or retry were added.

Process death releases the local lock. An incomplete latest journal still fails
closed and is never replaced with an older prepared state. A complete journal
still recovers an interrupted canonical write. Legacy canonical-only receipts
retain their existing behavior. Direct readers bypassing `load` are not covered
by this synchronization contract.

## Evidence

- 138 focused tests passed in 6.75s: receipt storage/publication, native and upload
  clients, batch client/preflight, workflow/draft and whole Study tests.
- Inter-process cases pause actual partial journal/canonical writes, block an
  observer until publication finishes, protect the complete read rather than
  only filename selection, isolate unrelated receipt paths, and kill writers.
- The actual native-client persistence order is tested with simulated external
  admission and process death before the call, after admission before response,
  and during accepted-journal publication. Resume opens no network session and
  never resubmits; original evidence is preserved.
- The exact installed v53 supervisor was probed locally with networking disabled
  and an empty synthetic registry. Its actual receipt worker, a Node API-process
  stand-in, and the inherited Python observer used UID 0 and the same
  `/tmp/scientific-receipt-locks-0` root. This is not a live-endpoint observation;
  v52 owners were already entering authorized retirement. Installed supervisor,
  entrypoint, service and receipt-module hashes are retained.
- Ruff (Python 3.12 target) and `git diff --check` pass. Existing non-POSIX
  chmod/rename prohibition and legacy/corrupt receipt tests remain unchanged.

Protected evidence: `receipt-publication-lock-r1/{receipt.json,candidate-tests.xml,
original-reproduction.xml,installed-owner.json}` in the unattended campaign.
Aggregate receipt SHA256:
`7d3c3ab5d3457413fa686521d1ec21172bad90e69d3c0b5b6054c021616993b3`.
Original source/incident diagnosis SHA256:
`7648ca09f01fd6522803747ae2e4060a667dd86e8bf1091e5fe9acc9d4590898`.

The workbench skill requires an exact-image/client acceptance after this source
change. v53 installed gates qualify only their frozen source; they do not qualify
the forthcoming image carrying this fix. No cloud mutation or inference was
performed for this repair. Companion observer diagnostic commit `07cc42a` exposes
bounded static failure codes, not raw stderr, and adds no fallback semantics.
