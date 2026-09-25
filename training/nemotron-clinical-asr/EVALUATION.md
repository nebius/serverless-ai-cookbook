# Evaluate frozen cohorts in a separate Job

Use `cloud-run --mode align-train` for the bounded training Job. After its
`completed.json` is published, take the actual `.nemo` object key and SHA256 from
that verified receipt. Run `cloud-evaluate` as a separate Serverless Job using
the same image, bucket-only secret injection, GPU and environment conventions.
This keeps inference and publication time outside the training Job allowance.

```bash
python -m clinical_asr cloud-evaluate \
  --bucket "$DATA_BUCKET" \
  --run-id clinical-evaluation-v1 \
  --checkpoint-key runs/clinical-training-v1/training/nemotron-clinical-en.nemo \
  --checkpoint-sha256 "$CHECKPOINT_SHA256" \
  --evaluation-manifest-key manifests/eval-clinical-dev-v1.jsonl \
  --evaluation-manifest-sha256 "$CLINICAL_MANIFEST_SHA256" \
  --evaluation-manifest-key manifests/eval-external-heldout-v1.jsonl \
  --evaluation-manifest-sha256 "$EXTERNAL_MANIFEST_SHA256" \
  --evaluation-manifest-key manifests/eval-general-english-v1.jsonl \
  --evaluation-manifest-sha256 "$GENERAL_MANIFEST_SHA256"
```

Each manifest must be frozen **before examining this candidate's predictions**.
Keys and SHA256 arguments are paired in their supplied order. Each key's filename
stem becomes its output directory and must be unique. Every manifest row must
have a unique string `id`, reference `text`, `duration` and canonical
`audio_filepath` under `/data/clinical-speech`, and a frozen `audio_sha256` for
that exact clip. Only referenced audio is staged from the same bucket and each
hash is verified before inference. `source_audio_sha256` is not substituted
because it can refer to a longer original recording. IDs,
split labels, exposure labels and original reference bytes are retained.

If an older frozen manifest lacks clip hashes, publish an explicitly versioned
new manifest that adds hashes from an independently audited audio inventory.
Retain exactly the old IDs, references and audio membership, and record the old
manifest's hash and the metadata-only transformation. Do not silently edit an
existing frozen manifest or derive this update from candidate predictions.

The evaluator uses the same pinned base, runtime, decoding settings and exact
audio for base and adapted checkpoints. **All rows** are evaluated; no implicit
12-row limit applies. Each cohort receives separate `references.jsonl`,
`cohort-provenance.json`, `base-predictions.jsonl`, `tuned-predictions.jsonl` and
prediction provenance. Each prediction records actual checkpoint and audio
hashes. Do not combine development/checkpoint-selection data with independent
held-out test data when reporting quality.

Outputs are uploaded with bounded concurrency and full GET/SHA256 readback.
`runs/<run-id>/completed.json` is published only after every output verifies.
A failed or incomplete run is not promotable. Evaluation completion means
predictions were produced, **not** that quality improved or clinical validation
passed. Score the separate pairs with the packaged evaluation scorer, including
degradations, blank outputs and unsupported keyword insertions.

The same repeatable manifest/SHA options can optionally be supplied to
`cloud-run --mode align-train-evaluate`. Without those options, that mode retains
the original **12-development-clip plumbing smoke**, not a representative
clinical benchmark. Prefer separate Jobs for the larger cohorts.

This command performs one offline, unpaced inference pass per model/cohort.
It is not a repeated latency benchmark or a measurement of microphone latency.
Cold model load, cold first request, warm throughput and paced-stream finalization
must be measured separately, with at least three retained repetitions before
making performance claims.

## Measured experiment: September 25, 2026

A bounded H200 Serverless Job completed 500 full-parameter training steps and
exported the checkpoint selected at step 500. A separate H200 Job completed
native base/adapted inference at 11:00:32 UTC. An independent audit checked the
published outputs, frozen references, all 631 exact input WAV hashes, prediction
order and model/runtime identities, then recomputed the scores below. All 1,262
predictions are retained, including blanks and regressions. No cohort is pooled
with another and no prediction-based example filtering is applied.

### Retained historical six-cohort report — assembly correction below

The following table preserves the original report. A later independent review
found that the batch evaluator inserted a space between native final fragments,
even when a fragment ended mid-word. For example, `naus` + `ea and vomiting`
became `naus ea and vomiting`. The original integrity audit mirrored that
implementation and did not establish the native text-assembly contract. Use the
explicitly versioned corrected scores below for model comparison, not the
superseded WER/KER values in this historical table.

