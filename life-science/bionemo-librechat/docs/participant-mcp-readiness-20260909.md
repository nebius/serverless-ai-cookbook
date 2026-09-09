# Stockholm participant readiness: BioNeMo MCP report — 2026-09-09

This report covers the live BioNeMo model MCP used by the deployed Stockholm
notebook agent. Qwen is outside the requested scope. ClawBio and Tavily are
also outside this server report because they are separate integrations.

The notebook under test was
`https://port3080-ryrr5n43y5yz12g.tunnel.applications.eu-north1.nebius.cloud`
(`aiendpoint-e00mhcnw5jpbsg95dk`, image `20260909-cc85e14`). Its chat model was
`zai-org/GLM-5.3-Flash` through Nebius Token Factory.

## What passed

- Direct MCP discovery returned 52 tools and 27 model contracts. Every named
  tool schema matched `get_model_schema`, and every published example validated
  against its advertised JSON Schema.
- All 32 installed notebook skills loaded under GLM: 21 scientific skills and
  11 Nebius infrastructure skills. BioNeMo model health was tested separately;
  loading a skill was not counted as a model pass.
- GLM used the notebook's live BioNeMo MCP connection to retrieve statuses and
  results for the serving and batch operations. It also rendered OpenFold2,
  OpenFold3, and Boltz2 structures through the notebook viewer.
- Ten named scientific-batch models completed with semantic validation
  `passed`. Every output manifest and every referenced output artifact was
  downloaded through MCP and verified against its published size and SHA-256.
- Thirteen of the fifteen in-scope serving routes completed their intended
  modality. MSA Search failed. NV-Reason-CXR accepted a text-only protocol
  check but its required real-image path failed before admission, so it is not
  counted as participant-ready.
- The intentional invalid OpenFold2 request returned JSON-RPC `-32602` with
  `data.type=model_input_validation`. A valid OpenFold2 request then succeeded
  and its 167-atom PDB rendered in the notebook. The earlier OpenFold2 concern
  is resolved.

### Serving operations

| Model | Result | Operation |
| --- | --- | --- |
| AltumAge | passed with a complete 20,318-CpG input | `8b7bc981-d584-4d5c-895c-0c43e3495869` |
| Boltz2 | passed | `2112dc72-da15-4128-a26d-090ac70d2e90` |
| Cosmos3-Nano | passed | `dc306c02-c499-4f58-8935-c6ec23739783` |
| DiffDock | passed; result artifact downloaded and verified | `b7c59642-3c63-451b-880d-f01620263d41` |
| Evo2-40B | passed | `5374271f-4d38-49c1-9f37-1ad746d3a913` |
| GenMol | passed | `ea4b629c-5a8f-4747-bc34-44cdf005df74` |
| MolMIM | passed | `590251ee-9974-4754-ba20-d3718cee98a9` |
| MSA Search PDB70 | **failed upstream** | `5e4fb15e-1f21-4abc-bc45-cfe875fc479a` |
| NV-Reason-CXR-3B | text-only protocol check passed; **real-image submission failed before admission** | text-only `38d4a08a-e62c-4d87-b55e-899eb1fe30e0` |
| NV-Segment-CT | passed with a real gzipped NIfTI fixture | `ddd7d91d-140d-4c04-913e-48260d42d89a` |
| OpenFold2 | passed and rendered | `73f95bd1-21e0-42dc-9a2a-47ab247d986e` |
| OpenFold3 | passed and rendered | `8064cd91-573d-444c-9500-939373cce371` |
| PhenoAge | passed | `11754582-599b-4e92-ada5-76d3040c0211` |
| ProteinMPNN | passed | `5f376363-b9f7-48dd-8ce5-b15139aea20f` |
| SDXL | passed | `addd7e3e-04c6-4c8d-aa52-96dda0937458` |

### Scientific-batch operations

