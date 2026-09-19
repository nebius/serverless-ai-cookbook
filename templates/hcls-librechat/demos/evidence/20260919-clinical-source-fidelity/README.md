# Clinical source-fidelity repair — bounded evidence, not medical readiness

The original full English consultation transcript (6,817 bytes; SHA-256
`e511be3353a9cdad1d2d2f10e7000ec7b9f2986e01ed3785f10723d99e3ffbee`)
is unchanged. No ASR was repeated. All provider calls used the existing
Qwen/Qwen3-235B-A22B-Instruct-2507 profile, temperature and per-call budgets.
Original failures, completed directories and model responses remain retained.

## Defect and repair boundary

In the real v36 client/v5-document replay, both extractor and reviewer declared
an incorrectly normalized medication name to be non-medication, with empty
source anchors. The reviewer explicitly justified a phonetic substitution.
The boolean-dependent guard therefore failed. This was not an ASR repair.

The successor constructs factual passages only from validated literal source
phrases. A model's medication classification cannot authorize new factual text.
Every accepted entry displays its complete cited source context immediately
beside the selected passage, including conditions and speaker context; selected
phrases must not be treated as standalone instructions. Report headings and
review explanations are separate from the source-language factual passages.

Coverage uses validated phrase locations, not model claims that a segment was
read or excluded. At most one additional extraction per original chunk receives
only segments without validated phrases. Initial omissions, self-exclusions and
remaining gaps are preserved in `coverage.json`. There is no retry-until-success,
context/output-budget escalation or new vocabulary/medication dictionary.

Unverified uncertainty descriptions and question rationales remain review-only.
Visible uncertainty text points to exact source wording. Rejected proposals
cannot become report facts. Completed older-version output directories require
a new directory; they are neither overwritten nor silently upgraded.

## Utility comparison on the same transcript

Counts are accepted **automated source entries**, not medically verified facts.
Granularity changed between experiments, so counts are not an accuracy score.

| Candidate | Evidence type | Accepted / withheld | Review-only excerpts | Important observed outcome |
|---|---|---:|---:|---|
| Original v36 client, document v5 | Real deployed replay | 30 accepted | — | Incorrect normalized brand accepted; negative retained. |
| v6 token gate | New same-provider replay | 2 / 34 | 0 | Brand blocked, but severe utility regression. |
| v7 excerpt fallback | Exact-request-matched retained-response replay | 2 / 34 | 17 | Original wording retained, not a useful paraphrased note. |
| v8 exact phrase extraction | New same-provider replay | 25 / 9 | 7 | Literal phrases improved; late dose/rest/follow-up not selected despite normal completion. |
| v9 model-declared coverage | New same-provider replay | 5 / 12 | 12 | Dose present; wrong segment exclusions and atomic multi-phrase rejections exposed. No recovery fired. |
| v10 validated coverage | Retained negative v9 initial response plus **one** missing-only extraction and normal reviews | 22 / 17 | 12 | Literal unclear name, dose quantity, work/rest and conditional return wording retained. |
| v11 adjacent context | Deterministic render of unchanged v10 entries; **zero** new model calls | 22 / 17 | 12 | All 22 entries show adjacent full cited context, including the dose's preceding condition. |

Final selected passages contain 32 exact source phrases; every offset matches
the original transcript. Sixteen of 20 source segments have a validated phrase.
S13, S14, S19 and S20 remain explicitly without validated phrases. In particular,
further-test detail from S19 was not successfully extracted. Model exclusion of
a segment is not evidence that it lacks clinical content. The dose's preceding
condition is present in adjacent source context, not falsely claimed to be part
of the shorter selected phrase.

The final report and follow-up do not contain the normalized brand. The unclear
literal source name is retained, marked uncertain. This does not identify the
intended medicine or validate any treatment. Quote selection, speaker identity,
negation, condition scope, omissions and suggested questions still need human
review. This is a source-linked review draft, not a medically qualified report,
translation, complete consultation note or patient-safety claim.

## Verification and retained receipts

37 focused tests pass, including EN/DE literal/invalid spans, both-false/empty-
anchor bypass, immutable old outputs, finite missing-only recovery, false model
exclusions, quote deduplication, review-only speculation and adjacent conditions.
Ruff and whitespace checks pass. Final-version German provider inference and
final-image browser acceptance are **not** established by these local tests.

Protected receipt roots are held by the campaign operator; no transcript,
credentials or provider response bodies are published here:

- `clinical-source-vocabulary-v6/summary.json`: `716c4abe30744b90349578272ce199d9db77f2c348162a1e6f6de482950660ba`.
- `clinical-source-excerpts-v7/retained-provider-replay-r2/summary.json`: `9b45f1789b73cb809c6e987711f866864996de5d8fd0b159bd68e821b92cd0b8`.
- `clinical-source-phrases-v8/same-provider-replay/summary.json`: `6678374e8c3bb6563274e75691fe54f32808b1b2047e06de1982c453ac9f4340`.
- `clinical-source-coverage-v9/same-provider-replay/summary.json`: `e7c0f7cea238077a39b3f764eca6bc8b7acd1de4e85f8540badb90d7cb93c6cf`.
- `clinical-source-coverage-v10/retained-initial-bounded-followup/summary.json`: `3b91c8b83598a4fd1c553ba465a3e1c9cad051aa835efae750d048a013aaf808`.
- v11 rendered report SHA-256: `04e9c09ffd2b576b4a7ee4d35b6e35dc26e2af86e5fbb729ee3380d4c77e9cae`.

No shared deployment was changed by this repair lane. Parent/workbench owners
control the combined image, preserved-data upgrade and public-browser gate.
