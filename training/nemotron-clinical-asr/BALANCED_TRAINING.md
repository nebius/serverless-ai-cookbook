# Renewable English-domain training with measured replay

This opt-in path retains the exact English Nemotron foundation, tokenizer and
native streaming decoder described in the main README. It changes **training
sampling**, not reference text, audio, validation membership or model decoding.
The default 3.5 path is unchanged. A balanced training run is an experiment, not
evidence that a model is clinically safe or better than its foundation.

## Prepare approved, already aligned inputs

Use independently approved training/development splits, with whole conversations
assigned before segmentation. Every row requires an original `id`,
`conversation_id`, `split`, `text`, `audio_filepath` and accurate `duration`.
Clips must be 0.5–30 seconds, mono 16 kHz PCM16 WAV. Preserve original references
and source/license provenance. The builder rejects invalid rows instead of
silently filtering, splitting or normalizing them.

The main README prepares simulated clinical audio and LibriSpeech replay.
`data/prepare_primock_adaptation.py` adds a pinned 40-conversation training /
5-conversation development PriMock57 split, excluding the 12 conversations used
in the documented development comparisons. See [sources and licenses](data/SOURCES.md).
Its output includes `train.jsonl`, `dev.jsonl` and exact human-timed WAV slices.
No source audio or transcripts are distributed in this repository.

Place approved WAVs under a common local root matching the manifest paths below
`/data/clinical-speech`. For example, a manifest path
`/data/clinical-speech/primock-adaptation/audio/clip.wav` maps to
`APPROVED_DATA/primock-adaptation/audio/clip.wav`. The builder verifies every WAV
and existing checksum, requires train/dev conversation and decoded-PCM separation,
and rejects test labels, duplicate IDs and out-of-root symlinks.

```bash
python data/build_training_bundle.py \
  --train-corpus simulated_clinical=APPROVED_DATA/clinical/train.jsonl \
  --train-corpus primock57=APPROVED_DATA/primock-adaptation/train.jsonl \
  --train-corpus librispeech_replay=APPROVED_DATA/replay/train.jsonl \
  --dev-corpus simulated_clinical=APPROVED_DATA/clinical/dev.jsonl \
  --dev-corpus primock57=APPROVED_DATA/primock-adaptation/dev.jsonl \
  --audio-root APPROVED_DATA \
  --output NEW_BUNDLE_DIRECTORY \
  --key-prefix YOUR_FRESH_INPUT_PREFIX \
  --seed 20260926
```

The five outputs are `audio.tar`, `mixed.jsonl`, `clinical-only.jsonl`, `dev.jsonl`
and `bundle.json`. The archive is deterministic and fully read back; metadata
pins every member, input manifest, rebased path and output hash. Original text,
audio, IDs and split membership are retained. LibriSpeech replay must retain its
`librispeech-train-clean100:` conversation provenance, not merely a relabeled
clinical corpus. This builder performs no upload or model call.

Upload these five files to the exact keys recorded in the bundle, with
`bundle.json` at `YOUR_FRESH_INPUT_PREFIX/bundle.json`. Use an authorized,
multipart-capable uploader: the archive may exceed the single-PUT size limit.
Do not use `data/upload_inputs.py` for this large bundled archive. Use a fresh
prefix and verify uploaded bytes by full GET/SHA-256; custom object metadata is
not proof of content identity. Record the local `bundle.json` SHA-256 for the Job.

These commands reproduce a **new approved-input experiment**, not automatically
the historical benchmark: clinical split seeds, exclusions and accepted
alignments must also match to make that stronger claim. No speaker-disjointness
or absence from upstream pretraining is implied.

## Run a fresh smoke, then a separately approved main Job

Build and pin your own public image as in the main README. Use its existing
Serverless Job command, storage-secret selectors and bounded GPU configuration;
replace the Job's application arguments with the following smoke arguments:

