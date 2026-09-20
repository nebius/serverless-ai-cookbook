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

## Completed checks and artifacts

- Skill-creator validation: **31/31 valid**.
- Portable package, native-contract and clinical-helper suite: **114 passed**,
  plus **31 clinical subtests** (Python 3.12).
- Affected workbench integration/regression suite: **88 passed** inside the
  workbench image's Python 3.11 scientific environment. This includes clinical
  customer outputs/negative outcomes, media guidance, robotics analysis, batch
  client and seeded/configuration behavior.
- Historical test entry point: **20 passed**; it now executes portable tests
  without `/home/tux` paths or the old manually patched MCP tool snapshot.
- Real LibreChat loader on the final built image at 06:28 UTC: **31 skills,
  17 attached resources**, all looked up through actual skill/file APIs and
  all **57 inventoried files** hash-verified. No model calls made.
- Live catalog: **37 visible / 37 covered / 0 unmapped**.
- Archive: deterministic rebuild, extracted verification, install/reinstall,
  tampered-file rejection and conflict preservation tested.

Image source commit: `75a83d5ffc3bfe91d69ccd487b6d0deb168a709b`.
Published image:
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:skills-20260920-v1`
with manifest digest
`sha256:01a9363e53e6cc7e7592af892c960e99410d201c70365c20f8a85b10efe4d94a`.
The application base remains pinned v61; only its skill tree and central skill
routing instructions changed. No existing endpoint uses this image until its
operator chooses a controlled rollout.

Public release tag: `scientific-ai-skills-2026.09.20.1`.
Asset `scientific-ai-skills-2026.09.20.1.tar.gz` SHA-256:
`46db30fa4efde41d9cd1568fe6cc92711dde11b5dff0371cab71311294fa5786`.
`SHA256SUMS` is published alongside it. The release receipt commit only updates
documentation; the packaged skill bytes and image source remain the commit above.

Post-publication customer-path check: downloaded both release assets anonymously
using HTTPS (no GitHub token), verified `SHA256SUMS`, extracted into a fresh
directory, verified all bundle hashes, installed all 31 skills into a new
customer directory and reran the portable suite: **114 passed + 31 subtests**.
The installed ASR helper ran against a synthetic German negation/dose fixture
and returned WER `0.5`, keyword miss rate `1.0`, and clinical correctness
`not_assessed`, as expected. The public `main` manifest and release tag were
read back successfully. `main`, the integration branch and release tag pointed
to `1c93007cd1e27ca2aae6a37ba2be42c071b5c559` at publication.

Navigation follow-up: the live website's existing Get the Skills URL still
targets the historical workbench branch and its old skill directory. The
canonical public destination is now
https://github.com/rene-tech/serverless-ai-cookbook/tree/main/skills/scientific-ai .
The website checkout contains unrelated in-progress visual changes; no website
source, deployment or those changes were modified during this skills release.
Use the canonical link or release asset in customer handoffs until that pointer
is updated in the website's next controlled release.
