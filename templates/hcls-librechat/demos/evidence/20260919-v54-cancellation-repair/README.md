# Cancellation of a blocked, known-operation Study

Scope: source repair after the failed v54 scientist-10 natural robotics study.
No new inference, live code patch, receipt rewrite, resource change or deployment
was performed by this repair. The original study is not an acceptance pass.

## Observed failure and cause

The native model operation succeeded and retained its MP4. Its workbench client
failed while expecting JSON, leaving the whole Study `needs_attention` with its
queue blocked. Those original failures and artifacts are archived separately;
model success did not deliver the requested complete report.

The operator made one supported Study cancel request at 18:53:54 UTC. HTTP 200
reported `cancellation_requested: true`, but all 15 subsequent observations
remained `needs_attention`. The changed receipt timestamps and later `TypeError`
prove the worker processed the request: this was **not a worker wake-up defect**.
`cancel_known_operation` treated every `operation` field as a nested object.
The actual native response is flat, with `operation: "generate-media"` and a
top-level `status: "succeeded"`. Indexing that string as an object failed. The
old exception handler also replaced the displayed original failure; its prior
immutable journal and full pre-cancel archive remain retained.

Protected evidence under `scientific-unattended-20260919/`:

| Retained file | SHA-256 |
| --- | --- |
| `v54-10-remaining-cancellation/response.json` | `0384bf4d4dea1ea05bdc798ca5de7d6aae943fb2ea96d4ad7ecdd3af5083b2bf` |
| `v54-10-remaining-cancellation/observations.json` | `823ce134e04d463c1938d17c175dae2a6f228f242e01c40e3b1f72edcda4e8f7` |
| `v54-10-remaining-cancellation/operation-before.json` | `3bf2833318cecb4cc4b879de465686faead637df8e5fcb6b2284667d46e0221c` |
| `v54-10-owner-handover/capture-r2/scientist-10/archive-sha256.json` | `7a7bfa9daff2676daceb972c9e75adf3e95920ae0a61542ba71d403e6daef890` |

## Narrow repair

- Recognize nested scientific operation objects only when the field is an
  object; accept the existing flat native shape. Missing status fails closed.
- Keep cancellation errors in `cancellation_failure`, preserving the original
  `failure` and immutable receipt history. No historical record is rewritten.
- A saved cancellation may run on a stopped-predecessor successor with changed
  analysis helpers or source files. It verifies the same owner, caller, frozen
  plan/output identity and agreement with the saved operation ID. It does not
  execute any scientific or local analysis phase. Ordinary resume still verifies
  all pinned input/helper/output bytes.
- Unknown admission remains blocked. A previously saved cancellation intent is
  reconciled using status only, without repeating its cancellation request.

`test_study_cancellation_contract.py` covers the actual native response shape,
wrapped batch shape, nonterminal and malformed status, worker-cycle processing
on changed input/helper bytes, preserved original failure, and owner/caller/
plan/operation mismatch or unknown admission. It asserts zero model admissions.
The original live v54 failure remains separate from these source/test results.
Exact successor-image qualification and live queue release must be recorded
separately; these tests do not establish either or scientific validity.

Source validation: 98 tests passed across cancellation, whole-study, clinical,
expected clinical outcomes, receipt storage/publication, native file transport
and typed Study text. Ruff and `git diff --check` passed. Existing pytest
temporary-directory cleanup permission warnings were unrelated to these tests;
no broad cleanup was performed.