```text
cloud-train --bucket YOUR_BUCKET
  --bundle-key YOUR_FRESH_INPUT_PREFIX/bundle.json --bundle-sha256 YOUR_BUNDLE_SHA256
  --run-id YOUR_NEW_SMOKE_RUN --arm mixed --model-family english_specialist
  --max-steps 20 --val-every 20 --checkpoint-every 0
  --batch-duration 120 --accumulate-grad-batches 1 --learning-rate 1.5e-5
  --seed 20260926 --require-replay-by-step 20
  --corpus-duration-fractions '{"simulated_clinical":0.35,"primock57":0.35,"librispeech_replay":0.30}'
  --require-training-corpus simulated_clinical --require-training-corpus primock57
  --require-training-corpus librispeech_replay
```

Join the lines into the CLI's single `--args` value, preserving the JSON quotes.
Use a **new run ID and output prefix for every attempt**. `cloud-train` checks the
bundle and all WAVs before optimization. Reusing an output prefix is rejected.
Configure a finite timeout and capture the exact allocated VM and scratch disk.

For a main experiment, start again from the original foundation, not the smoke
checkpoint. A prospective configuration is 3000 steps, validation every 500,
durable snapshot every 1000 and a four-hour managed cap. Select the lowest WER
on the unchanged full development set; do not select checkpoints from external
or final-test predictions. These are experimental settings, not quality or
completion-time guarantees. No resumed-training claim is made.

For a native paired smoke, add hash-pinned `--evaluation-manifest-key` and
`--evaluation-manifest-sha256` arguments for a small **development-only** cohort;
see [evaluation](EVALUATION.md). Without them, the wrapper trains/exports but does
not automatically perform a native batch/stream test. HTTP, microphone, MCP and
client qualification are separate gates.

## What “balanced” actually guarantees

NeMo's native weighted input mux chooses cuts, not seconds. The calibration uses
`target PCM fraction / mean clip duration` as the cut weight and repeats each
corpus with original IDs. The pinned sampler uses a 400-cut effective bucket
buffer, avoiding the large finite-prefix backlog observed with its default
buffer. No vendor code is patched. Weights are **not exact duration guarantees**.

The runtime retains a maximum 16 cuts per batch and 30 seconds per clip.
`batch_duration=120` is the native stopping threshold, **not a strict padded
tensor cap**: a real eight-cut batch was 120.04 padded seconds. Report actual
padding and GPU peak memory; do not silently reinterpret this as a hard 120-second
bound. The qualified 20-step H200 plumbing smoke used about 17.31 GB peak allocated
GPU memory; this is one smoke observation, not a production sizing guarantee.

Audit `training/corpus-sampling/calibration.json`, `consumption-progress.json`, the
completed-batch ledger, full development CSV and checkpoint provenance. Report
corpus-attributable seconds separately from uniquely matched clips, repetition
and ambiguous same-corpus token/audio matches. A useful prospective main gate is:

- All three corpora consumed by step 50; at least 99% of processed PCM attributable.
- Selected-checkpoint cumulative fractions within 5 percentage points of 35/35/30.
- All three corpora present and replay between 10–50% in **every completed**
  50-step window, including windows after the selected checkpoint.
- Contiguous actual optimizer-step evidence, finite losses and validation, and
  measured allocator/padding limits fixed before the run.

The runtime's early corpus guard is not a substitute for this post-run audit.
Compare the selected model to the **same untuned English foundation**, with
identical audio, decoding, word/clinical-entity metrics and uncertainty. Review
medication, dose and negation errors and unsupported additions explicitly;
unchanged or improved aggregate WER cannot establish clinical safety. Balancing
does not teach drug names absent from the training material. Keep final tests
sealed until known-quality and critical-error gates pass.

After terminal publication, verify the exact Job VM and scratch disk are gone;
retain immutable object-storage artifacts. Preserve existing serving resources.
Only create a separate candidate endpoint after quality gates, then qualify its
API/MCP/live-stream cancellation and client workflows before any promotion.
