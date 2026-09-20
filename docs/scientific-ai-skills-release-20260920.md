# Scientific AI customer skills release — 2026-09-20

Version: `2026.09.20.1`. Authoritative path: `skills/scientific-ai` in
`rene-tech/serverless-ai-cookbook`. This is the same source copied into LibreChat
and packaged for customers using other MCP clients.

## Scope and ancestry

Based on workbench commit `1250a009e72e7e8d02ba62c7f3a63752322eb719` (runtime
source `7524b8c33e4e7d7cc92af51c0e61b8ff46ab5b33`). The user fork's previous
`main` was `9a8fa2d126f6edc00dda9736b578b725d1c20302`, an ancestor. Integrating
this release therefore also preserves the existing workbench/BioNeMo branding
and client work instead of leaving it accessible only on long-lived branches.
This does not newly qualify every inherited template or change upstream Nebius.

Included branch ancestry: `agent/scientific-ai-workbench-v2-20260918`,
`agent/librechat-scientific-branding`, `agent/bionemo-librechat-20260907`,
`agent/bionemo-workbench-3-0`, `agent/bionemo-2-1_hdw227`,
`agent/create-bionemo-agent_bj5027`, and `agent/add-to-git_vp4ce2`.
No branch deletion, force-push, customer-instance replacement or changes to
parent-thread Stockholm cleanup are part of this release.

Separate unmerged work such as `agent/scientific-video-augmentation-20260919`
contains an additional preview/approval workflow with failed GPU qualification
recorded at `2c2e1a9`; it is not silently included as a ready feature here.
Other infrastructure-template and BioIR research branches are unrelated to this
skills consolidation and remain unchanged.

## Changes

31 customer skills: the existing 21 model/workflow skills plus clinical
documentation and infrastructure preparation, and eight new workflow skills:
speech, clinical ASR evaluation, single-cell analysis, Cellpose microscopy, SAM2,
binder campaigns, starter data and MindEval. The new guidance maps 37 observed
catalog Apps and distinguishes our runtime interfaces from NVIDIA upstream.

Corrected contradictions: unconditional RFdiffusion source versus motif PDB;
protein-only Boltz2 versus ligand affinity; workspace/viewer availability;
orchestration versus scientific compatibility; large-file/base64 transport;
private infrastructure skills versus portable customer installations.
The long ProteinMPNN PDB moved out of the skill body into a file-client example.

All NVIDIA source revisions, licenses and adaptation differences are recorded
in the bundle. Private `nebius/skills` source is not published and is not a build
prerequisite. Existing private infrastructure extensions are replaced by the
public customer pack in the new image, not removed from any live endpoint.

## Reproduction

```bash
python3 -m pytest skills/scientific-ai/tests skills/scientific-ai/clinical-documentation/scripts -q
python3 skills/scientific-ai/bundle.py verify
python3 skills/scientific-ai/bundle.py check-catalog
python3 skills/scientific-ai/bundle.py build --output /absolute/new-release-directory
docker build -f templates/hcls-librechat/Dockerfile.skills-release \
  --build-arg SKILLS_REVISION=EXACT_SOURCE_COMMIT -t scientific-ai-skills:qualified .
docker run --rm --network none --entrypoint node \
  -v "$PWD/templates/hcls-librechat/scripts/test-skills-installed.cjs:/tmp/acceptance.cjs:ro" \
  scientific-ai-skills:qualified /tmp/acceptance.cjs
```

The installed test uses LibreChat's actual deployment-skill loader, name lookup
and file-resource retrieval, not a replacement parser. The customer installer
checks all hashes, preserves conflicting local skills, includes attribution,
and needs no operator checkout or private GitHub repository. Archive builds
are deterministic, including gzip/tar metadata, and tested after extraction.

Contract snapshot: `tests/contracts.json`, generated from deployed control-plane
source `4f6fbc30d092c8852d1fdb86e4e813ab04df64fd`. This snapshot tests payload
shape, artifact alternatives and forbidden fields, not access or readiness.
The live schema always wins. Tests include rejected Boltz2 ligands, artifact
requests for new Apps, and drift detection for an unmapped catalog App.

The ASR helper preserves existing historical WER normalization, adds explicitly
defined CER and distinct-keyword coverage, and never outputs a clinical verdict.
It is tested against negation/dose changes, CRLF/Unicode hashes, overwrite refusal,
an independent edit-distance implementation and a long character sequence.

## Qualification boundary

This is a tested **skills package and client integration release**, not a claim
that all 37 scientific workflows have just passed customer end-to-end GPU tests.
No model inference, customer account change, endpoint replacement, snapshot
benchmark or medical validation is implied. Known adapter/client gaps remain
listed in `skills/scientific-ai/RELEASE.md` and in the relevant skill.

Completed verification and published artifact identifiers are recorded below
after final-image acceptance.
