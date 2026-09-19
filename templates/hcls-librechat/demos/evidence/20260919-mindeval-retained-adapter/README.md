# Retained MindEval report adapter: offline qualification

The new file-based adapter was checked independently against six complete,
unchanged records from the existing scientist09 workspace. No consultation,
judgment, model or workshop request was submitted. This does **not** establish
natural-client adoption of the durable phase, clinical validity or a final-image
release gate.

At 14:41 UTC on 19 September 2026, the deterministic replay measured:

| Quantity | Observed value |
| --- | ---: |
| Retained consultations | 6 |
| Profiles | 2 |
| Clinicians | 3 |
| Distinct criterion names | 5 |
| Profile–criterion cells | 10 |
| Literal transcript messages, including seeds | 126 |
| Supplied judge-score rows | 30 |
| Original JSON bytes | 746,549 |

Ten profile–criterion cells are not ten criteria; message counts are not
patient–clinician round counts. Scores remain uncalibrated and descriptive.

All original JSON bytes and full transcript contents were retained. Every score
was compared directly to its source run/criterion. Every completion artifact and
every source referenced by report provenance passed hash/size readback. Running
the unchanged helper again produced identical results. The original files were
not modified.

The independent tests caught two adapter defects before image publication: the
combined `records.json` source was referenced but not published, and malformed
falsey judgment envelopes could be masked as absent. Both were fixed by the
integration owner. The new 29 tests plus 24 existing report tests pass, covering
non-hardcoded counts, absent/partial/invalid scores, full long transcripts,
duplicate IDs, conflict preservation, interrupted writes, bucket readback failure,
CLI execution and the actual workflow-discovery output filenames.

Test: `python -m pytest -q templates/hcls-librechat/test_mindeval_report.py templates/hcls-librechat/test_report_assembly.py`.

Protected replay receipt:
`/home/tux/secure-handoff/scientific-unattended-20260919/mindeval-adapter-replay-20260919T144120276714Z/receipt.json`
(SHA256 `489e4d33885d4429bbb92f36bdc95585ce78a23046ae0ce1ab084bddec7ec7bb`).
Its helper SHA256 is
`072534e0a4b33643e62d37c8ed7a8d45bfb2e9332f6d823872052e00dc0c3cc5`;
publisher SHA256 is
`be4e6bc84c7a2514e99f2e26e68838f789f17347dc80562540aeb47feb5fdd37`.
The exact 15,856-byte report is SHA256
`d7b9e852b9a96a5e9fdd1aa2cf645ac1b8f06862adfa80b9eb9e1eb99a3cb54d`.
Records, report payloads and private paths inside the source bundle remain out
of Git. A changed helper/image requires its applicable successor acceptance.