WER and keyword error rate (KER) are percentages; lower is better. Each arrow is
**base → adapted**. Words and keyword occurrences are the respective scoring
denominators; zero keywords means KER is undefined, not perfect. Audio duration
is shown to three decimal places.

| Cohort | Clips | Audio seconds | Reference words | Keyword occurrences | WER % | KER % | Blank outputs |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Enriched development, all 27 dev conversations | 239 | 884.400 | 2,528 | 79 | 16.38 → 10.56 | 16.46 → 1.27 | 12 → 1 |
| External PriMock, two role-play conversations | 141 | 483.905 | 1,387 | 13 | 17.74 → 19.18 **worse** | 38.46 → 23.08 | 1 → 0 |
| General English, LibriSpeech test-clean subset | 242 | 1,801.370 | 5,033 | 0 | 3.79 → 5.11 **worse** | undefined | 0 → 0 |
| Three pre-frozen training candidates, mixed exposure | 3 | 19.440 | 37 | 2 | 18.92 → 13.51 | 100.00 → 50.00 | 0 → 0 |
| Five reference-term-enriched, verified consumed training clips | 5 | 60.240 | 178 | 34 | 15.17 → 8.43 | 38.24 → 0.00 | 0 → 0 |
| One training-source medication/dose/negation illustration | 1 | 18.400 | 39 | 2 | 25.64 → 12.82 | 50.00 → 50.00 | 0 → 0 |

### Corrected native-fragment assembly, same historical inference

The pinned native NeMo pipeline accumulates finalized fragments verbatim. The
`native_final_concat_v1` evaluator now uses exact concatenation, trimming only
outside whitespace; it does not insert word separators or repair native text.
An offline rescore reused all original model events, references, audio, models
and the unchanged lexical scorer. **No new inference or training produced these
differences.** Original prediction files and the historical report remain
retained; corrected predictions and a separate receipt identify the derivation.

The cohort memberships, word/keyword denominators, durations and blank counts
are exactly those in the historical table above.

| Cohort | Corrected WER %, base → adapted | Corrected KER %, base → adapted |
| --- | --- | --- |
| Enriched development, 239 clips | 16.42 → 10.48 | 16.46 → 0.00 |
| External PriMock, 141 clips | 17.66 → 19.11 **worse** | 38.46 → 23.08 |
| General English, 242 clips | 3.76 → 5.07 **worse** | undefined |
| Three training candidates, mixed exposure | 18.92 → 13.51 | 100.00 → 50.00 |
| Five verified consumed training clips | 15.17 → 8.43 | 38.24 → 0.00 |
| One training-source dose illustration | 25.64 → 12.82 | 50.00 → 50.00 |

The separate rescore receipt SHA256 is
`e28231c8b4352843631e69dca6d57ce5b628a9f0f2941e555bf1640597b9523f`;
the unchanged scorer SHA256 is
`395878d7aafc72628d861e00489b5d0a0a31c8adcad84711afe77dd11a4dd664`.
An independent review reproduced all 12 model/cohort groups and verified that
the 18 original reference/prediction source hashes were unchanged. External and
general regressions remain after correction, but individual lexical errors
introduced by the former assembler must not be attributed to fine-tuning.

The development gain is not an independent generalization result: development
also selected the checkpoint, and the scored subset was enriched using a frozen
reference-only medical-term rule. External PriMock was excluded from fine-tuning
but had prior integration exposure; it is not a blind test. Original base-model
pretraining exposure is unknown. General-English test-clean was never training
replay. Neither small external subset supports a population-wide claim.

The last three rows are illustrations, not held-out tests. Of the three original
training candidates, two are verified exact consumed clips and one is not
uniquely proven consumed. All five enriched clips are verified consumed before
the selected checkpoint. The new dose cut itself was not a training row; 22 of
its 39 source words overlap verified consumed training spans. These exposure
labels were determined before candidate predictions, not chosen by score.

WER uses NFKC/lowercase word edit distance without spoken-number or synonym
expansion. KER checks complete aligned lexical spans, not medical entity meaning.
No `<unk>` predictions occurred; the blank predictions above remain scoring
errors, not discarded samples. The `collapse_warning` field flags each blank or
`<unk>` output; a flagged clip is not proof of model-wide collapse. Both dose
hypotheses say "four hundred milligrams" where the reference says "400 milligrams".
Both fail the frozen literal numeric-keyword check because of spelling format;
this is **not a wrong-dose finding** or semantic dose adjudication.
Pronunciation, doses, negation, speaker
attribution and clinical safety still require audio-linked human review.

