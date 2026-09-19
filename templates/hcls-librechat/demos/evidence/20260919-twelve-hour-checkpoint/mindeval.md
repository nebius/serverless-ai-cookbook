# MindEval full20-r1: descriptive pilot

This separate **public API batch** used scientist09's ordinary key and unchanged one-worker policy. It is not natural LibreChat acceptance, a clinical trial, calibrated clinician assessment, or part of the GPU scientific-operation denominator.

## Frozen comparison

The first twenty profile IDs (`profile-000` through `profile-019`) from the pinned public catalog were each assigned to all three clinician models:

- `Qwen/Qwen3-235B-A22B-Instruct-2507`
- `openai/gpt-oss-120b`
- `zai-org/GLM-5.1`

Patient model: `Qwen/Qwen3-30B-A3B-Instruct-2507`. Judge: `google/gemma-3-27b-it`. Each consultation uses ten clinician/patient rounds, English, temperature 0.7 and a 4,096-token response ceiling. One seeded patient greeting is not a model response. Source provenance pins SWORDHealth/mind-eval revision `1c17f9e66c092d9480c4bda5a2bebc80b7f84961` and prompt/profile hashes in the retained frozen manifest; no hidden profile or transcript is published here. This first-ID selection is not representative clinical sampling.

## Terminal result and coverage

All **60 consultations completed** by the retained 05:53:04 UTC observation on September 19; the runner exited normally. Independent revalidation found **60/60 structurally passing reports**, all twenty profiles paired across all three clinicians, and all five exact rubric criteria finite within [1,6]. Each clinician has twenty reports and 200 generated clinician responses. No truncated turn/judge response, human intervention, missing completion identity or invalid report was found in this cohort.

There are **1,200 generated conversation responses** (600 clinician, 600 patient) and **60 separate judge responses**. The 60 seeded greetings are excluded from provider-response counts. The transcript-entry total also happens to be 1,260 because it includes greetings but excludes judge responses; these are different populations. These counts remain separate from backend serving/scientific operations and from earlier MindEval cohorts.

### Descriptive judge means

Each cell is the mean of twenty profile scores, rounded to two decimals on the 1–6 rubric. Full precision and all **60 profile-matched model-pair comparisons** (twenty profiles × three model pairs, five correlated axis differences each) are retained in the private analysis JSON. Means/pairs were computed only after the entire matrix passed; there is no pooling of incomplete cases or selection of favorable profiles.

| Judge rubric axis | Qwen3-235B | GPT-OSS-120B | GLM-5.1 |
|---|---:|---:|---:|
| Assessment & Response | 4.59 | 3.81 | 4.44 |
| Clinical Accuracy & Competence | 4.36 | 3.74 | 4.25 |
| Ethical & Professional Conduct | 4.83 | 4.73 | 4.73 |
| AI-Specific Communication Quality | 3.56 | 3.26 | 3.48 |
| Therapeutic Relationship & Alliance | 4.93 | 4.13 | 4.69 |

No composite winner, hypothesis test, confidence interval or calibrated clinical interpretation is inferred from this table.

### Timing, retries and reported usage

The study was frozen at 03:01:07 UTC; observed generated-turn timestamps span 03:02:24–05:42:52, followed by completion of judging at 05:53:04. Per-consultation admission-to-terminal wall time is 161.9–171.7 minutes (median 167.0), **including queueing and judging**, not isolated model execution. The retained per-response telemetry reports:

| Role | Responses | Mean latency | Median latency | Reported total tokens |
|---|---:|---:|---:|---:|
| Clinician | 600 | 9.089s | 5.687s | 2,343,718 |
| Patient | 600 | 4.132s | 3.000s | 3,276,579 |
| Judge | 60 | 5.427s | 3.472s | 1,583,717 |

All 1,260 response receipts report `finish_reason=stop`, zero retries, and prompt/completion/total token usage with no missing fields. Aggregate reported usage is **6,726,846 prompt + 477,168 completion = 7,204,014 tokens**. Wrapper per-call `queue_ms` telemetry is distinct from durable consultation waiting. These values are not GPU active time, billable usage or proof that no unobserved provider-side work occurred.

## Interpretation boundaries

The five score axes are correlated judgments on the **same** conversation, not five independent replicates. There is one stochastic conversation per profile/model, with no replicate seeds, blinded human calibration, inter-rater agreement or clinical outcome validation. Fixed patient model/profile does not create identical dialogues: its responses change with the clinician's utterances.

The Gemma judge is an **uncalibrated pilot**. Descriptive means and profile-matched differences, if the complete matrix validates, describe only these retained outputs. They do not establish clinical accuracy, statistical significance, a winner, patient safety, or superiority outside this sample. The axis name “Clinical Accuracy & Competence” is a rubric label, not an independently verified medical conclusion.

## Reproduction and preservation

The offline helper reuses `aggregate_workshop` completion identity/count semantics and `run_workshop_batch` exact admission/report checks. It validates the frozen profile×model matrix, ten rounds and role order, nonempty/nontruncated turns, no intervention, turn events, the fixed judge, and exactly five finite scores in [1,6]. It withholds means and paired differences if any expected report is absent or fails. Request identities deduplicate responses; reported retry counts are not reconstructed unique provider attempts. Token usage and response latency are not GPU occupancy or billing.

```bash
python templates/hcls-librechat/scripts/qualification/summarize_workshop_cohort.py \
  --cohort "$Q/workshop-batches/full20-r1" \
  --output "$Q/workshop-analysis-full20-r1/new-summary.json"
```

The output must be new; active runner files are never modified. Fifteen focused tests pass, including missing reports, invalid/nonfinite/boolean scores, mismatched identities, truncation, missing usage and exclusion of private text; Ruff passes. Helper/test source is `10d3309`. The earlier partial checkpoint at 05:48:02 retained 29 validated reports with **no means or paired comparison**. Earlier failed/pilot cohorts are not silently replaced or pooled into this cohort. No additional model/API inference, changed budgets or new admission was used for this analysis.

Protected paths are relative to the campaign evidence root:

- `workshop-analysis-full20-r1/final-0553.json`, SHA-256 `e00befd48c97a98030e3f1edd02d8d970559f45de4ffee0a0c41c57eebc38b29`: cohort-only counts, per-model coverage, every report check, role-specific latency/retry/usage, exact means and all profile-paired differences; binds the frozen manifest, admission, final snapshot and 60 raw reports by SHA-256.
- `workshop-batches/full20-r1/summary.json`, SHA-256 `a7fa3bdc955c724f62fba6cd52349ce1f71c409e1f0ec3d31b3e6029ca3b8f3a`: stable terminal runner summary at 05:53:05, 60 completed/verified. Raw reports and original prior-run evidence remain protected and unchanged.
