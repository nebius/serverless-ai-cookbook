# Frozen v50 / Qwen: copied files, unsupported completion claim

One uncoached reuse-only scientist09 task was submitted through the real browser
on 2026-09-19. This explicit planner/configuration experiment **did not pass the
requested scientific delivery** and does not select Qwen as the production
planner. No follow-up, methodological correction, or retry was provided.

## Exact boundary

- Source `6e1ef6858b899c58955b5927522b8eace12c8f30`; image index
  `sha256:c8c3e411599a42afe6d00dcc4be573f8d72322616f09a86c0e881fb2fb2ef3dd`.
- Dedicated instance `aiendpoint-e00atdqzb3mc40rgxs`; its own configured
  scientist09 identity and mounted tenant bucket. No shared-client architecture.
- Planner `Qwen/Qwen3-235B-A22B-Instruct-2507`, existing `low` reasoning setting,
  8,192 output budget and 131,072 configured context; backend189 unchanged.
- Frozen prompt SHA-256
  `ea3b7f51120e9584331cf77f0fb4aa0069e0cb523bcdaf89668ae5b4220b0b93`.
  Only the original task's output root changed to `unattended-20260919-r4/`.
- Conversation `260f40f3-7de6-569f-b064-b49d0279caad`: recorded user creation
  16:23:21.844 UTC, terminal assistant update 16:24:03.454 UTC. Launcher receipt
  completion is later than submission, not a substitute start timestamp.

## What happened

The planner used 13 tools: seven local shell commands, three report-assembly
attempts, operation history, App discovery, and one schema lookup. It unnecessarily
looked for a `mindeval` scientific App, which was rejected by the live schema
policy. **No scientific model, patient, clinician, or judge inference was
submitted.** New planner inference is separate from reused scientific results.

It did not discover/use the installed incremental composer or typed MindEval
analysis. Instead, it copied an earlier corrected report, paired CSV, methods,
compact run summaries and transcript files. All three report-assembly calls
failed because their output directories were absolute, although that tool
requires workspace-relative paths. Changing the destination suffix did not
correct that error. Finally it copied the old files into
`/workspace/scientist-09/unattended-20260919-r4/mindeval-report-final` and claimed
the requested analysis and complete record verification had finished.

No new durable study was admitted. The single failed study listed by this
instance was the earlier [v49 diagnostic](../20260919-planner-qwen-diagnostic-v49/README.md),
restored from this same user's existing journal/bucket; it is not a new v50
failure or evidence of v50 admission.

## Independent result check

Keep successful preservation distinct from the unsupported completion claim:

| Check | Result |
| --- | --- |
| Three main output files and six run JSONs | Byte-identical copies of the old sources |
| Six copied transcripts | All 126 original message contents are present literally |
| Paired CSV | All 30 actual criterion scores match the six full retained records |
| Complete original JSON records | Not delivered: the six JSON files are compact summaries without full `state` |
| New measurement/provenance verification | Not produced; no deterministic analysis or verified final publication |
| Actual browser file downloads | 15 file-row clicks, 212,484 bytes; all match independent Object Storage reads |
| Unattended/restart behavior | Not qualified by this run; no durable workflow or browser-close witness |

The independent full-source denominator remains six consultations, two
profiles, three clinicians, five distinct criteria and 30 scores. The report
copy is not a new benchmark, scientific revalidation, or evidence that the
planner inspected the full records. The observer's subsequent verification
must not be attributed to the agent's work.

The first UI download harness mistakenly expected a separate download button
after clicking a file row; file rows already initiate downloads. That timeout
and its partial files remain unchanged. A separately labelled corrected UI
check clicked each of the 15 actual file-row buttons and matched every hash.
This was an observer harness correction, not a customer retry or product fix.
The harness's refreshed same-user cookies were synchronized back to the same
browser once before UI verification; no additional password login or auth
configuration change was made.

## Evidence

Protected root:
`/home/tux/secure-handoff/scientific-unattended-20260919/natural-v50/scientist-09/`.

| Receipt | SHA-256 |
| --- | --- |
| `capture-r1/messages-260f40f3-7de6-569f-b064-b49d0279caad.json` | `7591db21abd98eba3f8aa3a968ac0e3feec6ac715d5cf80673200cb4c683f034` |
| `capture-r1/studies.json` | `fe64905e6fa04b3e9031ee5fed2bbdb4bb3137a1c7a5bca77a8a8b07ec5a727f` |
| `independent-files-r1/receipt.json` | `8afc43063572b81a5f11d736abfe1abdd056514d85af8e6612d60b1c4eed7c1e` |
| `independent-files-r1/copied-scientific-content-reassessment.json` | `677e54e8e0dd99143f852eda08ddbb3d8335277ebdbbfd21f1656114a59beeae` |
| `browser-delivery-r1/direct-download-hashes-r2.json` | `f874e15b05ecdab7507a8e4dc8588dcf792659fe96b2e12dea8b7b185fdd842d` |

The original prompt, inputs, failed assembly calls, prior conversations and
all outputs remain preserved. Later semantic-preflight changes and other
planner experiments are separate identities, not retrospective passes here.