### Training exposure and interpretation

Training used batch-duration 120 seconds, gradient accumulation 1, learning rate
`1e-4`, BF16, validation every 100 steps and durable optimizer snapshots every
200 steps. The selected checkpoint's completed-batch ledger records 7.343 hours
of processed audio, not the entire 51.910-hour source corpus. The 10.003-hour
replay manifest was appended after the clinical rows, but the bounded loader
buffer never reached it: **zero replay examples were consumed**, including all
ambiguous ledger candidates. This is a short clinical-only fine-tune, not a
replay-regularized model.

Full-manifest mixing was subsequently corrected in source
`751b35fb50243c9618aeebee558b156a5a4d6ecc`, with 72 CPU/runtime unit tests passing.
At the original publication, that correction had not been used in a new GPU
training run. Subsequent runs require their own selected-checkpoint exposure
audit and do not retroactively change this checkpoint. Do not attribute the development gain
or the external/general regressions to a tested replay strategy. The result
demonstrates why domain adaptation needs separate development, external clinical
and general-regression checks, not a blanket “better for healthcare” claim.

### Exact evidence binding

Both models used the pinned NeMo revision from the README, H200, PyTorch
2.8.0+cu128, FP32 greedy-batch inference, `en-US`, 560 ms chunks and native
`[56,6]` cache-aware context. Same-cohort audio and decoding settings matched.
The experiment was one unpaced inference pass per model/cohort, **not** a repeated
live-latency benchmark. Image identity is bound by the recorded immutable-digest
submission/build receipts, not independently attested by the Python runtime.

| Identity | Value |
| --- | --- |
| Training source commit | `32d8b5911a5739d681ad9b5fd422ec7b743da908` |
| Training image digest | `sha256:357b5e006cf6fad3c9ff0d7edd2a76ee0a4061e4286ffbb6cee826b4c7a00b91` |
| Evaluation image source commit | `95cd8a7706e70f5a6a806598f36fb903ffee85a2` |
| Evaluation image digest | `sha256:e1f3803a409045d5cad3040bdade3a4fbd63f60f1b9c583fe6fd2c090f334270` |
| Base `.nemo` SHA256 | `210214ed94039bf6bfbb9a047c7fa289628db75b103e2bf6381fa78285436a74` |
| Adapted `.nemo` SHA256 | `dfef5379788f983a2829b8d350e7eeaeb41d7b42751e88df21885a9d2a10bb15` |
| Raw evaluation publication SHA256 | `9062d631f841f5bc8b72928d967361ef498e7b899450a937d329bb9d9a9cabac` |
| Independent audit SHA256 | `4a5cedd973d128026ec3d3a83334609556d18e95a3d879a5d6981fe5f9a825b5` |

These hashes identify retained experiment artifacts, not downloadable weights or
private-resource dependencies supplied by this checkout. Use the public data and
preparation instructions to run your own experiment and retain its own complete
receipts; the documented public split seed need not reproduce this historical
split. Later source/docs commits do not retroactively qualify a different image.
Existing evidence bound to `751b35f` remains unchanged by this results summary.

Both training and evaluation Jobs reached terminal completion; exact-ID Compute
VM and scratch-disk GETs confirmed automatic release. Model and audit artifacts
were retained. This qualifies the bounded training/export/evaluation path, not
interrupted-worker recovery, autoscaling, the browser workflow, clinical safety
or PHI handling. No listening/pronunciation adjudication, clinician sign-off or
real-PHI processing was performed.

## Follow-up controlled runs: both rejected

Two subsequent fresh Nemotron 3.5 runs each completed 500 full-parameter steps,
using the same upstream base, seed, learning rate `1e-4`, batch-duration120,
accumulation1 and validation/checkpoint schedule. One used globally mixed clinical
and general-English data; the control used clinical data only. Each selected
step500. All three known-cohort base/candidate pairs used native exact fragment
concatenation, matched FP32/560ms H200 inference and the same frozen audio.

