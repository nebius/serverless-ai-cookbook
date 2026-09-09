---
name: scientific-gateway
description: Use the hosted fs2 scientific and inference Apps through their typed MCP tools. Apply when discovering models, choosing an App, preparing model inputs, submitting or resuming work, polling an operation or scientific batch, uploading inputs, downloading results, or explaining a gateway error.
license: Apache-2.0 AND CC-BY-4.0
---

# Scientific model gateway

Use the `bionemo-models` MCP server. Authentication is supplied by LibreChat;
never ask for, print, copy, or place an API key in tool arguments. The caller's
key determines the visible Apps and owns the resulting operations and artifacts.

## Discover before invoking

1. Call `list_models` and `list_scientific_models` when the requested App or
   current availability is not already established in this conversation.
2. Call `get_model_schema` with the selected public `model_id` and protocol.
3. Use the returned `contracts[].tool_name`, flat `input_schema`, examples,
   source references and active-runtime identity. Independent Apps using the
   same underlying model remain separate Apps.
4. Prefer that named typed tool. Do not infer fields from a model's name, an
   NVIDIA REST example, or an old skill. Re-discover after an authorization,
   missing-tool, or stale-schema error.

Named serving tools accept the model fields directly plus optional
`idempotency_key` and `wait_seconds`; named scientific tools accept the
scientific run fields directly plus optional `idempotency_key`. Do not wrap new
calls in `payload` or `request`. Do not send `model` to a named OpenAI-chat tool:
the App already selects it. The generic `invoke_model` and
`submit_scientific_run` envelopes are compatibility routes for model-agnostic
clients, not the default for a skill-directed call.

If this skill disagrees with the tool's current schema, the tool schema wins.
Do not silently omit unsupported scientific inputs or switch models. Explain the
specific incompatibility and ask the user to choose a supported workflow.

## Submit once and resume

- Create one stable idempotency key of 8–200 characters per logical submission.
  Reuse it only with the identical payload after an uncertain transport failure.
  A corrected or deliberately new request gets a new key.
- Set serving `wait_seconds` to `0` unless a short bounded wait materially helps.
  Submission returns a durable operation/status record, not the final prediction.
- Save and report the operation ID. Poll `get_operation`; use
  `get_operation_result` only after `result_available` is true.
- Scientific submissions return an operation plus batch state. Poll
  `get_scientific_status` and incrementally read `list_scientific_events`.
  Wait for result publication, then call `get_scientific_result` and retrieve
  the returned artifacts. Execution success alone may precede publication.
- Treat `queued`, `activating`, and `running` as progress. Do not resubmit or
  cancel because a chat/tool timeout elapsed. Terminal states are `succeeded`,
  `failed`, `cancelled`, `preempted`, and `expired`.
- Download and verify outputs before `acknowledge_operation`; acknowledgement
  purges an ordinary retained payload/result.

## Scientific artifacts

Chat attachments and local paths are not gateway artifacts. For every input:

1. Read the actual caller-owned bytes outside the language-model context.
2. Compute exact SHA-256, byte count, media type and compression.
3. Call `begin_scientific_artifact_upload`, transfer using its returned handle
   or `put_scientific_artifact_bytes`, then finalize.
4. Build a canonical manifest from the returned immutable artifact references;
   upload and finalize that manifest too.
5. Submit the named scientific tool with the finalized manifest reference.

Never invent or reuse another user's artifact ID. Keep large base64 values and
structure/media files out of chat. MCP inline transfer has base64 overhead and
is suitable only below the advertised ceiling; use returned upload/download
handles or the HTTPS artifact path for larger files. Check handle expiry.

## Errors and user-facing results

- MCP `-32602` with `data.type: model_input_validation` means no work was
  admitted. Use each issue's JSON-pointer `field`, `rule`, and any
  `missing_fields`, `allowed_fields`, or `expected` details to fix the input.
- For 401/403 or a missing App, check this user's key and current catalog. Never
  substitute an admin credential or claim academic eligibility in the request.
- For 429, retryable 503, or an interrupted submission, retain the same
  idempotency identity, back off, and check the saved operation.
- For a terminal model failure, report the public model/App, operation ID,
  timestamps and returned structured error. Do not label acceptance as success.
- Serving `get_operation_result` returns `{operation, result}`. Scientific
  results are versioned run documents whose output manifests point to artifacts.
  Preserve structured fields and verify artifact hashes rather than pasting raw
  files into the answer.

Model access is authorization, not a license grant or biological/clinical
validation. Describe outputs as model predictions. Do not invent snapshot,
replica, priority, or GPU controls in model payloads; those are platform settings.

Read [the complete client contract](references/client-contract.md) for transport
limits, scopes, retention, scientific-file details, and known BioNeMo differences.
