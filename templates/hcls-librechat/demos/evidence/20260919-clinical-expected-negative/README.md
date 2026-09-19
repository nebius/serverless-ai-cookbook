# Explicit clinical no-report outcomes

The original scientist-08 v54 study `e8ce4b96-1b56-515a-a89c-f0a7850e729a`
is retained as failed, not repaired. Its English and full German drafts finished;
the explicitly requested short-source negative produced the existing typed
`no_supported_clinical_facts` result. The old adapter stopped the entire study
there, before its analysis and final report. No continuation or extra provider
call was made to repair that natural journey.

The successor adds optional `allow_no_report: true` to a clinical stage. This
must represent the user's explicit allowance for that stage, not an instruction
to ignore errors. Default/false remains strict. Only the exact typed no-facts
outcome can complete without a clinical report; it must retain verified
`transcript.txt`, `review.json`, `coverage.json`, and `run.json`, have no active
operation, and contain no report/document/follow-up artifacts. Provider errors,
unknown admission, incomplete/corrupt evidence and cancellation retain their
existing failure/pending semantics.

Successful stages publish separate `clinical-outcome.json` and
`clinical-outcome.md` artifacts. A downstream deterministic report can consume
the latter whether the result is a draft or an explicitly allowed negative.
This does not fabricate a clinical letter, assert absence of illness, establish
completeness, or change the report model, extraction, retry or token budgets.
Existing positive draft bytes are unchanged.

## Source qualification

- 16 new tests cover strict defaults, positive byte preservation, exact opt-in,
  failure/pending/cancellation isolation, missing/corrupt evidence, active
  operations and nonboolean rejection.
- The full-study test persists the negative phase, then runs the real report
  helper and final publication in fresh Python processes. Re-entering the
  clinical adapter is forbidden in those processes; four nonempty artifacts
  and the final manifest are hash-verified. The provider boundary is a fixture,
  not a claim of new clinical inference or installed-image acceptance.
- 41 combined clinical/core/discovery tests and Ruff passed.
- Protected JUnit: `U/clinical-expected-outcome-source-tests-r2.xml`, SHA256
  `54e766f0e255c364e2c5d37169e109c92d02c190e8051561bfe6b7678d50ad94`.
  The preceding command named a nonexistent test file and collected nothing;
  its receipt remains separate. Initial new-test UUID/role fixture mistakes
  were corrected without changing runtime validation.

`U` is the private `scientific-unattended-20260919` handoff directory. Clinical
content and provider receipts remain there, never in this portable note.
Exact installed SDK and new natural-client acceptance remain separate gates.
