# Skill adaptation readiness report — 2026-09-09

Adaptation of the packed agent skills to the scientific model gateway
(`https://89.169.99.188`), per `/home/tux/model-skill-adaptation-instructions.md`.
Branch `agent/bionemo-librechat-20260907` (commits `504f5e5` baseline,
`9823149` adaptation). Customer key: MysteryBox
`nebius-scientific-model-gateway-20260908` (`SCIENTIFIC_MODELS_API_KEY`);
on 2026-09-09 the operator supplied the canonical `fs2_pat_…` key, which was
stored as the new primary secret version `mbsecver-e00khf53t8gey7qd9y` and
locally at `~/.config/fs2-gateway.env` (0600, outside any repo). All live
verifications below were re-run with this key (openfold2 sync 200 conf 93.22;
boltz2 op `adff65b2-a479-42db-ba65-6b0b68c07ee0` → succeeded). Running
endpoints created before the rotation still hold the previous env-secret
binding and pick up the new primary on next start/redeploy.

## Live catalog observed 2026-09-09 (this key only)

- Native/OpenAI (16): altumage, boltz2, cosmos3-nano, diffdock, evo2-40b,
  genmol, molmim, msa-search-pdb70, nv-reason-cxr-3b (openai-chat),
  nv-segment-ct, openfold2, openfold3, phenoage, proteinmpnn, qwen3-8b
  (openai-chat), sdxl.
- Scientific batch (11): alphafold3, bindcraft, boltzgen, esmfold2,
  esmfold2-fast, mosaic, openfold3-openbind, proteina-complexa, protenix-v2,
  rfdiffusion, app-95943840d2b14a65b5cdaa4717b2cdc3.
- The typed-MCP release exposes 19 core workflow tools plus one named typed
  tool per authorized App. The all-model acceptance key saw 27 named tools
  (46 total). `get_model_schema` returns exact flat inputs, examples, sources
  and active runtime identity; normal clients no longer need adapter-source
  inspection or speculative live probes.

## Per-model status from the original adaptation

This table preserves the local/live checks completed before source `5de025fe`.
It is not the current schema-discovery status; use `get_model_schema` for that.

| Model | Lane | Contract source | Example + validator | Local test | Live verification |
| --- | --- | --- | --- | --- | --- |
| boltz2 | native | `models/bionemo/boltz2/server.py` (variant `boltz2-hf-portable`) | yes | pass (incl. ligand/DNA rejection) | **pass** — 202 → op `9ef197ba-d7fb-4152-b839-b14241909738` → succeeded; mmCIF + confidence + ptm scores |
| openfold2 | native | `openfold2-upstream/server.py` `parse_request` | yes | pass (exact-4-fields, [1], relax=false) | **pass** — sync 200, conf 93.2, pLDDT array, ~1 s |
| diffdock | native | `structure/runtime/adapters/diffdock.py` | yes | pass | not tested |
| proteinmpnn | native | `adapters/proteinmpnn.py` | yes | pass | not tested |
| genmol | native | `bionemo/genmol/server.py` | yes | pass | not tested |
| molmim | native | `bionemo/molmim/server.py` | yes | pass | not tested |
| msa-search-pdb70 | native | `bionemo/msa-search-pdb70/server.py` | yes | pass | not tested |
| openfold3 | native | `structure/openfold3-preview2/server.py` parser | yes | shape only | not tested |
| altumage | native | `aging/contracts.py` (20318 CpG) | shape only | n/a | not tested |
| phenoage | native | `aging/contracts.py` (ClinicalRequest) | shape only | n/a | not tested |
| sdxl | native | `general-media/sdxl_server.py` | partial | n/a | not tested |
| evo2-40b | native | pending probe | partial | n/a | not tested |
| nv-segment-ct | native | pending probe | partial | n/a | not tested |
| nv-reason-cxr-3b | openai-chat | pending probe | partial | n/a | not tested |
| qwen3-8b | openai-chat | standard chat | partial | n/a | not tested |
| cosmos3-nano | native | pending probe | partial | n/a | not tested |
| alphafold3, openfold3-openbind, protenix-v2, esmfold2, esmfold2-fast, proteina-complexa, bindcraft, boltzgen, mosaic, rfdiffusion | batch | `catalog/runtime/schema/*-parameters.schema.json` + scientific-run-request v1 | shared `scientific-batch` skill | shape only | not tested |

