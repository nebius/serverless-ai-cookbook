---
title: Fine-tune and Serve Clinical Nemotron Speech
category: training
type: workflow
runtime: gpu
frameworks:
  - nemo
  - pytorch
  - fastapi
keywords:
  - speech-to-text
  - clinical-evaluation
  - streaming
  - finetuning
  - object-storage
  - mcp
difficulty: advanced
---

# Clinical-domain Nemotron Speech on Serverless Jobs and Endpoints

This recipe adapts **Nemotron 3.5 ASR Streaming 0.6B**, saves a real `.nemo`
checkpoint, and serves that checkpoint through batch HTTP, native WebSocket
streaming and typed MCP tools. It does not substitute generated transcript text
for model inference. All work is isolated in new resources; existing applications,
instances and endpoints need not change.

This is an experimental implementation, not a clinically validated model or a
medical device. A successful ten-step smoke job proves plumbing—not improved
accuracy. Do not label a checkpoint “better for healthcare” until paired held-out
results demonstrate that. PHI use is not approved by this recipe. Start with
simulated or appropriately de-identified inputs and clinician-reviewed drafts.

## Reproducible components

| Component | Exact revision |
| --- | --- |
| ASR model | `nvidia/nemotron-3.5-asr-streaming-0.6b@ea30d66debe3740a08b573244286791d423d6b3e` |
| Model license | OpenMDW 1.1; review upstream terms before redistribution |
| NeMo | `3b08b2acacc13ec1268e53653346266202b2335f` |
| PyTorch/CUDA | PyTorch 2.8.0, CUDA 12.8 |
| Alignment-only model | `nvidia/parakeet-ctc-0.6b@ad09ba1cc62743fbc9814de5d2016fca9096485a`, CC BY 4.0 |
| Dependency lock | `requirements.lock`: full pinned package set with hashes |

The CTC model is a **forced aligner of original human transcripts**, not the
model being fine-tuned and not a source of pseudo-labels. The Nemotron tokenizer,
encoder, language-prompt dictionary and decoder are retained. Model serving
restores the actual adapted checkpoint and reports its SHA-256.

