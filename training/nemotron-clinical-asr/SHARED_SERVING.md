# Serve your English fine-tune as a shared Scientific AI App

**Qualification scope:** the copied canonical runtime includes the native-backed
segment-separator fix. Raw event text and acoustic word timings remain unchanged;
assemblers honor only its explicit `separator_before` hint, never guess spaces
between chunks. No public rebuilt-image or capacity qualification is claimed by
the cookbook's copied-source CPU tests.

This is the intended multi-customer serving path. It packages the canonical
concurrent worker source in [shared-runtime](shared-runtime), then connects a
new Serverless Endpoint to the Scientific AI platform's existing gateway.
Customers use ordinary scoped platform keys, not the private worker credential.
The gateway owns tenant authorization, immutable artifacts, durable operations,
idempotency, scheduling metadata and usage. The worker owns bounded live/file
admission, independent decoder/cache state, fair chunk scheduling and GPU work.
One serialized GPU execution lane can batch/interleave several customer sessions.

This recipe is not a self-contained replacement for the Scientific AI platform.
It requires an installed gateway with the reviewed speech adapter, transactional
operation storage and artifact service. A raw worker Endpoint has no customer
MCP, operation store or tenant authorization. Do not expose it as a shared-bearer
customer API. The earlier `clinical_asr serve` runtime is research-only.

## 1. Train and retain your checkpoint

Skip training if you already have the selected, authorized English artifact:
its SHA-256 and size are in [selected results](SELECTED_ENGLISH_RESULTS.md).
Use those exact bytes, not a newly trained substitute. If the App is already
enabled for you, skip packaging and go directly to section 5. This recipe does
not distribute the demonstration weights or grant access to its private storage.