| Model | Result | Operation | Verified output files |
| --- | --- | --- | ---: |
| AlphaFold3 | passed | `320cfb5f-08ed-4c41-a9e8-fd1be6a25d23` | 2 |
| BindCraft | passed | `badfdc5d-bf4a-40d1-98de-4c9af26918ec` | 6 |
| BoltzGen | passed | `ec177508-141c-4712-afeb-eca896f5e885` | 2 |
| ESMFold2 | passed | `33df2c9e-3afc-406c-a980-8d9f549734eb` | 2 |
| ESMFold2-fast | passed | `b1b7659c-5777-4a45-aef3-6cb6993660ec` | 2 |
| Mosaic | passed | `b0a8d6c0-292a-4a83-8c3a-ea9b5114e4f1` | 3 |
| OpenFold3-OpenBind | passed | `58f084a7-94d0-4f58-bd6d-523be8afaa7a` | 3 |
| Proteina-Complexa | passed | `25c13ed8-8241-4cec-b2ea-662e85c7ac76` | 5 |
| Protenix-v2 | passed | `0e07f1fe-1324-4e5f-b06e-c280729486a3` | 3 |
| RFdiffusion | passed | `2251c9fa-9f1c-4bbf-8499-fbcf974e0b9d` | 2 |

## Issues to send to the BioNeMo MCP/server team

### 1. MSA Search returns an upstream 500 on its published valid contract

**Severity:** release blocker for MSA workflows.

The typed tool `msa_search_native` accepted this schema-valid request:

```json
{
  "sequence": "ACDEFGHIKLMNPQRSTVWY",
  "databases": ["pdb70_220313"],
  "output_alignment_formats": ["a3m"],
  "idempotency_key": "skill-live-f35b312d-ff7e-40cc-bb31-d9c206d719ac",
  "wait_seconds": 0
}
```

Operation `5e4fb15e-1f21-4abc-bc45-cfe875fc479a` was accepted at
`2026-09-09T15:23:26.618811Z`, reached ready/running state, and failed at
`15:23:37.918093Z` after all three configured attempts. Its terminal fields
were:

```text
status=failed
outcome=upstream_failed
semantic_outcome=not_evaluated
error_code=upstream_http_error
http_status=500
attempt=3
max_attempts=3
error_detail=null
response_content_type=null
result_available=false
```

The server team should trace this operation through the MSA route and worker,
verify the deployed database name/path and upstream request serialization, and
inspect the three attempt logs. The terminal operation should retain a safe,
actionable failure detail, such as the upstream error class and bounded stderr
or response summary. A participant currently sees only a 500 with no clue
whether the database, sequence, runtime, or dependency caused it.

### 2. MCP collapses distinct failures into `Error executing tool …`

**Severity:** high; this makes retries unsafe and prevents agents from giving
useful recovery instructions.

Several different conditions returned the same MCP result shape:

```json
{
  "content": [{"type": "text", "text": "Error executing tool <tool>"}],
  "structuredContent": null,
  "isError": true,
  "resultType": "complete"
}
```

This was reproduced for:

- concurrent serving submissions rejected while another operation occupied
  the participant key's single admission slot;
- `get_operation_result` for the known failed MSA operation;
- `begin_model_artifact_upload` for `nv-reason-cxr-3b`;
- `analyze_image_openai_chat` with a real chest X-ray.

The same serving requests that initially received the generic error succeeded
when replayed sequentially with the same idempotency keys. This proves at least
some of these errors are admission or concurrency responses, not invalid model
payloads.

Expected behavior is a stable JSON-RPC/MCP error contract that preserves:

- a machine-readable error type and code, for example
  `admission_limit_reached`, `operation_has_no_result`,
  `artifact_upload_unavailable`, or `model_input_validation`;
- whether the request reached durable admission and, if so, its operation ID;
- the idempotency replay status;
- a safe message and field issues where applicable;
- `retry_after_seconds` or equivalent for temporary capacity/admission limits;
- request/trace correlation for operator lookup.

The server should audit the exception path between domain/store errors,
`MCPError`, FastMCP tool dispatch, and the final `CallToolResult`. The working
OpenFold2 `-32602 model_input_validation` response is a good reference for the
level of detail agents need.

