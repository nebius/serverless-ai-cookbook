# Natural v54: dependent design delivered; clinical study stopped at its negative

These are the unchanged r7 customer tasks, one prompt per dedicated user,
explicit Kimi-K3 planner (low, 131072 context/8192 output), client source
`12fb896b4dd6c3b856b4b07da903bad08546a0ec`, image index
`c5d01a265447b6d89c155c6266acdad18e158b78eba8888fa2586b41234d421a`,
and backend190. Both browsers were closed only after fresh running-Study
readbacks, then reopened for progress and actual downloads. No continuation,
technical coaching, live repair, model switch, budget change or worker eviction
was used in these two journeys. The earlier separate backend eviction test is
not this natural cohort.

## Scientist04 — bounded dependent workflow pass

Study `370672c8-24ec-533d-8137-ef6ad22ee8e2` completed all eight phases:
RFdiffusion → complete-backbone preparation → ProteinMPNN → selection of the
first generated design → ESMFold2-Fast → explicit correspondence → structure
analysis → deterministic report. Three successful inference operations and
four input uploads are distinguished in the public readback. There were no
Mosaic/BindCraft calls and no selection of a better-looking later sequence.

Independent retained-byte inspection verified all 70 phase/final files and
manifests, actual input/output links, the four generated sequences, selected
index0, chain identities, all 48 positions and complete N/CA/C/O backbone.
Only 1 of 48 residues is identical between the poly-G design scaffold and
selected design: the correspondence is positional and hash-bound, not a
sequence-identity-only fit. Independent fixed-column PDB/Gemmi CIF parsing and
NumPy proper-rotation fitting reproduce the reported CA RMSD
1.7519136354081695 Å. All-float64 coordinate parsing gives
1.751913686597777 Å; matching the production parser's float32 coordinates gives
1.7519136354081697 Å at the original 1e-10 comparison tolerance.

All **10** declared files were clicked from Runs and downloaded through
Workspace (49,198 bytes); their bytes match both published hashes and the
independent S3 snapshot. Browser close was at18:24:39UTC while running, before
the first inference was accepted. No manual repair was needed after disconnect.

Limitations remain visible: one backbone/refold does not establish stability,
binding or biological function; diffuser_T50 was a planner-selected default.
The structure analysis did not receive `request_file`, so its sampling section
truthfully says unknown even though exact seed controls are retained and checked
in the request/provenance files. The interim chat was Russian despite an English
task; the downloaded report is English. This pass is **v54**, not a successor
image claim.

## Scientist08 — partial drafts, whole-study failure retained

Study `e8ce4b96-1b56-515a-a89c-f0a7850e729a` completed the English and full German
drafts, then failed at the explicitly requested short-source no-report outcome.
The clinical helper correctly returned `no_supported_clinical_facts`; the old
whole-study adapter stopped instead of permitting the expected negative. Thus
WER analysis and the final study report did **not** run. No further prompt or
extra draft was used to repair the result.

Independent literal checks found:

| Draft | Accepted facts / phrases | Segments with a selected phrase | Withheld / review excerpts |
| --- | --- | --- | --- |
| English | 23 / 31 (32 literal occurrences) | 18 / 20 | 13 / 9 |
| German | 24 / 24 | 13 / 14 | 13 / 8 |

All selected offsets match the unchanged source and full cited contexts are
rendered adjacent to their facts. Literal `dire light` remains, not an invented
brand. The English draft has zero uncertain-fact flags and German has one;
these counts do not establish adequate uncertainty detection. Reviews,
questions and source excerpts remain separate. Literal fidelity and segment
presence are not medical correctness, speaker attribution or completeness.

The negative retains11 verified checkpoint files, including its unchanged162B
source, review, coverage, run and both existing bounded extraction responses.
It produces no report/document/follow-up. No new ASR or platform operation was
submitted. The planner prepared custom WER code instead of the installed pinned
report helper; no measurement from that unexecuted code is accepted.

The operator navigated the two completed phase directories and clicked **18**
Workspace downloads; all match the phase receipts and independent S3 bytes.
These are partial drafts, **not final Runs deliverables or whole-study success**.
The successor's explicit opt-in fix is documented separately in
[clinical-expected-negative](../20260919-clinical-expected-negative/README.md).

## Protected evidence

`U` is `/home/tux/secure-handoff/scientific-unattended-20260919`. Clinical content,
credentials and raw messages are not published here.

| Receipt under U | SHA256 |
| --- | --- |
| `independent-v54/scientist-04-s3-20260919T183121354853Z/independent-verification.json` | `5eec9fa1a3aa114829043d381170e0ca7346c032788bb596389c59105c484eb8` |
| `independent-v54/scientist-04-browser-r1/download-receipt.json` | `2ec39326e693e494d58490d1cc7ebae97db13e24dbd63be2ad502e3a99a08a9f` |
| `independent-v54/scientist-08-s3-20260919T182759887273Z/independent-verification.json` | `e431b3c5c67fb47a22f64fcb4a0ae5ff50059c020cf179958e68dfd2847f7f85` |
| `independent-v54/scientist-08-browser-r1/partial-downloads/receipt.json` | `3bd0914ee40fe2afcb2174bb4ea2c047581a1d063e2a0fc8198a8d79eebedc71` |

`v54-08-owner-handover/final-r3/retirement-proposal.json` binds the exact08
endpoint, complete conversation/configuration/local-registry archive and435-file
S3 snapshot. Its final read found zero active generations/operations. No endpoint
lifecycle action was performed. The archive retains a stale observer-cookie401
and the inherited harness's missing browser User-Agent/SSE error; exact current
browser-state rebinding and normal headers resolved those observation issues,
without password login or runtime/auth-policy changes. The first independent
clinical rendering check mistook an inline hyphen for a fact boundary; the
corrected checker binds exact fact IDs and real list boundaries. None of these
harness issues is silently counted as a customer scientific failure or pass.
