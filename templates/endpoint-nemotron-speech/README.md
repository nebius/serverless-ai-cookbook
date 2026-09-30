---
title: Deploy stock or fine-tuned Nemotron Speech
category: inference
type: endpoint
runtime: gpu-h100-sxm
frameworks: [nemo, fastapi]
keywords: [speech-to-text, streaming, endpoint]
difficulty: intermediate
---

# 2. Deploy stock or your fine-tuned speech model

One standalone authenticated Serverless Endpoint supports complete-file
transcription and native real-time streaming. No Scientific AI App registration,
platform grant, private checkpoint or separate gateway is required.

1. **Choose weights:** stock English Nemotron is the default (pinned revision
   `ebe59e5a817142986528bbbee5dba8db7b38ed50`). For your fine-tune, attach the
   [training recipe's](../../training/nemotron-clinical-asr/README.md) output bucket
   read-only at `/data` and set the command to:

   ```text
   python /opt/recipe/serve.py --checkpoint /data/runs/YOUR_RUN
   ```

   The endpoint reads and verifies the sibling `model.sha256` automatically;
   you do not copy a checksum into the command. An invalid/missing folder fails
   startup and does not fall back to stock weights.

2. **Stock weights:**
   [![Create stock Endpoint](../assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fnemotron-speech-serve%40sha256%3A62f58367ce6247f4a9e6a2ee255cd607038796d73f5a2583e068f6bdf8498a32&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&preemptible=false&command=python+%2Fopt%2Frecipe%2Fserve.py&volumeMountPath=%2Fdata&volumeSize=100)

   **Your fine-tune:** Replace `YOUR_RUN` in the form's command before creating
   with the run ID from `runs/<unique-run-id>`, and attach its bucket read-only.
   [![Create fine-tuned Endpoint](../assets/create-endpoint.svg)](https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fnemotron-speech-serve%40sha256%3A62f58367ce6247f4a9e6a2ee255cd607038796d73f5a2583e068f6bdf8498a32&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&preemptible=false&command=python+%2Fopt%2Frecipe%2Fserve.py+--checkpoint+%2Fdata%2Fruns%2FYOUR_RUN&volumeMountPath=%2Fdata&volumeSize=100)

   Both buttons prefill the same public image pinned by digest. Review the form;
   choose your project, port **8000**, token authentication,
   100 GiB disk and 8 GiB shared memory. Add secret environment variables:
   `ASR_API_KEYS` = `{"customer-one":"YOUR_RANDOM_32_OR_MORE_CHARACTER_KEY"}`
   and a **different** `ASR_ADMIN_KEY` for operator metrics/drain. Never put
   secrets in a launch URL. More customers get separate backend keys in that map.
3. **Wait for `/readyz`, then transcribe:** save the endpoint URL and edge token
   shown by the console. Use your backend customer key as well:

   ```bash
   curl --fail "$BASE_URL/v1/audio/transcriptions" \
     -H "Authorization: Bearer $ENDPOINT_TOKEN" -H "X-API-Key: $CUSTOMER_KEY" \
     -H 'Content-Type: audio/wav' --data-binary @recording.wav
   ```

This file API accepts a raw mono 16 kHz PCM16 WAV, maximum 5 minutes/16 MiB;
it is **not** the OpenAI multipart API. The JSON result contains unmodified native
`text`, segments and the loaded checkpoint SHA. `/v1/models` exposes that identity.

**Validation scope:** CPU tests and imports passed for these recipe images.
No new GPU training or endpoint validation was run; configured concurrency is
not a measured capacity or production-readiness claim.

## Real-time streaming

Connect to `wss://YOUR_ENDPOINT/v1/audio/stream` with the same `Authorization`
and `X-API-Key` headers. Send:

```json
{"type":"session.start","options":{"model":"nemotron-speech-en-0.6b","language":"en-US","chunk_size_ms":560}}
```

Then send binary mono 16 kHz PCM16 chunks (≤65,536 bytes per message), followed
by `{"type":"input.finish"}`. Keep reading native transcript events through
`session.completed`; do not stitch partial hypotheses into a final transcript.
The [pinned stream contract](https://github.com/rene-tech/serverless-ai-cookbook/blob/db9e31e3ce4f760804b448a846101797111594fa/training/nemotron-clinical-asr/shared-runtime/src/fs2_speech/stream.py)
documents native cancellation and bounded buffering. Browser code must use its
own authenticated backend; do not embed operator or shared endpoint secrets.

## Limits and operations

The existing shared runtime provides isolated stream state, one serialized GPU
lane with fair scheduling, cancellation, bounded admission and graceful draining.
The configured limit of four concurrent sessions is **not measured capacity**.
Busy returns 429; starting/draining returns 503. No clinical/production readiness
claim follows from this recipe. Tune and qualify your exact checkpoint/hardware.
Operator-only `GET /metrics`, `GET /capacity-observation`, `POST /drain` use the
distinct admin key. Customer keys cannot call them or choose a scheduler group.
Before stopping, call `POST /drain` and wait until the authenticated observation
reports zero active sessions, queued actions and in-flight actions. Unexpected
SIGTERM disconnects live sockets and waits for cleanup; it does **not** guarantee
natural transcript completion or automatically replay a request.
Delete only your own endpoint when finished; your output bucket remains separate.

## Optional build

Build [the training image](../../training/nemotron-clinical-asr/Dockerfile), then:

```bash
docker build --build-arg TRAINING_IMAGE=YOUR_REGISTRY/nemotron-train@sha256:YOUR_DIGEST \
  -t YOUR_REGISTRY/nemotron-serve:YOUR_VERSION .
```

This installs a checksummed, immutable shared-runtime dependency; it does not
copy that framework into the cookbook diff or replace its scheduler. Stock weights
download on first start; private tuned weights stay in your mounted bucket.
Keep the upstream model license and human review requirements for any derivative.
