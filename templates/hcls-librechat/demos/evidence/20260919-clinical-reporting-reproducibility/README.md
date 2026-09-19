# Clinical study reporting: source-only correction

This candidate repairs **measurement reproducibility and claim discipline**, not
the clinical content, ASR model, inference settings, or v11 evidence checks.
No model calls, builds, deployment, or endpoint changes were performed for this
follow-up. The original natural08 v39 artifacts remain unchanged. Planner use of
the new helper still requires an exact-image customer-client replay.

## Retained defect

The original v39 browser workflow completed four ASRs and one clinical draft.
Its private acceptance receipt is `browser-evidence/scientist-08-v39-final/acceptance-receipt.json`,
SHA-256 `bc3586eaa02fa4144d5c41a838c96dbc244c0b0d8ce05b54ad46277612c45d7f`.
The actual report hash is
`10464dae95e182f93223b8187ebb3b0704499777f493f894ccdfa61f728b17f8`.

Two reporting failures are preserved:

- The emitted English WER table used 1,413 reference tokens, while its saved
  `wer.py` strips the standalone `--` token and yields 1,412. Keeping that token
  reproduces the emitted denominator and total edit distances; this was not an
  ASR output change. The separately pinned campaign scorer uses another regime
  (1,419 English tokens); it is unchanged and must not be conflated with either.
- The planner called 16 keyword-presence checks evidence of no important
  omissions. Repeated full contexts and review excerpts can contain a keyword
  that was never selected as a report fact. Literal selection also does not
  establish speaker, condition, clinical meaning, or completeness.

## Source candidate

`skills/clinical-documentation/scripts/study_report.py` is a stdlib-only offline
helper, included by the existing skills-directory Docker copy. It emits JSON
and Markdown from a single calculated result and retains byte-identical input
copies plus its exact executed `helper.py`. Completed output directories cannot
be overwritten. Replaying the retained helper and inputs into a new directory
reproduces both output files byte-for-byte.

The named normalization is `casefold-annotation-edge-punctuation/v1`: keep
uncertain inner words, remove the three documented reference annotation
markers, casefold, whitespace-tokenize, strip the declared edge-punctuation
characters (including `-`), and discard empty tokens. No number, contraction,
translation, or medical-word correction occurs. Alignment ties have an explicit
deterministic order. This is one reproducible regime, not a scientifically
privileged replacement for other declared regimes.

Helper SHA-256:
`db4eac1c94f689aa93e2540969e5d0cf3443bc8ab028016ab46e056bc9f4d08a`.

The coverage command reads v11 structured evidence and verifies exact source
offsets. It ignores model coverage labels when counting actual selected spans.
Optional exact source-range probes distinguish `selected_phrase`,
`cited_context_only`, `review_excerpt_only`, and `source_only`. These are literal
locations, **not** semantic entailment or medical completeness classifications.
All report language retains `clinical_completeness: not_established` even when
every supplied probe has a selected match. The bundled skill requires reporting
those limits and quoting generated metrics rather than manually recounting them.

## Offline remeasurement of unchanged actual v39 artifacts

All four JSON/Markdown pairs and the coverage pair reproduced byte-for-byte
with their retained helper/input copies. Original clinical files, source
transcripts, saved scorer, emitted metrics and disputed reports were hash-checked
before and after and remain unchanged.

| Actual retained transcript | N | S | D | I | Exact WER fraction |
| --- | ---: | ---: | ---: | ---: | --- |
| English Nemotron | 1412 | 92 | 108 | 62 | 262/1412 |
| Multilingual Nemotron, English | 1412 | 122 | 138 | 55 | 315/1412 |
| Parakeet | 1412 | 124 | 193 | 24 | 341/1412 |
| Multilingual Nemotron, German | 25 | 2 | 1 | 0 | 3/25 |

Counts are for the new explicitly named regime. The old tables are retained,
not silently replaced. WER is lexical agreement, not clinical quality.

The v11 draft still has 33 accepted facts, 40 selected phrases with 41 literal
span occurrences, 14 withheld candidates, and 10 review excerpts. Eighteen of
20 declared segments have at least one selected phrase. A whole-source probe
shows that the dose's condition and further-test wording are only in cited
context, while the return-if-persistent phrase is selected. The full no-alcohol
clause crosses a context boundary and is not a retained selected/context/review
span. A keyword lookup cannot establish preservation of that clause. No draft
text was changed to repair these limitations.

Protected reassessment: `browser-evidence/scientist-08-v39-reporting-reassessment-r2/receipt.json`,
SHA-256 `a11d4ee32c699619fc22a302d81b255bd15ec265240df28fcb73c0b275097a64`.
Earlier v39 failures and the first offline helper-development receipt remain
retained separately. Raw source text and reports are not published here.

## Tests and follow-up gate

- 18 new focused methodology tests, including standalone `--`, EN/DE text,
  empty references, stable alignment ties, ignored model coverage labels,
  context/review-only false positives, repeated span occurrences, exact source
  identity, immutable output, and byte-exact replay.
- Full clinical scripts suite: **55 passed**. Ruff passed for both new files.
- No changes to `clinical_report.py`, `document.py`, the campaign scorer,
  model/provider, output/context limits, MCP transport, ledger, or clinical
  accepted/rejected content.

`follow-up-inputs.json` beside the protected receipt pins the same 13 original
assets and original prompt hashes; SHA-256
`984eb65cd59d1e7472939fa773d9c8033663243da6e1603146848940e766ff15`.
It authorizes no inference. After a release owner supplies the actual candidate
image and approval, use the original natural study prompt unchanged except for
a fresh output directory, with the same four-ASR/one-draft scope. Verify actual
helper adoption, output hashes, browser downloads and appropriately bounded
final language. These source tests do not qualify that future client behavior
or establish medical readiness.
