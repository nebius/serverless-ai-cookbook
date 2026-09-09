---
name: scientific-gateway
description: Shared manual for the Nebius scientific model gateway. Read first to discover models, choose the right invocation lane, submit once with idempotency, poll operations, and handle errors and artifacts.
license: Apache-2.0 AND CC-BY-4.0
---

# Scientific model gateway (shared client manual)

All model skills share this contract. Config comes from the environment, never
hard-coded: `SCIENTIFIC_MODELS_API_BASE_URL` (HTTP, e.g. `https://89.169.99.188/v1`)
and `SCIENTIFIC_MODELS_MCP_URL` (MCP) with the non-admin key
`SCIENTIFIC_MODELS_API_KEY` (`Authorization: Bearer <key>`). These match the
`FS2_BASE_URL` / `FS2_MCP_URL` / `FS2_API_KEY` conventions. Never embed keys in
skills, examples, logs or chat. This key is a customer inference key, not an
admin credential; there is no academic self-assertion flow.

## Discovery (always confirm before first use of a session)

- HTTP: `GET /v1/models` (native and OpenAI-compatible serving) and
  `GET /v1/scientific-models` (scientific batch profiles).
- MCP: `list_models`, `list_scientific_models`.
- A model entry records: public `id`, `capabilities` (`native` | `openai-chat` |
  scientific batch), `operations`, `revision`, `active_runtime.variant_id`,
  `active_runtime.relationship`, `nim_artifact_parity`, and license/use policy.
  Being listed does not mean a model accepts chat messages. NIM artifact parity
  is generally unverified: describe runtimes by their variant, not by NIM
  package claims. Model lists are scoped to this key; do not reuse another
  customer's cached list. Availability changes; re-discover when a call 404s or
  403s.

## Three invocation lanes — keep them distinct

| Contract | HTTPS | MCP |
| --- | --- | --- |
| OpenAI-compatible | `POST /v1/chat/completions` with the model's OpenAI payload | `invoke_model` with `protocol: "openai-chat"` |
| Native HTTP | `POST /v1/models/{model_id}:invoke` with `{"operation": "<advertised op>", "payload": {...}}` | `invoke_model` with `protocol: "native"` and the **inner model payload** |
| Scientific batch | `POST /v1/models/{model_id}:submit` with the run document | `submit_scientific_run` with `model_id` and `request` |

`invoke_model` arguments: `model_id`, `protocol`, `payload`, `idempotency_key`,
`wait_seconds`. Convenience tools exist per model (e.g. `boltz2_predict_native`,
`submit_alphafold3`); their `payload`/`request` schemas are intentionally
generic `object` — the real payload contract lives in the model skill. For a
native model with several operations, use the HTTP wrapper's explicit
`operation`; do not guess what a convenience tool selects. Never call the
internal pod `/biology/...` paths on the public gateway.

## Submit once, then resume

- Generate an explicit idempotency key (8–200 chars) per logical request. On
  transport retries or uncertain outcomes reuse the **same key and same
  payload**. A corrected payload or deliberate new run uses a new key. Keep a
  private mapping: workload item → key, payload hash, operation ID.
- A submission may return the result directly or `202 Accepted` with an
  `x-fs2-operation-id` header and `Location: /v1/operations/{id}`. Accepted is
  not completed.
- Poll `GET /v1/operations/{id}` (MCP `get_operation`); scientific jobs also
  expose `get_scientific_status` and `list_scientific_events`. The same path
  returns different document shapes for serving vs batch — parse what is there.
- Queued/loading/running states are ongoing work. Honor `Retry-After`; else
  bounded backoff with jitter. A wait deadline yields a resumable operation ID,
  never a duplicate job or a "model failed" claim. Never cancel ongoing work
  because a client timeout elapsed. Do not invent payload flags such as
  `gpu_snapshot=true` or promise unmeasured cold-start times.
- On terminal success fetch `GET /v1/operations/{id}/result` (MCP
  `get_operation_result`, scientific `get_scientific_result`); wrappers differ
  — normalize JSON/text/binary/artifact outputs deliberately. Download needed
  artifacts and verify declared hashes. Call `acknowledge_operation` /
  `POST .../:acknowledge` only after the user has their outputs: it purges the
  ordinary result payload.

## Errors: make them useful, not retry loops

| Observation | Behavior |
| --- | --- |
| Local schema failure | Explain the exact field/type/format problem first; do not guess scientific inputs. |
| 400/422 or MCP invalid args | Inspect response detail and the submitted payload before assigning blame; an adapter may map execution errors to 400/422. Correct demonstrated input errors; never blind-repeat. |
| 401/403, unknown model, policy error | Check endpoint/key/model grant; re-run discovery. Do not switch tenants or invent access flags. |
| 404 | Check saved operation/artifact ID and retention; another tenant's objects are never accessible. |
| 409 | Read the error code: idempotency payload conflict, unfinished result, expired/purged result need different actions. |
| 429 / retryable 503 / transport | Reuse request identity, back off, check the existing operation, stop at deadline. |
| MCP HTTP 200 | HTTP 200 alone is not success: check JSON-RPC errors, `isError`, structured content, and final operation status. |
| Terminal failed/preempted | Preserve evidence; distinguish platform retries from a new user-authorized submission. |

For support keep a private debug record (endpoint, method, model ID, runtime
revision, UTC timestamps, request/operation IDs, idempotency key, attempts,
outcomes, elapsed time, submitted payload, returned error) without secrets or
signed download tokens. Give the user a short summary plus correlation IDs.

## Scientific batch requests are real

Run document schema `fs2-serve.nebius.ai/scientific-run-request/v1`: `schema`,
`operation`, `service_class` (`presentation`, `interactive`, `customer-batch`,
`bulk-backfill` — use one your key may select; checked-in examples typically
use `customer-batch`), `input_manifest` (artifact ref), `parameters` (≤256
properties), optional `client_context` (`batch_id`, `correlation_id`,
`display_name`). Artifact refs require `artifact_id`, `sha256` (64 hex),
`size_bytes`, `media_type`. Upload real input bytes first
(`begin_scientific_artifact_upload` → `put_scientific_artifact_bytes` →
`finalize_scientific_artifact_upload`), then build the manifest from returned
immutable pointers, computing hashes/lengths from the actual bytes. Checked-in
`public-request.json` files are templates with fixture IDs — always materialize
this customer's artifacts; never send local paths or invented artifact IDs.
Batch by model-native batching only if the schema supports it; otherwise
independent jobs with shared `client_context.batch_id` and distinct item IDs at
bounded concurrency. Never alter replicas, node groups, priorities or quotas
from a client skill.

## Model-specific contracts

Each model skill states the exact public ID, protocol, operation, bounds and
one minimal valid example. Model IDs to expect (verify via discovery; keys
grant different subsets): native `boltz2`, `openfold2`, `openfold3`,
`diffdock`, `genmol`, `molmim`, `msa-search-pdb70`, `evo2-40b`, `proteinmpnn`,
`altumage`, `phenoage`, `nv-segment-ct`, `nv-reason-cxr-3b` (openai-chat),
`qwen3-8b` (openai-chat), `sdxl`, `cosmos3-nano`; scientific batch
`alphafold3`, `openfold3-openbind`, `protenix-v2`, `esmfold2`, `esmfold2-fast`,
`proteina-complexa`, `bindcraft`, `boltzgen`, `mosaic`, `rfdiffusion`.
Keep `openfold3` (native) and `openfold3-openbind` (batch) distinct.
