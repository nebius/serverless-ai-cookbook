# Clinical natural v56: durable completion, incomplete customer delivery

The original one-prompt scientist08 study remains unchanged. Exact client source
`cba6304ec772a70cc7fccf44743145b0a7e3a479`, OCI index
`7b5b3b46713b61fd5fafc8085fa29fd8fc54f631a993c1aa28c4aa7d9e842c3c`,
backend190, explicit Kimi-K3 planner low/131072/8192. Drafting remained the
requested Qwen3-235B-Instruct profile; no new ASR, followup prompt, provider
fallback, budget increase, or operator repair occurred.

Study `236daf70-1be4-5651-88a4-3f681c9752c4` completed all five phases in
136.797 seconds: English draft, full German draft, permitted short-source
no-report outcome, WER, and report publication. The actual browser closed while
the study was running at19:29:31 UTC, then reopened to Runs with all five phases
complete. The original v54 negative-outcome failure remains visible separately.

## Verified scope and remaining failure

- All47 published phase files matched their size/SHA-256 receipts and independent
  exact-prefix Object Storage bytes (501 retained objects,6,129,275 bytes).
- English:29 entries/29 phrases, all literal offsets and adjacent cited contexts
  exact;19/20 declared source segments have a selected phrase,11 withheld
  candidates,8 review excerpts. German:25/25,14/14 segments,9 withheld candidates,
  6 review excerpts. These counts do **not** establish completeness, correct
  speaker attribution, medical meaning, or clinical readiness.
- The short162-byte German source produced explicit
  `no_supported_clinical_facts`, no report/document/questions, and retained source,
  review, coverage and provenance. Downstream work continued without another
  draft or prompt.
- All four WER outputs independently reproduced exact S/D/I and denominators
  using the existing deterministic edit-count helper and the actual declared
  custom normalization. Results:392/1570,447/1570,474/1570,3/25. The custom scorer
  uses NFKC/lowercase/Unicode-word-character normalization, distinct from the
  bundled edge-punctuation scorer; historical values are not rewritten.
- Eight actual Runs downloads (29,096 bytes) matched independently retained
  bytes. However the manifest contained outcome summaries, not actual draft
  reports/transcripts/documents/review/questions. The final report included
  completed flags but no measured source-selection assessment. **Requested
  customer delivery is incomplete despite the completed engine state.**
- Twenty additional clinical files were downloaded by operator navigation to
  phase folders and matched storage/phase receipts. This verifies accessibility,
  not natural final delivery, and is not counted as a repaired study.

Private evidence root is
`/home/tux/secure-handoff/scientific-unattended-20260919` (`U` below). No clinical
text, credentials or raw provider content is included here.

| Receipt under U | SHA-256 |
| --- | --- |
| `v56-owner-bindings/scientist-08/receipt.json` | `9474fec46cefd4417f7675662ecbdc1d0d6fbe99f97ddcf57269dd37319b59c7` |
| `natural-v56/scientist-08/disconnect-r1/receipt.json` | `5bf9c697b21a36b320f13e927e05ea6d03d668ef152df4405e18e128cae233c0` |
| `natural-v56/scientist-08/readback-r2/study.json` | `63af593f786113a66f6f79ccd2c699e32db4d128bbe06c5450ee2299543a46e8` |
| `independent-v56/scientist-08-s3-20260919T193223592078Z/independent-verification.json` | `384c2a6421e2541a7d6127adf297d913409f4a37deef0adfb4edf7da60136fbc` |
| `independent-v56/scientist-08-browser-r1/download-receipt.json` | `49e50d6f3190048c11f374fca946212a39f5bf428b7044156d219edd3d81b71a` |
| `independent-v56/scientist-08-browser-r1/clinical-phase-downloads/receipt.json` | `a4a2549290a847b4a27a280a027b2ec115da1546ac6addd77b61e8761e7b2da5` |

## Separate source repair; not deployed or retroactive acceptance

`scientific_clinical.outcome_documents` now uses the existing v11
`study_report.selection_report` against the full unchanged source/document.
Stable outcome JSON/Markdown carries exact selected-span/segment counts,
withheld/review counts, source-selection gaps and explicit limits. No new
clinical judgment, source rewriting or model call is introduced. Negative
outcomes retain an explicit no-report assessment instead of inventing a draft.

`customer_artifacts` registers a bounded, hash-verified allowlist: positive
source/report/document/review/questions/coverage/run and outcomes; negative
source/review/coverage/run and outcomes only. Catalog, calls and checkpoints are
not registered. The separately coordinated Study publication hook appends these
with step-qualified names, retaining strict declared deliverables and avoiding
duplicate paths. The clinical skill explains measured outcomes and actual
downloads rather than treating a completed flag as delivery.

33 focused tests passed, plus Ruff and the skill validator. Tests cover missing
required files, corrupt hashes/offsets/source identity, default strict negative
failure, explicit negative continuation after process restart, unchanged draft
bytes, downstream measured report, and automatic positive customer downloads.
The initial new-test collection used the wrong module for `measure`; that
test-only import was corrected before this passing gate. No runtime limit changed.

A retained-only replay of the exact v56 English/German/negative files registered
10/10/6 customer files and reproduced the same literal measurements, without
writing the original study. Its receipt is
`U/clinical-customer-output-repair-v56/receipt.json`, SHA-256
`e3cc0617766fbeff40cb51e2bb658b4ad3376e97fdcfc3920598054abd894c84`.
Installed successor and natural customer delivery remain required gates.
