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

Use [balanced training](BALANCED_TRAINING.md) with your approved paired domain
audio and general replay, explicitly selecting `--model-family english_specialist`.
Complete a finite smoke and a separately approved main Serverless Job. Retain
full development selection, source/exposure ledgers, `.nemo` and their full GET
checksums before releasing that Job's exact GPU/VM/scratch resources. Do not
stop currently running serving resources. No training is performed at serving
startup, and a ten-step smoke is not a useful fine-tune by itself.

Create a new model-bundle directory **outside the repository** containing only:

```text
model.nemo       # your actual selected, verified English checkpoint
MODEL_CARD.md    # parent revision, training provenance, changes and limitations
MODEL_LICENSE   # applicable upstream license text and derivative obligations
```

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

Discover `GET /v1/models` and the exact native schema using the ordinary key.
For a small audio file, the canonical gateway supports multipart
`POST /v1/audio/transcriptions` with `file`, public `model`, optional
`language=en-US` and `response_format=verbose_json`. Preserve an
`Idempotency-Key`. Its limit is 8 MiB; larger recordings use the existing
begin-upload → trusted byte transfer → finalize artifact → native invocation
flow. A 202 response is durable acceptance, not a transcript: poll the same
operation until terminal and retrieve its full result. Never repeat submission
with a fresh key merely because the worker is cold or queued.

MCP uses the **gateway `/mcp`**, not the worker. Discover tools and call
`get_model_schema` with `{"model_id":"nemotron-speech-en-medical-0-6b","protocol":"native"}`.
Use its returned named tool/schema directly; top-level controls are
`idempotency_key` and `wait_seconds`, not part of the model payload. Transfer
audio through the trusted artifact helper, never base64 in tool context. Poll
`get_operation` and retrieve `get_operation_result`. The generic `invoke_model`
fallback must name the same public App and native protocol explicitly.

For live audio, connect through the authenticated gateway/LibreChat relay to
`/v1/audio/stream`. Public start options identify the chosen App; the gateway
maps it to the English wire options. Negotiate mono 16 kHz PCM16LE, 560 ms chunks
and word granularity. Wait for `session.ready` and verify the loaded checkpoint
before sending PCM. Partial events replace a segment; final events seal it.
Send `input.finish` to flush the tail and require `session.completed`. Only
native word items provide acoustic times; empty items do not permit invented
alignment. Cancel/disconnect must release that session without affecting others.

In the Scientific AI LibreChat client configure canonical API/MCP origins,
ordinary scoped credentials and a new tenant-owned workspace. The requested
selector is English base → exact fine-tune → **same** fine-tune + Sortformer.
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
