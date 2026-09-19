# Natural clinical workbench v42 — bounded revalidation

Three scientist08 conversations finished on **19 September 2026, 05:21:21 UTC**.
Two drafts and the expected no-report negative were delivered. Source-preservation,
download and pinned measurement checks passed; residual agent-written analysis
errors mean this is **not clean customer or clinical readiness**.

## Exact deployment and scope

- Client source `7674a107eeeb2fce5782030c872adad91e966add`.
- Image index `sha256:ffc003193e5e26886ad1c5f3278b2e6a07e6c1dd51234131c8da901b0256fc81`;
  amd64 `sha256:c024118c6b9a8d5d1972d871dd011e34bb9e81c249408921f0e0f1f86b0e185b`.
- Isolated endpoint `aiendpoint-e00h0p3h5hddp0ktay`, scientist08's unchanged key,
  mounted bucket and configured Apps. No endpoint, limit or provider changes.
- Planner: `deepseek-ai/DeepSeek-V4-Pro-0813`, low reasoning, 8,192 output tokens,
  131,072 context. Report provider: `Qwen/Qwen3-235B-A22B-Instruct-2507`.
- Original v39 prompts changed **only in output directories**. Full sources
  remained unchanged; no expected-answer hints or scientific-method coaching.

The English conversation spans backend182's CP-only rollout: Helm started
05:05:48.23772438 and was settled by05:10:17. Its first failed turn ended
05:05:32.055, **before** that upgrade. All three report jobs began after the
settled boundary. This is not a frozen182 full-pipeline acceptance cohort.
See [installed-image evidence](../20260919-integrated-client-v42/README.md).

## Actual customer journeys

| Cohort | First prompt → final answer (UTC) | Wall time | User turns | Report-job result |
|---|---|---:|---:|---|
| English full PriMock57 study | 05:02:44.709 → 05:16:15.397 | 810.688 s | 3 | Draft completed in37.720 s |
| German full HHU acted consultation | 05:17:03.647 → 05:19:14.630 | 130.983 s | 1 | Draft completed in56.134 s |
| German short non-consultation negative | 05:20:11.370 → 05:21:21.467 | 70.097 s | 1 | Expected no-report outcome in4.122 s |

These are different clocks: total customer time includes preparation, analysis,
downloads and the English user's two ordinary continuations. Report time is not
GPU occupancy. The negative uses public job creation→finish, whereas completed
drafts use the worker's start→completion.

English's first turn ended without a usable answer; the second explicitly
stopped at an interim result. Both are retained. There were self-recovered
tool-name, shell and upload-concurrency errors. No provider finish reason was
exposed in the retained message, so token exhaustion is not asserted as the cause.

**No fresh ASR inference was performed.** The recovery chose four earlier
succeeded v39 operations and explicitly reported their reuse. There were two
new artifact uploads and three new clinical jobs: two drafts and one expected
negative. This validates draft/recovery/measurement behavior on full retained
ASR, not a repeated fresh voice→report pipeline. It does not add four calls to
the campaign inference count.

## Independently verified results

The natural English agent used the installed `study_report.py` without a manual
method correction. Its four WER bundles and one source-selection bundle
regenerate JSON and Markdown **byte-for-byte** from their saved helper/inputs.
Helper SHA256: `db4eac1c94f689aa93e2540969e5d0cf3443bc8ab028016ab46e056bc9f4d08a`.

| Retained ASR output | Edits / normalized reference words | WER |
|---|---:|---:|
| Nemotron English | 262 / 1412 | 18.5552% |
| Nemotron multilingual, English | 315 / 1412 | 22.3088% |
| Parakeet English | 341 / 1412 | 24.1501% |
| Nemotron multilingual, short German | 3 / 25 | 12% |

The reported table and declared normalization match the saved code. These are
lexical errors, not a medical accuracy rating; alternative earlier normalization
regimes remain separate historical measurements.

- English draft: unchanged6,817-byte ASR, SHA256
  `e511be3353a9cdad1d2d2f10e7000ec7b9f2986e01ed3785f10723d99e3ffbee`.
  Its32 selected passages match literal offsets with adjacent cited context;
  nine candidates were withheld and seven source excerpts retained for review.
  Selected phrases occur in19/20 declared segments, **not proof of completeness**.
  The draft does not silently normalize the uncertain medication name; original
  ASR errors and conditional dosing context remain visible.