One controlled replay narrows this further. From the notebook, GLM called
`infer_openfold2_native` twice with byte-for-byte equivalent arguments to the
original successful request and the same idempotency key
`skill-live-d0e3e3c3-6adb-4988-9621-8090c52f39d9`. Both calls returned only
`Error executing tool infer_openfold2_native`; their saved tool-call arguments
confirm that no field was added, removed, or changed. In the same notebook turn,
`submit_esmfold2` replayed successfully with `reused=true`. Immediately after,
a fresh raw MCP client called `infer_openfold2_native` with the identical JSON
and received operation `73f95bd1-21e0-42dc-9a2a-47ab247d986e`,
`status=succeeded`, `reused=true`.

This differential rules out the OpenFold2 payload and runtime. Investigate the
persistent notebook MCP session, named-tool dispatch after tool-list refresh,
and any per-session admission or exception state. The server and LibreChat
adapter owners may need to trace the two notebook calls together; the server
must still return the underlying structured failure instead of hiding it.

### 3. `list_models` publishes false qualification states for proven-live routes

**Severity:** high for discovery and automatic model selection.

The fresh catalog returned all three fields below as `false` for eight models:

```text
qualification.states.route_active=false
qualification.states.http_mcp_qualified=false
qualification.states.elasticity_qualified=false
```

Affected models: `boltz2`, `diffdock`, `evo2-40b`, `genmol`, `molmim`,
`openfold2`, `openfold3`, and `proteinmpnn`.

Every one of those routes completed a real request in this sweep and returned
a result. These are false negatives in the public catalog. Agents that obey the
qualification fields may hide or reject models that are actually working.

The catalog/qualification reconciler should be checked for stale receipts,
model-ID or variant mismatches, and failure to promote the active route state.
If qualification is unknown or intentionally not asserted for a portable
runtime, publish `null`/`unknown` with an explanation instead of the factual
value `false`. Add a consistency check that compares discoverable active routes
with qualification state after a successful operation.

### 4. Serving-model artifact upload and the real NV-Reason-CXR path fail before admission

**Severity:** release blocker for the CXR model and any serving model that needs
file transport.

With no active batch operation, the generic helper
`begin_model_artifact_upload` failed for `nv-reason-cxr-3b`. The test used a
real 144,679-byte JPEG with SHA-256
`f36d1809cc50c920818d577041963d8d6ec0036ab3928db92264ffce80053f35`,
media type `image/jpeg`, compression `none`, and idempotency key
`participant-sweep-20260909-r1-cxr-upload`. No upload or operation ID was
returned; the only response was the generic MCP error described above.

This is inconsistent with the published generic-helper documentation and the
implementation's stated purpose of accepting an authorized serving or batch
App. The scientific upload aliases worked repeatedly for the ten batch models.
The team should trace the idempotency key through `ScientificInputUploadService`
and verify serving-registry fallback, model authorization, route-enabled checks,
and upload-operation admission for `nv-reason-cxr-3b`.

The fallback request used the published OpenAI-chat contract with a text part
and a real public `image_url`, `max_completion_tokens=256`, `temperature=0`,
and idempotency key `participant-sweep-20260909-r1-cxr-inference`.
`analyze_image_openai_chat` again returned only the generic error and no
operation ID. A text-only request had previously reached the model and returned
its expected request-for-an-X-ray response, so tool registration and basic
text routing exist; the image-bearing path is what remains broken.

Please test both supported image transports independently: an allowed HTTPS
URL and a tenant-owned finalized artifact reference. If remote URLs are
intentionally forbidden, the schema should reject them before admission with a
field-level error and the artifact upload route must work. If the worker failed
while fetching or decoding the image, return an admitted operation with a safe
terminal error instead of losing all correlation.

### 5. Dynamic MCP tool discovery stays stale until a manual reconnect

**Severity:** medium; newly added helpers are invisible to an already-running
participant session.