| Known selection cohort | Upstream3.5 WER% | Clinical-only control WER% | Replay-mixed WER% | Frozen maximum WER% |
| --- | ---: | ---: | ---: | ---: |
| Clinical dev239, 2,528 words | 16.42 | 10.28 | 12.06 | 11.00 |
| External141, 1,387 words | 17.66 | 19.39 | 18.82 | 18.16 |
| General242, 5,033 words | 3.76 | 4.85 | 4.17 | 4.01 |

Both candidates are **rejected by known quality gates**, not pending promotion.
Neither was evaluated on the sealed final tests or deployed. No failed/blank
output was removed: base/control/mixed blanks were12/3/3 on dev,1/1/5 on external,
and0/0/0 on general. Clinical keyword errors were13/0/3 out of79 on dev and5/3/2
out of13 on external; these lexical counts do not establish safe medical meaning.

The selected-checkpoint consumption audit independently reconstructed native
reference-token hashes and the complete inverse candidate sets, verified all500
completed steps, and retained ambiguous matches. Control consumed7.371432 hours
of clinical audio. Mixed consumed4.224429 hours clinical and2.857071 hours general
replay:40.3456% replay by PCM samples, with positive replay in every completed
50-step window after warmup and100% domain-attributable samples. This proves
actual replay exposure in these new weights, unlike the original experiment.
It does not prove replay alone caused the score differences: optimizer steps
match, but clinical hours and individual examples differ between arms.

| Evidence | Clinical-only control | Replay-mixed |
| --- | --- | --- |
| Adapted `.nemo` SHA256 | `eeb7209093dc638111a67a72c6b29299c05e0bf4ed4d1c192f4643cb14c51069` | `788b26aaf3c06abb7b04f778e2340939a663779dfb335aac301739b82784b960` |
| Independent artifact/metric audit SHA256 | `1fc551321ef9098a6108538565a418d14235648d0babbbd025952181c43a078f` | `8814504fc63498dc2ca8b255ae321db49e2e4f3f49fd22cb744b5085a71a341e` |

Both used source `4a442c08b6d96987414ce659f934c078b05e90d6` and a new unique
image tag verified before launch against digest
`sha256:a46f303c72cc8b3e919e126dafde7ba21e1c3403255de4f5749b4fd8dbeb0ee7`.
Host logs did not expose the resolved pulled digest, so direct runtime-image
attestation is **not claimed**. This limitation was not waived for promotion.
Both Jobs completed and exact-ID GETs confirmed their temporary VMs and scratch
disks were released; original serving resources were unchanged.

## Separate English-foundation comparison

A separate immutable-image evaluation compared the untuned English-specialist
Nemotron foundation with upstream3.5 and the original served adapted3.5 model.
It did not fine-tune English. All rows and failures were retained, with one
unpaced inference pass per model/cohort; native left context differs intentionally
between the English architecture (`[70,6]`) and multilingual3.5 (`[56,6]`).

| Cohort | Upstream3.5 WER% | Original adapted3.5 WER% | Untuned English WER% |
| --- | ---: | ---: | ---: |
| Known clinical dev239 | 16.42 | 10.48 | 13.92 |
| Known external141 | 17.66 | 19.11 | 13.19 |
| Known general242 | 3.76 | 5.07 | 2.76 |
| Expanded external828, 10 role-play conversations, 8,863 words | 15.76 | 15.84 | 12.10 |

Expanded external keyword errors were37/33/17 out of109 respectively; blanks
were11/9/17. English therefore improved measured external/general recognition,
but it did not dominate every metric, and its17 short-clip blanks remain errors.
The expanded cohort was frozen before these predictions and excluded from the
adaptation datasets; it is now known selection evidence, not a fresh final test.
Speaker independence and absence from model pretraining are not established.
Meaningful medication, dose, polarity and conditional-scope errors remain in all
three models. These scores do not qualify any model for unattended clinical use.

The English foundation is pinned to revision
`ebe59e5a817142986528bbbee5dba8db7b38ed50`, checkpoint SHA256
`283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd`.
The independent comparison audit SHA256 is
`812bff5b3749c947a737aa8b07faf7464c98fa2bcbf00e90aa41bf6881faec57`.
Its submitted image digest was
`sha256:d2b4649d3a59a2f8138abf225c33b42a51befd266956a70ade3d193ecf069d5c`,
source `654a05f34be32cbdae47e7d01c3861b43737e6fd`. The actual admitted API image
reference matched the immutable submission; this is not host-level attestation.
The temporary comparison VM and scratch disk were released after completion.
Any future English adaptation must compare with this matched English base and
separate architecture gains from actual fine-tuning gains.