- German full draft: unchanged4,798-byte source, SHA256
  `c0c0aeebaef6383955d8fb4e98d34820d0a90c675302ec6bbb522bab4bb729e8`.
  Its26 passages pass the same literal/context checks; ten candidates were
  withheld and eight excerpts retained. Independent accounting finds13/14
  segments with selections. Narrator setup is contextual, not a selected patient
  finding. The generic findings section still mixes self-report with other
  content; this is not audio-verified speaker attribution. No verified human
  transcript exists for this full German recording, so no WER is claimed.
- German negative: unchanged162-byte non-consultation source, SHA256
  `ecf9a586ece9c373ba38d721cc9301ddc05e66e8d4b3aa28179dadc63f0c267f`.
  Public status/run expose `no_supported_clinical_facts` and an actionable
  explanation. No provider `report.md`/`document.json` exists; requests return409.
  The actual UI offers only source/review/run downloads and no report button.
  The agent's separate workspace `report.md` is clearly headed **not created —
  insufficient source**, a limitations note rather than a fabricated Arztbrief.

All **24 actual browser UI downloads** were nonempty and byte-identical to the
retained authenticated API/workspace files: English12, full German7, negative5.
This includes the faulty supporting comparison file; downloading it is not
accepting its contents.

## Remaining defects and precise reproduction

1. English's ad hoc `reference-comparison.json` says `accepted_fact_count: 0`;
   `clinical/document.json` and the pinned coverage measurement correctly say32.
   The generated walker searched `source.text` instead of the canonical
   `facts[].source_phrases`/`statement`. The wrong JSON remains linked in README.
2. The prose calls alcohol information omitted because one wording was rejected,
   although accepted F0039 contains the equivalent source phrase. Rejection of a
   candidate's exact wording is not evidence that the concept is absent.
3. The English report suggests Parakeet's deletions follow from lowercase and
   unpunctuated output, despite normalization casefolding and stripping edge
   punctuation. That causal explanation is unsupported.
4. The German agent declines automated coverage for lack of a human reference.
   That is appropriate for WER, not for source-selection accounting. The separate
   operator measurement is not credited as natural agent delivery. Similarly,
   a fixed exact-span probe may miss a differently bounded equivalent selection;
   probe/keyword presence is not a semantic completeness metric.

Reproduce defect1 from the untouched protected study directory:

```sh
jq '.accepted_fact_count' reference-comparison.json
# 0
jq '.facts | length' clinical/document.json
# 32
jq '.measurement.accepted_facts' measurements/source-selection/measurement.json
# 32
```

Recommended next work is a typed, schema-bound comparison/report path using the
existing deterministic measurement helper, with inconsistent denominators/field
lookups surfaced rather than published as results. Separately distinguish exact
source selection, semantic coverage and clinical interpretation. Do not treat
literal copying as clinical correctness or silently revise these old artifacts.

## Evidence and preservation

[Portable receipt](receipt.json), SHA256
`d93ad8ee30b4414f3e2eb1493de5ddb1ceac73d37f060aa79ed68b4a2ec04d11`, binds
the exact conversations, jobs, source hashes, file hashes and timings. Its raw
references are beneath the protected campaign root
`/home/tux/secure-handoff/scientific-qualification-20260918` (`Q`).

- `Q/browser-evidence/scientist-08-v42-{english-final,german-full-final,german-negative-final}`:
  original messages, caller history and report outputs.
- `Q/browser-evidence/scientist-08-v42-browser/`: screenshots and real downloads.
- `Q/browser-evidence/scientist-08-v42-independent-final/`: five exact replays.
- `Q/browser-evidence/scientist-08-v42-german-full-independent/`: independent
  source accounting; the first checker assumed English renderer labels and
  failed locally. The corrected bilingual boundary check required **no inference**;
  its original harness error is retained and is not a model failure.
- `Q/browser-evidence/scientist-08-v42-input-verification/`:15 input hashes.
- `Q/browser-evidence/finalize-v42-clinical.py`: receipt assertions and provenance.

Historical v36/v39 failures and every v42 output remain unchanged. A progress
directory's mistaken `0514` suffix is not an observation time; all reported
timings use persisted records. No new admissions after these three cohorts.
This remains a research workbench assessment, not clinician/patient-use approval.
