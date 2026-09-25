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
every Job/Endpoint definition. `Dockerfile.internal` is an accelerated internal
build using a separately qualified CUDA 12.8 runtime; it is not needed to
reproduce the public recipe. Record the exact built image digest in the run
evidence. Public and internal builds require separate runtime qualification.

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

## Serverless Job

Upload the source data directory contents at a private bucket root. The manifest
paths map to bucket keys by stripping `/data/clinical-speech/`. Use a new scoped
service account/secret and a new Job; do not reuse or modify running instances.

Inject `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` through runtime secrets, and
set `AWS_ENDPOINT_URL` to the bucket region's Object Storage endpoint. Credentials
must not appear in images, manifests, shell history or evidence. Cross-region
Jobs stage data with S3 to local disk; no cross-region FUSE mount is required.

Container arguments for the first real GPU smoke:

```text
cloud-run --bucket YOUR_PRIVATE_BUCKET --run-id pilot-UNIQUE
  --manifest-key manifests/pilot-alignment.jsonl
  --max-steps 10 --val-every 5
  --batch-duration 30 --accumulate-grad-batches 1
  --upload-lightning-checkpoints
```

Using the current Nebius CLI, after setting non-secret IDs and an immutable image
reference in your shell (these commands create billable **new** resources):

```bash
nebius ai job create \
  --parent-id "$ASR_PROJECT_ID" --subnet-id "$ASR_SUBNET_ID" \
  --name "$ASR_NEW_JOB_NAME" --image "$ASR_IMAGE_DIGEST" \
  --platform gpu-h200-sxm --preset 1gpu-16vcpu-200gb \
  --disk-size 250Gi --timeout 1h --restart-policy never \
  --container-command "python -m clinical_asr" \
  --args "cloud-run --bucket $ASR_BUCKET --run-id $ASR_RUN_ID --manifest-key manifests/pilot-alignment.jsonl --max-steps 10 --val-every 5 --upload-lightning-checkpoints" \
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
`--replay-manifest-key` if replay is chosen.

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
from local unit tests. Periodic snapshots introduce storage/transfer overhead.

Manual stage commands are also supported:

```text
align --manifest /data/clinical-speech/manifests/pilot-alignment.jsonl --output /output/alignment
segment --source-manifest /data/clinical-speech/manifests/pilot-alignment.jsonl --alignment-dir /output/alignment --output /output/segments
train --train-manifest /output/segments/train.jsonl --dev-manifest /output/segments/dev.jsonl --output /output/train --max-steps 10 --val-every 5 --accumulate-grad-batches 1
```

No package installation or source checkout happens inside the training job.

## Evaluation and promotion

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
  --name "$ASR_NEW_ENDPOINT_NAME" --image "$ASR_IMAGE_DIGEST" \
  --platform gpu-h200-sxm --preset 1gpu-16vcpu-200gb --disk-size 250Gi \
  --container-command "python -m clinical_asr" --args serve \
  --container-port 8000 --auth none \
  --env MODEL_ID=nemotron-clinical-en --env "MODEL_BUCKET=$ASR_BUCKET" \
  --env "MODEL_S3_KEY=runs/$ASR_RUN_ID/training/nemotron-clinical-en.nemo" \
  --env "MODEL_SHA256=$ASR_CHECKPOINT_SHA256" \
  --env "STATE_BUCKET=$ASR_BUCKET" --env "STATE_PREFIX=endpoint-state/$ASR_NEW_ENDPOINT_NAME" \
  --env "AWS_ENDPOINT_URL=$ASR_S3_ENDPOINT" \
  --env-secret "API_BEARER_TOKEN=$ASR_RUNTIME_SECRET_ID" \
  --env-secret "AWS_ACCESS_KEY_ID=$ASR_STORAGE_SECRET_ID" \
  --env-secret "AWS_SECRET_ACCESS_KEY=$ASR_STORAGE_SECRET_ID"
```

`--auth none` disables only the platform's additional token layer in this example;
the application itself enforces its required bearer secret on all inference,
artifact, metrics and MCP paths. It refuses startup without that secret. Enable
an additional platform authentication layer if its forwarding semantics have been
tested with the relay. `--public` is deliberately omitted: a public VM IP is not
needed for managed HTTPS. Neither choice makes a PHI-ready private endpoint claim.

For base-model comparison use a separate endpoint, `MODEL_ID=nemotron35-base-en`,
and no `MODEL_PATH`/`MODEL_S3_KEY`. The clinical alias refuses startup without an
actual checkpoint. The model is restored once; it stays resident. Serving uses
float32 greedy-batch decoding, en-US prompt, native `[56,6]` cache-aware context
at 560 ms, one active stream. It does not send the complete accumulated recording
through offline ASR on every chunk.

### HTTP and artifact flow

All inference and MCP requests require `Authorization: Bearer ...`; health and
readiness probes do not. Tokens stay on the trusted client relay/server, never
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

Local tests (`python -m pytest -q tests`) use explicit synthetic engines for
protocol validation. They do not demonstrate GPU inference, medical accuracy or
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

For a real managed-endpoint probe, install the client dependencies from the lock,
inject `ASR_ENDPOINT` and `API_BEARER_TOKEN` securely, and run:

```bash
python -m clinical_asr.probe --audio /path/to/approved-synthetic.wav \
  --model nemotron-clinical-en --output /path/to/private-evidence.json
```

This runs an actual artifact upload, idempotent batch submit/poll, MCP discovery
and same-operation polling, then sends the audio as real-time-paced binary PCM
over WebSocket and records partial/final timings. Evidence contains transcript
text and must follow the approved-data policy. Browser microphone/review gates
remain separate; this SDK probe does not qualify the browser.
