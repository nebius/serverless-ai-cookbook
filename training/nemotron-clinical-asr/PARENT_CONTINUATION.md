# Continue adapting an English Nemotron checkpoint

Use this optional path when you have an existing English Nemotron `.nemo`
checkpoint and additional approved, human-transcribed domain audio. It retains
the pinned English architecture and tokenizer; it does not convert a 3.5 model
into the English family. The default fresh-foundation workflow is unchanged.

This guide describes an experimental workflow, not a clinically validated model.
A checkpoint hash establishes identity, not permission to use its training data,
absence of PHI, or quality. Review the model and dataset licenses separately.

## Freeze inputs and comparisons first

Prepare the train/dev bundle using [the balanced-training guide](BALANCED_TRAINING.md).
Keep conversation boundaries, original references, waveform hashes and source
attribution. For additional speaker-labeled narration, split speakers before
training and document any repeated prompts across splits. A held-out speaker
with a shared prompt is not a prompt-disjoint benchmark. A vendor's public test
set used for training must be retired as an independent benchmark for that run.

For your own corpus, give it its real `training_corpus` name in the bundle and
duration-fraction map; do not relabel it as PriMock or another published source.
The current `--require-training-corpus` early guard accepts only the named
recipe corpora (`simulated_clinical`, `primock57`, `librispeech_replay`,
`eka_medical_narration`). Custom names work in the sampling map but need an
explicit post-run exposure audit; that early guard cannot verify them.

Upload only approved inputs and the parent checkpoint to your private bucket,
using fresh object keys and full-GET SHA-256 verification. Keep held-out final
test audio outside the training archive. Freeze the selection rule, decoding,
general-English regression limits and critical-word/meaning review before
training. Never select a checkpoint by watching the final test score.

## Start with a real GPU smoke

Build a new immutable image from this recipe. Use the bounded **new** Serverless
Job allocation and secret injection in the main README. For the three-corpus
example bundle from the balanced guide, use these application arguments:

```text
cloud-train --bucket YOUR_BUCKET
  --bundle-key YOUR_FRESH_INPUT_PREFIX/bundle.json --bundle-sha256 YOUR_BUNDLE_SHA256
  --run-id YOUR_NEW_CONTINUATION_SMOKE --arm mixed --model-family english_specialist
  --initial-checkpoint-key YOUR_PINNED_PARENT_KEY
  --initial-checkpoint-sha256 YOUR_PARENT_SHA256
  --max-steps 20 --val-every 20 --checkpoint-every 0
  --batch-duration 120 --accumulate-grad-batches 1 --learning-rate 5e-6
  --seed 20260926 --require-replay-by-step 20
  --corpus-duration-fractions '{"simulated_clinical":0.35,"primock57":0.35,"librispeech_replay":0.30}'
  --require-training-corpus simulated_clinical --require-training-corpus primock57
  --require-training-corpus librispeech_replay
```

Join the lines into the Job's single `--args` value, preserving JSON quotes.
Use the names and fractions of **every and only** corpus actually in your bundle.
The example learning rate and fractions are starting settings, not an optimum.
To run a paired native transcription smoke after export, also supply the
hash-pinned development-only evaluation manifest described in [EVALUATION.md](EVALUATION.md).
Without that manifest, successful training does not imply an inference test.

Before any optimizer update, the runtime checks the parent's full-file hash,
native model class, actual serialized tokenizer, architecture configuration,
state keys/shapes/dtypes and finite weights. It then measures the parent on the
entire supplied development set using a separate validation-only Trainer.
That baseline does not enter candidate checkpoint selection.

The new training Trainer starts a fresh optimizer, scheduler, step counter and
consumption ledger. `--initial-checkpoint` and `--resume-pointer` cannot be
combined. The old parent's training exposure is not included in the new ledger;
retain its historical provenance separately. The downloaded parent is not
republished as a duplicate output artifact.

Audit the smoke's actual baseline coverage, 20 optimizer updates, finite full
post-training validation, export/reload and any requested native predictions.
Check exact source consumption, padding and GPU memory, not just manifest counts.
A 20-step run does not establish the main run's long-run sampling fractions,
accuracy, HTTP/MCP behavior or microphone readiness.

## Main continuation and release

Only after the smoke works, submit a separate new Job from the **same original
parent**, not the smoke checkpoint. A prospective experiment can use 1,000 steps,
validation every 250, durable snapshots every 500 and a two-hour timeout. Change
the early exposure deadline to 50 steps. Keep the training/dev bundle and parent
hash fixed. Select minimum finite full-dev WER, with ties resolved to the earliest
checkpoint; the parent baseline remains a comparator, not a candidate.

Retain `training/initial-parent-development-baseline.json`,
`training/training-provenance.json`, the development CSV, wall times, exported
checkpoint hash and completed-batch consumption ledger. Report real PCM exposure
per corpus, speaker concentration, repeated examples and ambiguous matches.
Target weights describe expected sampling shares, not guaranteed exposure.

Compare untuned foundation, original parent and selected candidate on identical
audio with identical native decoding. Report word errors, medical/entity errors,
deletions, blanks and medication/dose/negation meaning changes. New training data,
parent weights, learning rate and update count can all change; do not attribute
improvement to one factor without a controlled comparison. Known development
gains are not held-out final-test or clinical safety evidence.

After quality review, serve the exact selected `.nemo` hash using the existing
[Serverless Endpoint instructions](README.md#serverless-endpoint), adding
`--env MODEL_FAMILY=english_specialist` to that command. The compatibility
default is 3.5: omitting this setting selects the wrong family and the restored
class check fails closed. At 560 ms, English uses native context `[70,6]`, not
3.5's `[56,6]`. Keep the exact checkpoint key/SHA, authentication and a fresh
state prefix; confirm the English family and checkpoint via authenticated
`/v1/models`. Requalify batch HTTP, native streaming, cancellation/recovery and
MCP for this checkpoint.
Speaker diarization is a separate model, not a capability learned by this ASR
training. Keep synthetic/de-identified demo inputs and clinician review explicit.

When each training Job terminates, verify its exact allocated VM and scratch
disks are released; retain the immutable training artifacts. Do not stop or
replace existing serving endpoints as part of training cleanup.