For your own data, use the [raw-audio English Job path](README.md#opt-in-english-specialist-candidate-path)
or [balanced training](BALANCED_TRAINING.md) for already-aligned domain/replay
clips, explicitly selecting `--model-family english_specialist`.
Complete a finite smoke and a separately approved main Serverless Job. Retain
full development selection, source/exposure ledgers, `.nemo` and their full GET
checksums before releasing that Job's exact GPU/VM/scratch resources. Do not
stop currently running serving resources. No training is performed at serving
startup, and a ten-step smoke is not a useful fine-tune by itself.

### Retrieve your Job's export

Both `cloud-run` and `cloud-train` export the development-selected checkpoint
automatically. They publish these keys in your bucket:

```text
runs/YOUR_RUN_ID/completed.json
runs/YOUR_RUN_ID/training/nemotron-clinical-en.nemo
runs/YOUR_RUN_ID/training/training-provenance.json
```

`training-provenance.json` records `checkpoint_sha256` and
`selected_checkpoint_global_step`; that step need not equal the last training
step. A `.ckpt` is an optimizer/training checkpoint, not the `.nemo` serving
artifact. An absent `completed.json` or failed Job is not a successful export.

For a **new run of this recipe**, the following uses AWS CLI, `jq` and GNU
`sha256sum` locally, with bucket-scoped credentials supplied securely by your
environment/credential provider. Set `ASR_BUCKET`, `ASR_RUN_ID` and
`ASR_S3_ENDPOINT` to your actual run; do not paste credential values into commands.
This downloads only to a new private directory, not into the repository:

```bash
umask 077
ASR_EXPORT_DIR="$(mktemp -d)" || exit 1
aws --endpoint-url "$ASR_S3_ENDPOINT" s3 cp \
  "s3://$ASR_BUCKET/runs/$ASR_RUN_ID/completed.json" \
  "$ASR_EXPORT_DIR/completed.json" --no-progress || exit 1
jq -e --arg run "$ASR_RUN_ID" \
  '.status == "completed" and .run_id == $run and .model_family == "english_specialist"' \
  "$ASR_EXPORT_DIR/completed.json" || exit 1
for name in nemotron-clinical-en.nemo training-provenance.json; do
  key="runs/$ASR_RUN_ID/training/$name"
  aws --endpoint-url "$ASR_S3_ENDPOINT" s3 cp \
    "s3://$ASR_BUCKET/$key" "$ASR_EXPORT_DIR/$name" --no-progress || exit 1
  expected="$(jq -er --arg key "$key" \
    '[.objects[] | select(.key == $key)] | if length == 1 then .[0].sha256 else error("missing or duplicate export") end' \
    "$ASR_EXPORT_DIR/completed.json")" || exit 1
  printf '%s  %s\n' "$expected" "$ASR_EXPORT_DIR/$name" | sha256sum -c - || exit 1
done
ASR_CHECKPOINT_SHA256="$(jq -er '.checkpoint_sha256' "$ASR_EXPORT_DIR/training-provenance.json")" || exit 1
printf '%s  %s\n' "$ASR_CHECKPOINT_SHA256" \
  "$ASR_EXPORT_DIR/nemotron-clinical-en.nemo" | sha256sum -c - || exit 1
```

Stop on any failed command or checksum; do not package partial output. Retain
the completed publication and provenance alongside the evaluation results.
For the historical selected artifact, obtain its authorized verified export
from your operator and check the published selected hash/size instead of assuming
that an older run has the current publication schema.

Create a new model-bundle directory **outside the repository** containing only:

```text
model.nemo       # your actual selected, verified English checkpoint
MODEL_CARD.md    # parent revision, training provenance, changes and limitations
MODEL_LICENSE   # applicable upstream license text and derivative obligations
```

Copy the verified `nemotron-clinical-en.nemo` to `model.nemo` without conversion;
renaming does not change its SHA-256. Supply the real model card and license,
not placeholder documents. Keep training/provenance files outside this three-file
build context. For your own fine-tune, use its actual SHA, never the demonstration's
`2a2b…` identity.

Review all model/data license obligations before distributing a derivative or
an image containing it. The code's Apache license does not cover the weights.
For the English family, preserve the NVIDIA Open Model License; do not copy the
different 3.5 OpenMDW license. This recipe distributes no checkpoint or dataset.

## 2. Build from the public dependency recipe

First build the main [Dockerfile](Dockerfile), which uses a public digest-pinned
PyTorch base, checksummed NeMo source and hash-pinned dependencies. Push it into
your registry and resolve the immutable digest as `ASR_TRAINING_IMAGE`.
The serving Dockerfile installs no additional packages and has no dependency on
an internal/private Nebius image. Its core framework/API dependency versions
match the reviewed source runtime; your reconstructed image still needs tests.

Set `ASR_MODEL_BUNDLE` to the new bundle directory, `ASR_CHECKPOINT_SHA256` to its
verified full-file hash, and `ASR_RECIPE_COMMIT` to this cookbook commit. From
this recipe directory:

```bash
docker buildx build --platform linux/amd64 \
  --build-arg "TRAINING_IMAGE=$ASR_TRAINING_IMAGE" \
  --build-arg "CHECKPOINT_SHA256=$ASR_CHECKPOINT_SHA256" \
  --build-arg "SOURCE_REVISION=$ASR_RECIPE_COMMIT" \
  --build-context "model_bundle=$ASR_MODEL_BUNDLE" \
  -f shared-runtime/Dockerfile \
  -t "$ASR_NEW_SERVING_TAG" --push shared-runtime
```

Require a digest reference for `ASR_TRAINING_IMAGE`, a fresh serving tag, and
verify the published serving manifest/config/checkpoint before use. Keep model
bundle, credentials and other local files outside the default-deny main context.
Only the three explicit bundle files are copied from its named context. The
worker runs as UID/GID10001, offline, restores the exact hash and fails on a
missing or mismatched artifact. It reports the loaded hash in `runtime_identity`.
The pinned original English base can be packaged separately for comparison;
never configure the derivative App to point at the base checkpoint.

## 3. Create a new authenticated Serverless worker

Choose available GPU capacity and a new name; never reuse a running instance.
Resolve `ASR_SERVING_IMAGE` to the immutable published digest. Use the current
CLI help and a dry run first. An example one-GPU allocation follows; this is
an explicit experimental shape, not a measured minimum or capacity promise.

```bash
nebius ai endpoint create \
  --parent-id "$ASR_PROJECT_ID" --subnet-id "$ASR_SUBNET_ID" \
  --name "$ASR_NEW_ENDPOINT_NAME" --image "$ASR_SERVING_IMAGE" \
  --platform gpu-h200-sxm --preset 1gpu-16vcpu-200gb \
  --disk-size 100Gi --shm-size 8Gi --on-demand \
  --container-port 8000/http --public=false \
  --env FS2_SPEECH_MAX_SESSIONS=4 --env FS2_SPEECH_MAX_BATCH_SIZE=4 \
  --env FS2_SPEECH_BATCH_WAIT_SECONDS=0.005 \
  --env "FS2_SPEECH_ARTIFACT_HOSTS=$ASR_ARTIFACT_STORAGE_HOST" \
  --env-secret "FS2_STT_GATEWAY_TOKEN_MATERIAL=$ASR_GATEWAY_WORKER_SECRET" \
  --dry-run
```

The version-pinned Secret contains `FS2_STT_GATEWAY_TOKEN_MATERIAL`, a strong
private gateway-to-worker credential of 32–1024 non-whitespace ASCII characters.
It is removed from the process environment before runtime import and placed in
a new 0700 directory/0600 temporary file. Never put it in browser code, CLI
arguments, images or logs. The mandatory startup adapter rejects missing auth.
Only the trusted gateway receives it; customer isolation uses the gateway's
ordinary per-customer keys and authenticated scheduling groups instead.

Omitting `--public` avoids a public **VM IP**, not managed public HTTPS. Worker
inference, drain, metrics and detailed capacity observation require the private
credential; process `/healthz` and `/readyz` are unauthenticated application
routes. Decide whether managed ingress auth/network restrictions are additionally
required for your deployment and test those exact settings. No PHI/private-network
claim follows from this example. Artifact downloads allow only your explicitly
listed HTTPS storage host(s); never use `*` or accept customer arbitrary URLs.

Remove `--dry-run` only after reviewing the exact billable creation. Record
Endpoint/image/VM/disk IDs, secret version (not its value), model SHA, profile
and a cleanup owner. Keep warm serving only for your intended period. Inspect
actual readiness and loaded identity before enabling any customer App.

## 4. Register the distinct App through the canonical platform

Use the platform's App/model-onboarding workflow and reviewed Serverless adapter,
not a hardcoded reverse proxy or a second scheduler. Registration must bind:

- A distinct public App/model identity, derivative license/model card and exact
  checkpoint SHA/size/source lineage. The demonstration uses
  `nemotron-speech-en-medical-0-6b`; its base remains `nemotron-speech-en-0-6b`.
- A distinct runtime variant and immutable image/Endpoint route. The reviewed
  medical variant is `nemotron-speech-en-medical-0-6b-nemo-cuda-v1` with native
  wire options `nemotron-speech-en-0.6b`. Wire compatibility is not weight identity.
- The gateway's signed route/worker-credential binding, artifact-download host
  allowlist, persistent operation store and ordinary tenant grants/budgets.
- A measured capacity envelope for this exact model/image/GPU/profile and an
  existing platform owner for scaling and draining. Configuring 4 does not prove 4.

The source snapshot comes from platform revision
`b193b5c65ed1ae0a11cb9c32b8be88c0c6c02ced`. Relevant gateway modules there are
`speech_models.py`, `model_input_contracts.py`, `speech_routes.py`,
`speech_stream.py` and `mcp_input_contracts.py` under
`k8s-inference/components/control-plane/src/fs2_serve`.
The gateway requires an installed matching contract and registered route; adding
a display name or environment variable alone cannot make an App available.
Use the operator's actual schema/registration interface for the deployed release;
do not assume arbitrary fine-tune names automatically inherit the base contract.

The source's concrete bootstrap projection is
`fs2_serve.native_serverless.DeploymentSet`, selected by
`FS2_NATIVE_SERVERLESS_DEPLOYMENTS_FILE`. Its schema can be inspected in the
matching installed control-plane environment without changing cloud state:

```bash
python -c 'import json; from fs2_serve.native_serverless import DeploymentSet; print(json.dumps(DeploymentSet.model_json_schema(), indent=2))'
```

The operator fills that strict document from real catalog/artifact manifests,
observed Endpoint/image/checkpoint, exact gateway and discovery Service UIDs,
scoped Secret identity, trust bundle, two native fixtures and file/live parity
receipts. The existing attestor signs the complete subject with a maximum
24-hour expiry; mount that reviewed document read-only in the gateway. Never
invent receipt hashes, reuse another gateway's signature, or copy an old expiry.
The route permits only explicitly listed qualification tenant/principal pairs
in addition to their normal grants. It deliberately reports readiness,
semantic/HTTP/MCP/cold-start/elasticity qualification as false until separately
established; route-active does not mean production-ready. This bootstrap has
**no unrestricted-customer promotion mode**. Production release requires the
platform's normal acceptance and signed release process after measured tests.
See the matching platform document
`k8s-inference/docs/native-serverless-qualification-routes.md`.

## 5. Customer API, MCP and LibreChat

Use the **native batch contract** as the default: schema discovery → upload
and finalize a tenant-owned artifact → named native tool → poll → full result.
These core tools and upload routes are present in platform source
`654ff215ea122a404e30fc0d64feacaa05102954`. Publishing a batch-native App does
**not** install `/v1/audio/transcriptions` or `/v1/audio/stream`; main-platform
multipart audio and live support are not established by this recipe. An operator
must separately enable the exact App/route and grant your ordinary customer key.

### One native batch request

Connect your MCP client to the operator-supplied **gateway `/mcp`**, not the
worker. All examples below use the selected demonstration App ID; use the exact
operator-registered ID for your own fine-tune. If it is absent from your
authorized discovery, stop and ask the operator—do not silently use the base.

1. Discover tools and call `get_model_schema` with:

   ```json
   {"model_id":"nemotron-speech-en-medical-0-6b","protocol":"native"}
   ```

   Retain the returned native `tool_name`, `input_schema` and runtime identity.
   A schema response is not proof that the worker is ready or the App qualified.

2. Hash one approved WAV locally (`sha256sum "$ASR_AUDIO"`) and obtain its exact
   byte size (`stat -c %s "$ASR_AUDIO"`). Call `begin_model_artifact_upload` with
   the same `model_id`, that actual `sha256`, integer `size_bytes`,
   `media_type: "audio/wav"`, `compression: "none"` and a unique upload
   `idempotency_key`. Retain its returned **upload** `operation_id`, `upload_id`,
   `content_path` and `max_content_bytes`. Upload reservation is not inference.

3. A trusted file-transfer client writes the exact bytes outside model context.
   For a file no larger than the returned `max_content_bytes`, the supported
   gateway PUT is shown below. Set `ASR_API_ORIGIN` to the operator's HTTPS origin
   without a trailing slash, and the two IDs from that actual reservation.
   Confirm the resulting path equals the returned `content_path`; do not invent
   IDs. `ASR_AUTH_HEADER_FILE` is a private 0600 file provisioned by your secret
   manager containing `Authorization: Bearer <ordinary-customer-key>`.

   ```bash
   umask 077
   ASR_RESPONSE_DIR="$(mktemp -d)" || exit 1
   curl --disable --silent --show-error --fail-with-body --proto '=https' --noproxy '*' \
     --connect-timeout 10 --max-time 90 --request PUT \
     --header "@$ASR_AUTH_HEADER_FILE" --header 'Content-Type: audio/wav' \
     --data-binary "@$ASR_AUDIO" --output "$ASR_RESPONSE_DIR/upload.json" \
     "$ASR_API_ORIGIN/v1/scientific-artifacts/uploads/$ASR_UPLOAD_ID/content?operation_id=$ASR_UPLOAD_OPERATION_ID"
   ```

   This does not follow redirects or retry automatically. For a larger file,
   use the reservation's write-once `handle` through the trusted transfer client,
   subject to the model's actual schema limit. Do not print signed URLs/headers,
   send the gateway key to object storage, or put audio/base64 into MCP arguments.

4. After successful transfer, call `finalize_model_artifact_upload` with those
   same upload `operation_id` and `upload_id`. Keep its entire verified artifact
   descriptor. Call the discovered **named native tool** with `audio` equal to
   that descriptor and `options` matching its schema. For this English worker,
   the native options are `{"model":"nemotron-speech-en-0.6b","language":"en-US","output_granularity":"word"}`.
   The wire model is not the public App ID and does not itself identify the
   fine-tuned weights. Add top-level `idempotency_key` for this intended
   transcription and `wait_seconds: 0`; do not nest these controls in `audio` or
   `options`, and do not wrap a named tool's fields in `payload`.

5. Retain the returned **inference** operation ID, distinct from the upload
   operation. Poll `get_operation` with that ID; `queued`, `activating` and
   `running` are not final. Only after `succeeded`, call `get_operation_result`
   with the same ID and save the full result, including text/segments and reported
   checkpoint/runtime identity. Download any returned artifact through the
   trusted client and verify its size/hash before acknowledgement or expiry.
   `failed`, `cancelled`, `preempted` and `expired` are not empty successful
   transcripts. A timeout has an unknown outcome: reconcile the same operation
   and idempotency key, never submit a fresh key merely because work is queued.

For clients requiring the generic compatibility tool, `invoke_model` takes the
same public `model_id`, `protocol: "native"`, `payload: {"audio": <finalized descriptor>, "options": <schema-matching options>}`,
plus top-level `idempotency_key` and `wait_seconds`. The HTTP equivalent is
`POST /v1/models/{model_id}:invoke` with `{"operation":"transcribe","payload":...}`,
an `Idempotency-Key` header and `x-fs2-wait-seconds: 0`. Its 202 response is durable
acceptance, not a transcript: use `GET /v1/operations/{id}`, then
`GET /v1/operations/{id}/result`. This native fallback does not depend on a
multipart audio adapter. Keep credentials and output text private.

### Optional multipart and live integrations: release-specific

Only use `POST /v1/audio/transcriptions` if your installed gateway explicitly
publishes and qualifies that compatibility route for the selected App. The
separate speech-adapter implementation supports small multipart uploads up to
8 MiB; that is **not** a capability implied by a native-only catalog entry.
Use the native flow above when it is absent; do not change public routing to
make an undocumented endpoint work.

Likewise, only on a separately enabled and qualified live integration, connect
through the authenticated gateway/LibreChat relay to
`/v1/audio/stream`. Public start options identify the chosen App; the gateway
maps it to the English wire options. Negotiate mono 16 kHz PCM16LE, 560 ms chunks
and word granularity. Wait for `session.ready` and verify the loaded checkpoint
before sending PCM. Partial events replace a segment; final events seal it.
Send `input.finish` to flush the tail and require `session.completed`. Only
native word items provide acoustic times; empty items do not permit invented
alignment. Cancel/disconnect must release that session without affecting others.

If your existing LibreChat deployment exposes that qualified microphone choice,
select it, record, then Stop. Check the selected model
and returned transcript; do not assume a fresh recording will reproduce a saved
example. A custom trusted relay sends a `session.start` JSON message with
`options.model` set to that public App, `language: "en-US"`,
`chunk_size_ms: 560`, `output_granularity: "word"` and
`audio: {"encoding":"pcm_s16le","sample_rate_hz":16000,"channels":1}`.
Then send only binary PCM (not the WAV header) at real-time pace after ready.
Keep customer credentials in the relay, not browser JavaScript or a WebSocket
query string. The historical `clinical_asr.probe` targets the single-active
diagnostic API; it is **not** a client for this shared gateway contract.

For an operator-configured Scientific AI LibreChat integration, use canonical
API/MCP origins, ordinary scoped credentials and a tenant-owned workspace.
The demonstration's selector is English base → exact fine-tune → **same** fine-tune + Sortformer;
this is a separate client integration, not a main-platform live-support claim.
Sortformer is a separate authorized App, invoked after Stop. Anonymous channels
are not clinician/patient identities; role assignment and note review are explicit.
An explicitly selected fine-tuned batch result is saved in full before drafting;
the draft reads that transcript, not an implicit second ASR call. A microphone
choice must never relabel an unrelated default audio-upload route as fine-tuned.

## 6. Qualification and operational boundaries

Run `FS2_STT_REQUIRE_GATEWAY_AUTH=0 PYTHONPATH=shared-runtime/src python -m pytest shared-runtime/tests` in an
isolated test environment with the recipe dependencies and pytest 8.4.1. These
unit tests use fake engines; they do not qualify the reconstructed image/GPU.
The zero is test-only for the existing optional-auth fixtures; the separate
entrypoint tests verify required-auth rejection. Never change the production
Dockerfile's mandatory auth setting or use this test environment to serve traffic.
Record import tests as UID10001, exact artifact checksum/restore, native file
and paced-stream parity, acoustic timing/tail, real customer API/MCP/browser
flows, wrong-key/checkpoint failure, idempotency and cancellation.

Measure overlapping distinguishable customers, mixed file/live work, repeated
steady load, burst/overload/recovery, latency distributions, actual processed PCM,
peak device memory and transcript correctness. Expose `/capacity-observation`
and `/metrics` only to authorized operators and integrate their active/pending,
wait, buffered PCM, processed PCM, rejects and GPU pressure into existing
telemetry. Missing values are unknown, not spare capacity. Declare the highest
qualified concurrency and first failing or untested bound. Prove scale-out,
draining and worker-loss outcomes on the actual serving substrate before claiming
those capabilities; Kubernetes results do not qualify Serverless autoscaling.

The illustrative 4-session setting is **not a production capacity certificate**.
Clinical quality is separately limited as in [selected results](SELECTED_ENGLISH_RESULTS.md).
Use synthetic or approved de-identified audio; clinician review, PHI agreements,
privacy/security architecture, retention and production cost remain explicit
pilot decisions. Keep failed/skipped checks visible and qualify the final image,
App, endpoint, ordinary client and loaded checkpoint together.
