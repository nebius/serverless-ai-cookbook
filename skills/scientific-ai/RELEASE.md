# Scientific AI skills 2026.09.20.2 — source integration

Updated the portable ClawBio catalog for the optional pinned native CPU/hosted-App
extension in the full LibreChat image. The public core remains 31 skills;
ClawBio-enabled images add 48 namespaced skills and an isolated runtime. External
clients and skills-only images do not acquire that runtime from this bundle.
No release asset, default deployment image or existing endpoint was changed by
this source merge. See `templates/hcls-librechat/clawbio/README.md` in the source
repository for extension preparation and its separate qualification limits.

## Previous published release: 2026.09.20.1

Scope: one public, checksummed skill bundle and its skills-only LibreChat image,
not a requalification of every deployed model. See the repository's
`docs/scientific-ai-skills-release-20260920.md` for the completed test receipt.

## Changes

- Consolidated 23 existing customer skills and their clinical scripts/references
  under one path; added eight workflow skills (31 total).
- Mapped all 37 Apps in the public catalog observed on 2026-09-20.
- Corrected RFdiffusion source roles, Boltz2 affinity claims, missing-file/viewer
  claims, client portability and optional infrastructure assumptions.
- Added pinned NVIDIA attribution and hosted-API adaptations, an offline EN/DE
  lexical ASR evaluator, portable contract tests, deterministic archives and
  conflict-preserving installation. Moved the large ProteinMPNN teaching input
  out of the model's skill context.

## Remaining gaps, not concealed by this release

- Full agent-led GPU workflows across all 37 Apps, long-recording streaming,
  load/scaling and snapshot performance are not newly benchmarked here.
- Upstream capabilities beyond our adapters remain unavailable: ligand affinity
  through protein-only Boltz2; predicted labels/DE through the current scVI API;
  automatic browser live-microphone support from installing a skill alone.
- DICOM conversion needs a qualified local converter; the skill does not ship a
  clinical imaging stack. Scientific/medical outputs still require appropriate
  independent evaluation.
- The optional ClawBio and MindEval servers, private Sword artifacts, official
  private Nebius infrastructure extensions and an external client's local file
  executor are not installed by downloading this bundle.
- Cosmos Transfer 2.5 is described conditionally, not advertised as public merely
  because an operator-side implementation exists. Starter-pack coverage can lag
  the live catalog; recipes must be checked against actual files and contracts.
- Existing per-user cloud endpoints are not replaced by this publication. The
  release image can be selected for the next controlled customer rollout.