## Notes / remaining integration gaps

### Continuation acceptance, 2026-09-09 11:55–12:04 UTC

Fresh SDK discovery validated all 46 tools / 27 model contracts. The old
`evidence-typed/model-schemas.json` has empty batch schema objects despite its
zero-error summary; use the new private `live-20260909-continuation/model-schemas.json`.

| Model | Current live result |
| --- | --- |
| diffdock | Succeeded, `91c4bef9-9dcf-4dfb-a1f8-44eabd0d646e`; one SDF ligand pose and finite confidence, result retrieved; ~6.57 s admission-to-completion |
| msa-search-pdb70 | Failed, `c622c651-b23a-4093-86eb-a196aec6a2cc`; upstream HTTP 500, three platform attempts, no error detail |
| proteinmpnn, genmol, molmim, openfold3, qwen3-8b | Live published examples passed JSON Schema but named calls returned MCP `isError: true`, generic “Error executing tool” and no operation ID; admission outcome is unknown, not proof no job was created |
| esmfold2 | Succeeded, `956415b1-7b3f-4540-9ffb-eb710356dde0`; actual input and canonical manifest uploaded/finalized, client disconnected and resumed the saved ID, semantic validation passed, output manifest and both output files downloaded and SHA-256/size verified |

The intentional OpenFold2 extra-field check returned JSON-RPC `-32602`,
`data.type: model_input_validation`, with the allowed field list. This confirms
the advertised pre-admission validation path, independently of HTTP status.
These are customer SDK checks, not LibreChat UI acceptance or multi-user proof.

Client helpers: `tests/live_serving.py` and `tests/live_batch.py`. Evidence must
remain outside source control, with the same directory/key used on reconnect.
They do not acknowledge or cancel operations. Four offline tests cover MCP
error envelopes, canonical JSON and digest/length mismatches. Skill tests: 8 pass.

The gateway/tutorial/batch skills now explicitly disable attachment-bridge and
viewer claims for this deployment. The old helper code remains legacy, not a
compatible fs2 integration. Saved scientific agent instructions are supplied in
`scientific-agent-instructions.md` for the scientific image seeder.

Remaining backend errors require operator investigation using the private
receipts, submission times and idempotency keys; no platform code was changed.
Multi-user isolation needs two distinct operator-provided customer keys, which
are not available in this session. Other batch Apps and large-file signed-handle
acceptance remain untested. The user has additionally requested a full model
picker/tutorial usability review and integrated redesign on the branding branch.

- The previous public-schema gap is closed by `get_model_schema` and flat typed
  named tools. Twenty-five current Apps publish validated examples. AltumAge
  and NV-Segment CT deliberately require complete domain assets rather than
  fabricated tiny examples.
- Handoff's priority list (proteina-complexa, boltzgen, mosaic, bindcraft,
  rfdiffusion, esmfold2/f2-fast, protenix-v2, alphafold3) exists on the
  scientific batch lane of this key; native lane has no rfdiffusion/proteina.
- Evidence snapshots: `/home/tux/fs2-skill-adaptation/evidence/` (models.json,
  scientific-models.json, mcp-tools.json).
- Live smoke operations used idempotency keys `skill-adapt-*-20260909a`.
- `seed-workbench.js` now attaches complete live MCP servers through its
  `mcpServerNames` dynamic wildcard instead of pinning the invalid old
  `scientific_models__*` IDs. The old artifact bridge still speaks a ClawBio
  upload protocol and must be replaced before file-based workflows are advertised.
