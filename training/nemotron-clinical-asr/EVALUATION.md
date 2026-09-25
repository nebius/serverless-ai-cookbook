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
`audio_filepath` under `/data/clinical-speech`. Only referenced audio is staged
from the same bucket. Optional `audio_sha256` is verified; `source_audio_sha256`
is not substituted because it can refer to a longer original recording. IDs,
split labels, exposure labels and original reference bytes are retained.

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