Fresh direct MCP discovery returned 52 tools. The already-running notebook
session exposed only 46 and omitted the six new generic model-artifact helpers.
Opening MCP Settings and reconnecting the BioNeMo server immediately refreshed
the same user/session to all 52 tools; no deployment restart was needed.

This needs joint server/client ownership triage. Confirm that the MCP server
emits `notifications/tools/list_changed` when dynamic registrations change and
that the advertised capabilities declare list-change support. If it already
does, LibreChat must consume the notification and refresh the saved agent tool
inventory. If dynamic changes are intentionally snapshot-based, expose a tool
catalog revision and make the notebook reconnect automatically when it changes.

### 6. The catalog exposes an opaque duplicate Protenix app as a participant model

**Severity:** medium for discoverability; admission behavior also needs review.

`list_scientific_models` returns both the named `protenix-v2` model and:

```text
model_id=app-95943840d2b14a65b5cdaa4717b2cdc3
display_name=apps-scientific-20260908-scientific-clone-r01
mcp_tool_name=app_95943840d2b14a65b5cdaa4717b2cdc3
parameter_schema=fs2-serve.nebius.ai/protenix-v2-upstream-v2-0-0-parameters/v1
```

The named Protenix-v2 model passed. The opaque clone accepted the same canonical
fixture as operation `c9f10f15-67c7-4f39-a665-6c034788189c`, then remained
queued with revision 0, attempt 0, and both stages pending for more than five
minutes. It was cancelled to avoid delaying the participant sweep.

If this is an admin acceptance clone, remove it from the participant token's
catalog or mark it non-discoverable. If it is intended for participants, give
it a stable model ID/display name and explain how it differs from Protenix-v2.
Also inspect why its scheduling snapshot never advanced while the immediately
preceding named Protenix-v2 operation completed successfully.

### 7. Two usable models have no published minimal example

**Severity:** low to medium; schema-only discovery is much harder for agents.

AltumAge and NV-Segment-CT are the only two of 27 contracts without a published
example. Both models passed after the client constructed real fixtures, so this
is a catalog usability gap rather than a runtime defect.

AltumAge's full 20,318-CpG example may be too large to inline. Publish a small
artifact/fixture reference or an example generator recipe with the exact CpG
ordering and digest. NV-Segment-CT can publish a genuinely tiny valid NIfTI
fixture reference and complete request example. This lets notebook agents
exercise the published path without inventing domain inputs.

### 8. Raw artifact-byte tools are exposed to the language model despite being documented as client-only

**Severity:** medium to high for context size and data handling.

During the notebook batch check, GLM correctly found that each
`get_scientific_result` response contains only an output-manifest artifact
reference. To count its entries, it called `read_scientific_artifact_bytes` ten
times. LibreChat then placed each base64 payload in the model conversation, as
it does with ordinary MCP tool results.

This conflicts with the tool documentation, which describes the byte readers
as intended for non-LLM client code and says their result must not be copied
into another model call. An MCP tool exposed to an agent cannot rely on that
instruction: its result is normally returned to the model automatically. The
same design concern applies to the raw base64 upload helpers.

The ten manifests in this check were small, but exposing general binary reads
can exhaust the chat context and unnecessarily disclose scientific input or
result bytes to the chat model. Keep byte transfer in a trusted UI/client data
plane. Give the agent a compact metadata or parsed-manifest tool that returns
names, media types, sizes, digests, and signed download resources without raw
content. If the byte tools must stay on the same MCP server, exclude them from
the agent-visible tool policy and grant them only to a separate trusted helper
principal.

## Notebook and test evidence

The private evidence directory is
`/home/tux/fs2-skill-adaptation/participant-sweep-20260909-r1`. It contains the
52-tool snapshot, all 27 schemas, per-operation receipts, batch manifests and
hash-verified artifacts, Token Factory responses, and saved notebook
transcripts. No credentials are stored in the source report.

The notebook UI checks completed without browser console errors. The local
agent regression suite passed 45 tests. The serving acceptance helper now runs
sequentially by default because this participant key has a bounded outstanding
operation allowance; parallel submission remains an explicit opt-in for keys
provisioned for it.
