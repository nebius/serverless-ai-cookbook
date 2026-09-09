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
