# fs2 gateway client contract

This reference supplements `SKILL.md`. Live `tools/list` and
`get_model_schema` remain authoritative for the caller and deployment.

## Transport and identity

- Transport: stateless MCP Streamable HTTP at the exact `/mcp` path. Do not add
  a trailing slash. Use a conforming MCP SDK rather than hand-writing routing
  headers. TLS verification remains enabled.
- Authentication: `Authorization: Bearer <ordinary inference API key>` supplied
  by the client configuration. Never use an admin bootstrap token.
- A practical full-workflow key has `catalog.read`, `inference.invoke`,
  `mcp.invoke`, `operations.read`, `operations.result`, and, if cancellation is
  offered, `operations.cancel`, plus a model allowlist.
- Ordinary serving operation access is tied to the exact submitting key and
  principal. Preserve that identity until required results are retrieved.
- Tool discovery is authorization-aware, private, and uncached. Reconnect after
  replacing credentials or after the operator changes the catalog.

The current server uses MCP SDK 2.1.1 and supports modern and legacy protocol
negotiation. Let LibreChat manage `MCP-Protocol-Version`, request routing headers,
client capabilities and JSON-RPC envelopes. Do not configure those as static
headers because method and tool-name values change per call.

## Limits and retention

The following are source defaults, not promises about every deployment. Use
limits and expiry timestamps returned by the server when available.

| Boundary | Default |
| --- | ---: |
| Raw HTTP/MCP request | 16 MiB |
| Decoded inline artifact | 16 MiB |
| Upstream response body | 128 MiB |
| Stored artifact | 1 TiB |
| Signed upload/download handle | 600 seconds |
| Serving synchronous wait maximum | 30 seconds |

Base64 expands data by about one third. With a 16 MiB raw MCP request limit,
`put_scientific_artifact_bytes` can carry just under 12 MiB of binary data after
JSON-RPC overhead. Large uploads must use the handle returned by the reservation.
Large downloads should use `download_scientific_artifact` or the authorized HTTP
content route. `read_scientific_artifact_bytes` returns base64 and is bounded by
the inline ceiling; its tool response can exceed the chat client's own limit.

Ordinary payload/result TTL defaults to 24 hours and operation metadata to seven
days. Scientific artifacts/results default to 90 days. Use returned expiry
fields; settings are configurable. Request-debug capture is operator-only and
currently has no automatic deletion job. Never assume a chat history is the
durable store for an output.

## Tool families

Core tools cover:

- catalog/schema: `list_models`, `list_scientific_models`, `get_model_schema`;
- serving: `invoke_model`, `get_operation`, `get_operation_result`,
  `cancel_operation`, `acknowledge_operation`;
- scientific runs: `submit_scientific_run`, `get_scientific_status`,
  `list_scientific_events`, `get_scientific_result`, `cancel_scientific_run`;
- artifacts: `begin_scientific_artifact_upload`,
  `put_scientific_artifact_bytes`, `finalize_scientific_artifact_upload`,
  `get_scientific_artifact`, `read_scientific_artifact_bytes`, and
  `download_scientific_artifact`.

There is also one named typed tool per authorized App. A 2026-09-09 all-model
acceptance key saw 27 named tools: 14 native, two OpenAI-chat and 11 scientific
batch Apps, including an independent App clone. Restricted keys see fewer.

## Scientific batch document

The typed named tool exposes the exact fields. The canonical run schema is
`fs2-serve.nebius.ai/scientific-run-request/v1`, including the advertised
operation, an allowed `service_class`, a finalized `input_manifest`,
model-specific `parameters`, and optional `client_context` identifiers. Use one
logical `batch_id` with distinct correlation IDs for related items. Do not
invent service classes or infrastructure priority; use discovery values.

For files, reserve/write/finalize each real input, build a manifest containing
the immutable returned references, serialize it canonically, then upload and
finalize the manifest. Fixture artifact IDs in examples are not caller-owned.
After submission, poll status/events and wait for result publication. The
scientific result describes attempts, execution identity, semantic validation
and output artifacts. Download the output manifest and its entries; verify exact
SHA-256 and byte size.

## Selected runtime compatibility

- Boltz2 is the protein-only portable runtime. It requires explicit A3M beneath
  each polymer and does not expose NIM ligand, DNA/RNA, affinity, constraint,
  template, step-scale or full-PAE features.
- OpenFold2 accepts exactly `input_id`, uppercase canonical `sequence`,
  `selected_models: [1]`, and `relax_prediction: false`. It has no external
  MSA/template, ensemble or relaxation path in this deployment.
- NVIDIA BioNeMo Agent Toolkit instructions and scripts remain useful domain
  guides, but many call NVIDIA REST URLs, use different authentication and
  expect immediate response JSON. Installing them does not redirect those calls
  to this MCP server. Adapt invocation to the discovered named tool and durable
  result flow; never drop unsupported inputs or fabricate missing scores.
- OpenFold3 native and OpenFold3-OpenBind scientific batch are separate Apps.
- AlphaFold3 and other licensed/academic runtimes require operator-prepared
  assets and applicable terms. Model access does not itself grant a license.
- There is no OpenAI token streaming guarantee, no universal NIM parameter
  parity, and no assumption that a discoverable App is already warm.

For exact examples and selected-runtime sources, call `get_model_schema`.