Primary references: [Nemotron model card](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b),
[NVIDIA fine-tuning tutorial](https://huggingface.co/blog/nvidia/fine-tuning-nemotron-35-asr),
[pinned NeMo fine-tuning code](https://github.com/NVIDIA/NeMo/blob/3b08b2acacc13ec1268e53653346266202b2335f/examples/asr/speech_to_text_finetune.py),
[pinned native streaming pipeline](https://github.com/NVIDIA/NeMo/tree/3b08b2acacc13ec1268e53653346266202b2335f/nemo/collections/asr/inference),
[NVIDIA Parakeet CTC model card](https://huggingface.co/nvidia/parakeet-ctc-0.6b).

## Build and compute

Build from this directory with the public Dockerfile:

```bash
docker buildx build --platform linux/amd64 -t YOUR_REGISTRY/clinical-asr:YOUR_VERSION --push .
```

Resolve the pushed image digest and use `YOUR_REGISTRY/clinical-asr@sha256:...` in
every Job/Endpoint definition. No private base image is required. Record the exact
built image digest in the run evidence; a new image requires its own runtime
qualification, including imports and execution as the Dockerfile's default user.

Initial smoke target: one H100/H200, 16 vCPU, roughly 200 GiB host memory, 250 GiB
scratch, regular capacity, finite Job timeout. This is a starting allocation,
not a measured minimum. Serving is one GPU, one process, one replica, one active
inference at a time; qualify an L40S only after measured load/peak-memory checks.
GPU driver compatibility with CUDA 12.8 must be verified. Downloads are enabled;
set `HF_HUB_OFFLINE=0` if inheriting an image that disables Hugging Face access.

## Data contract

Source JSONL contains:

```json
{"audio_filepath":"/data/clinical-speech/prepared/audio/EXAMPLE.wav","duration":430.2,"text":"Original human transcript ...","conversation_id":"EXAMPLE","split":"train","lang":"en-US","target_lang":"en-US"}
```

Use 16 kHz mono PCM16 WAV. Split **whole conversations before alignment** into
train/dev/test. Do not use test references for training, selection or vocabulary
choices. The source simulated medical corpus is advertised as approximately
55 hours; the audited audio totals 51.910 hours across 272 conversations. Keep
source license, hashes, decoding fixes and transcript provenance with the data.
Case, punctuation and original source targets remain auditable. Human transcripts
are not proof that every word is verbatim: review alignment and selected examples.

`align` uses NVIDIA Forced Aligner on the full original human transcript. `segment`
reconciles every CTM word against the source before cutting 0.5–30 second WAVs at
word boundaries. Token mismatches fail for review; the implementation never
divides audio proportionally to text. Speaker labels are not learned by this ASR
recipe. Segments retain conversation IDs, original spans and pending review flags.

Optional replay uses already paired short LibriSpeech **train-clean-100**
utterances only, explicitly lowercased training targets with raw uppercase source
retained in provenance. General-English test-clean stays evaluation-only. The
replay proportion and any regression must be measured, not presumed beneficial.

### Prepare public inputs from a clean checkout

The CPU-side scripts below need Python 3.12+ and `ffmpeg`/`ffprobe` on `PATH`.
They do not require PyTorch or a GPU. [Source and license details](data/SOURCES.md)
include pinned archive hashes and attribution. No audio or private credentials
are included in the checkout. Set `ASR_DATA_DIR` to a **new, dedicated** local data
directory outside the source checkout; allow space for archives, extraction and
16 kHz WAVs. Clinical download is about 1 GB; optional replay downloads add about 7 GB.

```bash
python data/download_public.py --dataset clinical --data-root "$ASR_DATA_DIR"
python data/prepare_corpus.py --root "$ASR_DATA_DIR" --seed clinical-asr-v1
```

This verifies the original CC0 archive, handles UTF-16 transcripts, preserves
source case/punctuation and warnings, converts audio, and creates:

- `prepared/audio/*.wav` and auditable speaker-marked source turns;
- frozen `manifests/conversation-splits.json` (whole-conversation 80/10/10);
- `manifests/{train,dev,test}-nfa.jsonl` and `train-dev-alignment.jsonl`;
- `manifests/pilot-alignment.jsonl`: four shortest train and two shortest dev
  conversations, selected before alignment or any ASR predictions;
- `provenance.json` with hashes, licenses, actual durations and warnings.

Preparation refuses to replace different frozen manifests. The default public
seed is explicit; it need not reproduce a separately reported experiment's
seed. Never change a test split after looking at predictions. The retained
`test-nfa.jsonl` is **not** part of the train/dev alignment Job.

Optional general-English replay and regression:

```bash
python data/download_public.py --dataset replay-train --data-root "$ASR_DATA_DIR"
python data/download_public.py --dataset general-test --data-root "$ASR_DATA_DIR"
python data/prepare_replay.py --data-root "$ASR_DATA_DIR" --train-hours 10 \
  --pilot-train-hours 2 --regression-minutes 30 --seed clinical-asr-replay-v1
```

Outputs are `replay-train.jsonl`, `replay-train-pilot.jsonl`,
`general-test-clean.jsonl` and `general-test-clean-pilot.jsonl` in `manifests/`.
Only the first two may enter training. Native utterances outside 0.5–30 seconds
are excluded and counted. Lowercased targets do not fabricate punctuation.

Optional external clinical evaluation uses two pinned PriMock consultations:

```bash
python data/download_public.py --dataset primock-sample --data-root "$ASR_DATA_DIR"
python data/prepare_external.py --data-root "$ASR_DATA_DIR"
```

The downloader resolves actual Git LFS audio and checks its SHA-256. Preparation
cuts original human-TextGrid intervals into `external-test-utterances.jsonl`,
retaining the CC BY license and exclusions. This is not the full 57-consultation
dataset and not mixed-speaker diarization; never use it for training or model
selection in this experiment.

## Serverless Job

Upload only required prepared files at a private bucket root. The manifest
paths map to bucket keys by stripping `/data/clinical-speech/`. Use a new scoped
service account/secret and a new Job; do not reuse or modify running instances.

Inject `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` through runtime secrets, and
set `AWS_ENDPOINT_URL` to the bucket region's Object Storage endpoint. Credentials
must not appear in images, manifests, shell history or evidence. Cross-region
Jobs stage data with S3 to local disk; no cross-region FUSE mount is required.

After creating your own bucket-scoped credential through the supported cloud
workflow, configure it through the standard AWS credential provider chain, not
command-line values. The optional uploader needs only `boto3==1.42.49` in the
local preparation environment, not the full GPU dependency lock:

```bash
python -m pip install boto3==1.42.49
python data/upload_inputs.py --data-root "$ASR_DATA_DIR" --bucket "$ASR_BUCKET" \
  --manifest manifests/pilot-alignment.jsonl \
  --provenance provenance.json --provenance manifests/conversation-splits.json \
  --receipt "$ASR_DATA_DIR/pilot-upload-receipt.json"
```

This is a cloud write to your explicitly chosen bucket. It uploads the named
manifest, only its referenced WAVs and explicit provenance; never raw archives,
private files or the entire working directory. Existing mismatches fail closed;
every object gets a create-only PUT and full-GET SHA-256 verification. For a full
run repeat `--manifest` for `train-dev-alignment.jsonl` and the chosen replay
manifest, and use a new receipt path. Preserve the dataset license/provenance
files with replay/external artifacts as well.

Container arguments for the first real GPU smoke:

```text
cloud-run --bucket YOUR_PRIVATE_BUCKET --run-id pilot-UNIQUE
  --manifest-key manifests/pilot-alignment.jsonl
  --max-steps 10 --val-every 5
  --batch-duration 30 --accumulate-grad-batches 1
  --checkpoint-every 10
```

After checking your installed Nebius CLI help, set non-secret IDs and
`ASR_IMAGE_REF` to your immutable image reference. An early submission in this
work recorded a Compute-label length error for a long digest-form image string;
this was not an OCI syntax error, and was not re-tested on CLI0.12.280. If that
specific compatibility issue occurs, use a **new unique short tag**, verify its
registry digest immediately before submission, record the digest and never
overwrite the tag. A floating `latest` tag is not an equivalent workaround.
These commands create billable **new** resources:

```bash
nebius ai job create \
  --parent-id "$ASR_PROJECT_ID" --subnet-id "$ASR_SUBNET_ID" \
  --name "$ASR_NEW_JOB_NAME" --image "$ASR_IMAGE_REF" \
  --platform gpu-h200-sxm --preset 1gpu-16vcpu-200gb \
  --disk-size 250Gi --shm-size 16Gi --timeout 1h --restart-policy never \
  --args "cloud-run --bucket $ASR_BUCKET --run-id $ASR_RUN_ID --manifest-key manifests/pilot-alignment.jsonl --max-steps 10 --val-every 5 --checkpoint-every 10" \
  --env "AWS_ENDPOINT_URL=$ASR_S3_ENDPOINT" --env HF_HUB_OFFLINE=0 \
  --env-secret "AWS_ACCESS_KEY_ID=$ASR_STORAGE_SECRET_ID" \
  --env-secret "AWS_SECRET_ACCESS_KEY=$ASR_STORAGE_SECRET_ID"
```

The storage secret has payload keys `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`; the registry may also require `--registry-secret` with
`REGISTRY_USERNAME`/`REGISTRY_PASSWORD`. Verify installed CLI help, platform,
project quota, secret access and region before creation. Do not use a floating tag.

These arguments run alignment → segmentation → full-parameter training → paired
12-segment base/adapted dev predictions. `--mode align` stops before training;
`--mode align-train` skips the prediction smoke. Longer training should use the
full train/dev alignment manifest, a justified step budget and
`--replay-manifest-key manifests/replay-train.jsonl` if replay is chosen.

The wrapper uploads logs, manifests, word CTMs, segment WAVs, resolved model
config, `.nemo`, provenance and predictions under `runs/RUN_ID/`. Each upload is
verified by **full GET readback SHA-256**, not custom S3 metadata. `completed.json`
is published last only after all stages and uploads succeed; `failed.json` retains
diagnostics on ordinary failures. Sudden machine loss cannot run `finally`.

For longer/preemptible runs enable `--checkpoint-every N`. This saves and uploads
full Lightning optimizer state and publishes `runs/RUN_ID/resume/latest.json`
only after readback verification. Resume explicitly with
`--resume-pointer runs/RUN_ID/resume/latest.json` and the **same run ID/data paths**
and training settings. Base and manifest hashes must match. This path still needs
an actual interrupted/resumed GPU qualification; do not claim tested recovery
from local unit tests. Static review also identified a recovery limitation: a
restored Lightning callback can retain an earlier best-checkpoint file path that
does not exist on a replacement worker. This implementation does not separately
restore that earlier best file; if subsequent validation never replaces it,
final selected-checkpoint export can fail. Do not present snapshots as an
end-to-end recovery guarantee. Use bounded uninterrupted regular-capacity Jobs
for the qualified training path until replacement-worker recovery is tested.
Periodic snapshots introduce storage/transfer overhead.
`--upload-lightning-checkpoints` separately copies all local optimizer snapshots
again during final publication; it is not needed for the periodic recovery
pointer. Leave it off unless you specifically need those additional retained
copies. Keep `.nemo`, provenance and verified recovery snapshots.

Manual stage commands are also supported:

```text
align --manifest /data/clinical-speech/manifests/pilot-alignment.jsonl --output /output/alignment
segment --source-manifest /data/clinical-speech/manifests/pilot-alignment.jsonl --alignment-dir /output/alignment --output /output/segments
train --train-manifest /output/segments/train.jsonl --dev-manifest /output/segments/dev.jsonl --output /output/train --max-steps 10 --val-every 5 --accumulate-grad-batches 1
```

No package installation or source checkout happens inside the training job.

## Evaluation and promotion

For complete frozen cohorts, prefer a separate bounded Serverless Job using
[`cloud-evaluate`](EVALUATION.md). It verifies the checkpoint, each cohort
manifest and every referenced audio clip before paired inference. The default
training wrapper's twelve-clip smoke is not a substitute for this evaluation.

The September 25, 2026 **500-step experiment** completed real training/export and
an independently audited six-cohort native evaluation. Enriched development WER
improved from **16.42% to 10.48%**, but external clinical WER worsened from
**17.66% to 19.11%** and general-English WER from **3.76% to 5.07%**. These are
versioned corrected scores from the same original inference events: the former
batch assembler inserted spaces between native fragments, including mid-word
fragments. The old report is retained, and the offline correction is not a
trained improvement. This was a
short clinical-only fine-tune: the consumption audit found zero replay examples.
See [measured results and exact experiment identities](EVALUATION.md#measured-experiment-september-25-2026)
for every cohort, denominators, blank outputs and limitations. These results do
not establish a generally better healthcare model or clinical safety.

Do not evaluate only generic WER or select a “good looking” example after seeing
test predictions. Use fixed references and identical audio/settings for base and
tuned models. Report:

- normalized WER, medical entity/keyword errors and recall, unsupported insertions;
- medications/doses, negation, numbers, names and pronunciation failure examples;
- external held-out clinical data and general-English regression data;
- paced microphone first-partial/final latency separately from unpaced batch RTF;
- cold model readiness, GPU memory, timeouts, error rate and cost at measured volume;
- clinician review and explicit unresolved transcription uncertainties.

`evaluate` writes per-record predictions, runtime identity, checksums, acoustic
events and measured times. Its `collapse_warning` flags blank or `<unk>` output.
Dev scores guide checkpoint choice; test data must remain untouched until that
choice is fixed. The evaluator does not invent physician validation or safety
approval. Passing an alignment/training smoke does not automatically promote the
checkpoint into the webinar selector.

### Freeze and score useful cohorts

The wrapper's first 12-dev-clip output is a **pipeline smoke**, not a medical
benchmark. Keep dev, external clinical and general-English results separate.
The tools below run locally on references/predictions and require no model calls.
Set `ASR_ALIGNED_DEV` to the verified Job's full `segments/dev.jsonl`, and
`ASR_EVAL_DIR` to a new evaluation directory. Freeze the rule/lexicon hashes
before accessing predictions; archive the resulting selection receipt. Also set
`ASR_CLOUD_RUN_ID` to that Job's exact `cloud-run --run-id` and
`ASR_CLOUD_PUBLICATION` to its downloaded, verified `completed.json`.
Do not use a partial output listing or another run's publication.

```bash
python evaluation/select_dev.py --aligned-dev "$ASR_ALIGNED_DEV" \
  --source-dev "$ASR_DATA_DIR/manifests/dev-nfa.jsonl" \
  --output "$ASR_EVAL_DIR/dev-selected-local-paths.jsonl"
python evaluation/prepare_references.py \
  --manifest "$ASR_EVAL_DIR/dev-selected-local-paths.jsonl" \
  --cloud-run-id "$ASR_CLOUD_RUN_ID" \
  --cloud-publication "$ASR_CLOUD_PUBLICATION" \
  --output "$ASR_EVAL_DIR/dev-references.jsonl"
python evaluation/prepare_references.py \
  --manifest "$ASR_DATA_DIR/manifests/external-test-utterances.jsonl" \
  --output "$ASR_EVAL_DIR/external-references.jsonl"
python evaluation/prepare_references.py \
  --manifest "$ASR_DATA_DIR/manifests/general-test-clean-pilot.jsonl" \
  --output "$ASR_EVAL_DIR/general-references.jsonl"
```

`select_dev.py` selects whole clips around each conversation's first reference
medical term, with fixed evenly spaced fallback, targeting 30–45 seconds per
conversation. Missing/short conversations are recorded. This enriched dev cohort
can guide selection; it is neither population-wide nor final held-out evidence.
The fixed lexicon is curated, not clinician-reviewed, and is never learned from
test predictions. No script supplies physician-reviewed factual labels.

The second command explicitly maps a published clinical clip from
`/output/<run-id>/segments/audio/<id>.wav` to
`/data/clinical-speech/runs/<run-id>/segments/audio/<id>.wav`. It requires the
exact clip in the matching completed publication, retains IDs/order/reference
text, validates any existing clip hash, and records all path changes plus the
publication hash in a new receipt. For older manifests that lack a clip hash it
adds **only that exact published clip's** `audio_sha256`; it never substitutes
`source_audio_sha256`, which belongs to the longer recording. The new manifest
does not overwrite the original. Cloud evaluation separately full-GET verifies
each clip against the frozen hash before inference. No model predictions are
read during selection or mapping. External/LibriSpeech manifests already use
canonical bucket-mount paths and clip hashes, so do not pass the cloud mapping
options for them. For a purely local run, omit these options and make its audio
paths accessible to the local evaluator instead.

Upload the three final reference manifests under distinct `manifests/` keys and
record their exact SHA256 values before candidate inference. Do not re-upload
large clinical audio: the verified training publication already contains it at
the mapped keys. Use [EVALUATION.md](EVALUATION.md) for separate full-cohort
`cloud-evaluate` Jobs with repeated manifest-key/SHA arguments. This requires
every row to contain its exact `audio_sha256` and its canonical
`/data/clinical-speech/<bucket-key>` path; local `/output/...` paths are rejected.

For **each** frozen cohort, run both commands below in the same GPU runtime with
the same manifest and accessible audio paths. These are container arguments to
the built image (its entrypoint is `python -m clinical_asr`); stage the chosen
manifest, audio and verified checkpoint at the shown paths first. `evaluate`
without `--limit` processes the full supplied manifest, unlike the wrapper smoke.
Use distinct output files and retain all inference failures.

```text
evaluate --manifest /data/cohort.jsonl --output /output/base.jsonl
evaluate --manifest /data/cohort.jsonl --output /output/tuned.jsonl --model-id nemotron-clinical-en --checkpoint /data/model.nemo --checkpoint-sha VERIFIED_SHA256
```

After retrieving those verified prediction files, score locally:

```bash
python evaluation/score_pair.py --reference "$ASR_EVAL_DIR/dev-references.jsonl" \
  --base "$ASR_EVAL_DIR/dev-base.jsonl" --tuned "$ASR_EVAL_DIR/dev-tuned.jsonl" \
  --output "$ASR_EVAL_DIR/dev-paired-scores.json"
```

Repeat with separate external and general reference/prediction files. The scorer
requires equal nonempty ID sets, equal audio hashes and matching decoding/base
settings; it preserves empty hypotheses as errors and refuses overwritten scores.
WER uses NFKC/lowercase normalization, preserves decimal values and negation,
and does not expand numbers or synonyms. KER counts reference keyword occurrences
whose complete aligned token spans are not retained; overlapping phrases count
separately and extra occurrences are reported. Zero keywords means **null**, not
perfect clinical performance. Dose/negation/speaker semantics require separate
audio-linked review. Report unchanged or worse results honestly.

## Serverless Endpoint

Start the same image with container argument `serve`, HTTP port 8000. Create a
**new** endpoint. Keep one replica; autoscaling/multiple replicas need an external
transactional operation/admission store and are not supported by this demo.

Required runtime configuration for the fine-tuned model:

```text
MODEL_ID=nemotron-clinical-en
MODEL_BUCKET=YOUR_PRIVATE_BUCKET
MODEL_S3_KEY=runs/YOUR_COMPLETED_RUN/training/nemotron-clinical-en.nemo
MODEL_SHA256=ACTUAL_CHECKPOINT_SHA256_FROM_PROVENANCE
AWS_ENDPOINT_URL=https://storage.BUCKET_REGION.nebius.cloud
STATE_BUCKET=YOUR_PRIVATE_BUCKET
STATE_PREFIX=endpoint-state/YOUR_NEW_ENDPOINT
CHUNK_SIZE_MS=560
```

Inject `API_BEARER_TOKEN` (at least 24 characters) and bucket-scoped S3 credentials
as secrets. An alternative is read-only local `MODEL_PATH` + `MODEL_SHA256` and
a persistent `DATA_DIR`. Without S3 state or a persistent volume, operation
durability is limited to the current filesystem. Never claim replacement-safe
durability with only ephemeral storage.

Example new-endpoint creation after the artifact and quality gates pass:

```bash
nebius ai endpoint create \
  --parent-id "$ASR_PROJECT_ID" --subnet-id "$ASR_SUBNET_ID" \
  --name "$ASR_NEW_ENDPOINT_NAME" --image "$ASR_IMAGE_REF" \
  --platform gpu-l40s-a --preset 1gpu-8vcpu-32gb --disk-size 100Gi --shm-size 8Gi \
  --args serve --container-port 8000/http \
  --auth token --token-secret "$ASR_RUNTIME_SECRET_ID" \
  --env MODEL_ID=nemotron-clinical-en --env "MODEL_BUCKET=$ASR_BUCKET" \
  --env "MODEL_S3_KEY=runs/$ASR_RUN_ID/training/nemotron-clinical-en.nemo" \
  --env "MODEL_SHA256=$ASR_CHECKPOINT_SHA256" \
  --env "STATE_BUCKET=$ASR_BUCKET" --env "STATE_PREFIX=endpoint-state/$ASR_NEW_ENDPOINT_NAME" \
  --env "AWS_ENDPOINT_URL=$ASR_S3_ENDPOINT" \
  --env-secret "API_BEARER_TOKEN=$ASR_RUNTIME_SECRET_ID" \
  --env-secret "AWS_ACCESS_KEY_ID=$ASR_STORAGE_SECRET_ID" \
  --env-secret "AWS_SECRET_ACCESS_KEY=$ASR_STORAGE_SECRET_ID"
```

The runtime secret contains both `AUTH_TOKEN` (managed ingress) and
`API_BEARER_TOKEN` (application), with the same strong token value. This dual
layer was exercised through managed HTTP, MCP and WebSocket routes; the
application refuses startup without its bearer secret. Even health/readiness
requests through the managed public URL must include authorization. A direct
application health route exemption does not bypass the managed ingress.
The L40S allocation was exercised with the pilot checkpoint; repeat qualification
for your exact image/checkpoint and check regional availability. `--public` is
deliberately omitted: a public VM IP is not needed for managed HTTPS. These
authenticated public URLs are not a PHI-ready private-endpoint claim.

For base-model comparison use a separate endpoint, `MODEL_ID=nemotron35-base-en`,
and no `MODEL_PATH`/`MODEL_S3_KEY`. The clinical alias refuses startup without an
actual checkpoint. The model is restored once; it stays resident. Serving uses
float32 greedy-batch decoding, en-US prompt, native `[56,6]` cache-aware context
at 560 ms, one active stream. It does not send the complete accumulated recording
through offline ASR on every chunk.

### HTTP and artifact flow

All inference and MCP requests require `Authorization: Bearer ...`; managed
ingress also requires it for health/readiness probes. Tokens stay on the trusted client relay/server, never
in browser JS, URLs or WebSocket query strings.

1. `POST /v1/artifacts` with multipart field `file` uploads mono16k PCM16 WAV.
2. `POST /v1/transcriptions` accepts an immutable artifact and idempotency key:

```json
{"audio_artifact":"artifact:sha256:64_HEX_CHARACTERS","idempotency_key":"unique-intended-submission","options":{"model":"nemotron-clinical-en","language":"en-US","output_granularity":"word"}}
```

3. A 202 response contains one durable operation ID.
4. `GET /v1/operations/ID` resumes/polls that same operation; no resubmission.
5. `POST /v1/operations/ID/cancel` requests chunk-boundary cancellation.

Identical idempotent replay returns the original operation; a changed request with
the same key conflicts. The queue is bounded at four. Interrupted accepted work
becomes an explicit `worker_interrupted` failure after restart, not a hidden retry.
Live stream reconnection is intentionally not silently resumed.

`POST /v1/audio/transcriptions` is a multipart compatibility route (`file`,
`model`, `language=en`, `response_format=json|verbose_json`). Verbose responses
include `words:[{word,start,end}]` from NeMo's acoustic output, `audio_seconds`
and runtime identity. `timestamp_granularities[]=word` is supported. Requests
that exceed 600 seconds return the operation as 202 for polling. Preserve
`Idempotency-Key` when retrying and `X-Operation-Id` from the response.

### True live streaming

Connect to `wss://NEW_ENDPOINT/v1/audio/stream` through an authenticated trusted
relay. Verify actual Serverless WebSocket forwarding/time limits in the deployed
endpoint—HTTP success does not qualify WebSockets.

```json
{"type":"session.start","options":{"model":"nemotron-clinical-en","language":"en-US","chunk_size_ms":560,"output_granularity":"word"},"audio":{"encoding":"pcm_s16le","sample_rate_hz":16000,"channels":1}}
```

Send binary PCM16LE messages of at most 65,536 bytes, then
`{"type":"input.finish"}`. `{"type":"session.cancel"}` cancels. The server emits
`session.ready`, `transcript.partial`, `transcript.final`, `session.completed`.
Partials **replace** the current `(segment_id,revision)`; never append every
partial as new words. A final seals that segment. Word/segment `items` include
real acoustic offsets; confidence is `null`, not an invented probability. The
tail is explicitly flushed, including exact chunk boundaries. Disconnect and
cancellation release native encoder/decoder state after the active GPU call.

Native ASR does not identify speakers. A separate diarization component can join
its speaker activity to real word timings. Mark overlaps/uncertainty and let the
human assign clinician/patient roles; do not infer the role from speaker number.

### MCP

`POST /mcp` supports MCP Streamable HTTP. Typed tools are:

- `describe_clinical_asr`
- `transcribe_clinical_audio(audio_artifact,idempotency_key,model)`
- `get_clinical_transcription(operation_id)`
- `cancel_clinical_transcription(operation_id)`

Use HTTP for large audio upload. MCP returns operation identity and structured
status/results, never base64 audio. This is the new endpoint's MCP surface, not a
mutation of the running Scientific AI control plane. Actual LibreChat discovery,
tool invocation and transcript handoff still need end-to-end qualification.

## Boundaries, observability and acceptance

`/healthz` is process health; `/readyz` turns ready only after successful model
load. Authenticated `/v1/models` reports checkpoint identity and limits; `/metrics`
reports readiness, GPU admission, queue depth, request and error counts. Access
logs are disabled; service code does not log audio or transcript contents.
Artifacts and operation results are retained in the configured private storage;
set retention/deletion policy before any sensitive deployment. Bearer auth is not
proof of private networking, HIPAA compliance or acceptable PHI logging. Verify
endpoint exposure, bucket ACLs, region, network controls and platform logs.

Before the webinar, qualify the actual digest/checkpoint through the **new client**:
base default microphone; tuned selector only after promotion; file upload; paced
audio streaming; acoustic word timing; speaker-aware transcript; SOAP/task draft;
editable clinician review; cancellation; overload; invalid audio; restart-safe
operation polling; and an intentionally visible transcription failure.

Fast public-data/scoring tests need only a small development environment:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install pytest==8.4.2 boto3==1.42.49
.venv-dev/bin/python -m pytest -q tests/test_public_data.py tests/test_public_scores.py tests/test_public_mapping.py
```

These tests are offline and do not download corpora or load a model. To run the
complete protocol suite, separately install `pytest==8.4.2` into a disposable
environment with the recipe runtime dependencies, then run
`python -m pytest -q tests` from this directory. Do not expand the production
dependency lock just to add test tools. Protocol tests use explicit synthetic
engines. They do not demonstrate GPU inference, medical accuracy or
cloud ingress compatibility. Keep measured cloud evidence outside the source tree
and report pending gates honestly.

Jobs save a read-only `environment.json` (actual driver, GPU, Python/framework
versions and allowlisted configuration) and process-local training memory peaks.
Batch predictions include per-request PyTorch allocated/reserved peaks; these are
not whole-GPU usage and exclude external allocators. Keep cold image/model startup
separate from warm unpaced batch inference and real-time-paced stream finalization.
For a latency claim, retain at least three identical-fixture repetitions; a single
smoke run is a plumbing check, not a performance comparison.
`wall-times.jsonl` separates CUDA-synchronized training batches, validation,
local Lightning checkpoint writes, durable S3 checkpoint publication/readback
and `.nemo` export. Validation total may overlap callback/checkpoint time; do not
sum overlapping windows. Timing records are also emitted as compact progress logs.

`consumed-training-segments.jsonl` records reference-token and exact audio-length
matches for completed training batches. The native prompt loader does not return
cut IDs, so only `match=unique` establishes an unambiguous source segment; retain
ambiguous/unmatched rows. For the selected `.nemo`, count only records with
`global_step_before < selected_checkpoint_global_step` from training provenance.
Also require `consumption_seen_claim_eligible=true`. Resumed runs currently fail
closed for seen-example claims because earlier ledger history is not restored;
reuse of an existing ledger is refused to avoid counting a discarded attempt.
Dataset membership alone is not proof that a short run consumed a demonstration
clip. Source word spans remain in each segment's manifest for audit.

### Replay mixing and the initial qualification run

Replay rows must be mixed across the **whole** training manifest before NeMo's
bounded-buffer shuffling. The wrapper now uses a deterministic full-manifest
shuffle with `--seed` (default `20260925`), records input/output membership and
order hashes in `replay-provenance.json`, and passes the same seed to training.
Every row, text target, split and source field is retained. This controls manifest
order, not bitwise GPU reproducibility or a guaranteed replay fraction per batch.

The initial 500-step qualification on September 25 used the earlier append-only
merge. Its audited loader buffer contained only clinical rows: **zero replay
examples were consumed**, despite replay being present in the manifest. Those
weights must be described as a short clinical-only fine-tune, not as
replay-regularized. It processed about 7.34 hours, not the complete available
corpus. Those weights and original artifacts have not been changed. The original
score report is retained and explicitly superseded by the native-fragment
assembly rescore in [the evaluation notes](EVALUATION.md#corrected-native-fragment-assembly-same-historical-inference).

The corrected mixing has CPU membership/order/hash/seed regression tests,
including a clinical prefix larger than the native 20,000-cut buffer. These tests
do **not** establish GPU replay consumption. A separate actual training run and
selected-checkpoint consumption audit are required before claiming that replay
was used; independent general-English regression evaluation remains necessary.

For a real managed-endpoint probe, install the small client subset in a separate
environment, inject `ASR_ENDPOINT` and `API_BEARER_TOKEN` securely, and run from
this source directory (no local model or GPU dependency is needed):

```bash
python -m pip install httpx==0.28.1 websockets==15.0.1 mcp==1.26.0
python -m clinical_asr.probe --audio /path/to/approved-synthetic.wav \
  --model nemotron-clinical-en --output /path/to/private-evidence.json
```

This runs an actual artifact upload, idempotent batch submit/poll, MCP discovery
and same-operation polling, then sends the audio as real-time-paced binary PCM
over WebSocket and records partial/final timings. Evidence contains transcript
text and must follow the approved-data policy. Browser microphone/review gates
remain separate; this SDK probe does not qualify the browser.

### Opt-in English-specialist candidate path

`train`, `cloud-train`, `evaluate`, and `cloud-evaluate` accept
`--model-family english_specialist`. The default remains `nemotron35`; no
existing endpoint, model selection, or image is changed by this option. The
English foundation is pinned in `clinical_asr/families.py` to its exact upstream
revision and checkpoint SHA256, and uses the non-prompt RNNT dataset loader.
Its original tokenizer, 618,084,865 parameters, and trained attention contexts
are retained; only the dataset template is replaced, explicitly reading `text`.
Consumption evidence handles its native four-tensor batch contract separately
from the multilingual five-tensor contract.

English candidate comparisons use the original English checkpoint as `base`
and the explicit English-adapted checkpoint as `tuned`; they must not label an
English model as multilingual. `evaluate-english` separately benchmarks the
original pinned English foundation. A future English-adapted endpoint requires
`MODEL_FAMILY=english_specialist` alongside its actual `MODEL_PATH`/`MODEL_SHA256`
and `MODEL_ID=nemotron-clinical-en`. Its native 560ms inference context is
`[70,6]`, compared with `[56,6]` for multilingual Nemotron 3.5.

At this preparation stage, the English fine-tuning path has passed CPU tests
and actual checkpoint/loader/reference-token preflight, **not GPU training or
candidate quality qualification**. Complete a separately recorded GPU smoke,
freeze the adaptation and comparison protocol, and qualify real candidate
weights before serving them. The multilingual and English families are not
interchangeable optimizer-resume targets. Neither model is clinically validated.

### Resource lifetime and cleanup

Before creating a resource, record its unique experiment name and exact ID. Keep
all pre-existing instances out of the cleanup set. Jobs use a finite timeout;
an always-running serving endpoint also accrues allocation time while idle.
Choose explicitly whether to keep it warm for a demonstration or stop it between
sessions. Processing time alone is not the deployed service's billed lifetime.

While each new training/evaluation Job is running, record its Compute instance
IDs from `status.instances`, then the instance's `metadata.parent_id` and exact
disk IDs. Serverless children can live under an application (`appbox-...`)
parent: absence from a project-level Compute listing does **not** prove release.
Use full pagination for inventories; these read-only examples use CLI0.12.280:

```bash
nebius ai job get --id "$ASR_JOB_ID" --format json
nebius compute instance get --id "$ASR_JOB_VM_ID" --format json
nebius compute disk list --parent-id "$ASR_JOB_APPBOX_ID" --all --format json
```

Wait for terminal Job status **and** the recipe's verified `completed.json`
before promoting successful output. A failed/cancelled Job or a partial object
listing is not a successful model publication. Confirm release with exact-ID
Compute instance and disk GETs after termination; distinguish `ResourceNotFound`
from authorization, transport or other errors. Retain `.nemo`, provenance,
recovery snapshots, evaluation and failure evidence in Object Storage. If a
resource remains allocated, investigate the exact owned Job/application instead
of deleting broadly from the project.

Stopping an endpoint can remove its local runtime disk. Export required local
artifacts first, use verified bucket-backed state, and record the exact owned
endpoint/VM/disk IDs. Only when that particular endpoint is no longer needed:

```bash
nebius ai endpoint stop --id "$ASR_ENDPOINT_ID" --async
```

Check terminal endpoint status and exact VM/disk release afterward. This does
not delete the retained model or bucket evidence. Starting the same owned
endpoint later uses `nebius ai endpoint start --id "$ASR_ENDPOINT_ID" --async`;
recheck its current route, authenticated readiness and checkpoint identity before
use, and allow cold image/model loading. This command is not proof of qualified
restart recovery: native streams are not resumable, and persisted-operation
recovery needs its own interrupted-worker test. Apply bucket retention and
credential retirement separately after the experiment; do not delete evidence
or credentials that active serving still needs.
