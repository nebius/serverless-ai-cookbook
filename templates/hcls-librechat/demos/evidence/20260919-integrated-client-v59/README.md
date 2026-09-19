# v59 candidate: direct-coordinate evidence and admission acknowledgement

This successor addresses two failures from the
[v58 customer cohort](../20260919-integrated-client-v58/customer-path.md).
It does not change scientific requests, inference settings, resource limits,
timeouts, retries or the dedicated-instance-per-user architecture. Building or
testing it locally is not deployment or completed customer qualification.

## Coordinate and confidence provenance

A completed batch producer records its output manifest and artifact files.
When downstream preparation references a coordinate artifact directly, the
runner now carries that same producer's manifest after checking recorded bytes,
directory, coordinate entry and operation identity. It does not scan neighbors,
guess metadata from filenames or change the immutable plan/selected structure.
Explicit paths still require explicit metadata; absent confidence stays absent.

The correspondence helper verifies the selected coordinate bytes against one
manifest entry, preserves exact raw confidence JSON and its sample/seed lineage,
and retains the envelope consumed by the existing structure report. Duplicate,
changed or incompatible evidence is not converted to an invented confidence.
CRLF coordinate bytes are preserved rather than silently normalized.

An offline replay of the actual v58/04 files restores the exact model-native
values in metrics and short/assembled reports while preserving coordinates,
residue mapping and geometric results. All 195 retained original files remain
unchanged; no inference or original-output repair occurred. Private receipt
`v59-direct-confidence-retained58-r2/receipt.json`, SHA256
`dd1447d560a6ff9fea7e2d82a26207e9dfd6d658c83c517e13a04fb86cc5d87d`.

## Deterministic pending-study response

The pinned LibreChat graph recognizes only a just-completed, single exact
`run_scientific_workflow` tool call with a confirmed durable admission and
matching call/Study identity. It emits a normal assistant message containing
the saved Study ID, observed pending state and Runs link. It does not invoke
another model to invent protocol details or scientific results after admission.

Original tool messages stay intact. Unrelated, multi-tool, legacy, malformed,
failed, unknown or terminal outcomes, newer user turns and unresolved upstream
tool calls keep their existing route. Re-entry does not emit a duplicate
acknowledgement. This is an admission UX fix, not an assertion of completion.

Twenty-seven candidate tests cover the selector, exact pinned graph execution,
real graph streaming events, matching stream/state message IDs, ordinary END
and final-text detection, absence of provider initialization, unchanged error
paths and the exact retained v58/07 receipt. The original first stream-test
failure is retained; typed-content emission was corrected. This proof compiled
the candidate patch against v58 dependencies in memory: it is not the final
v59 installed-image or live Mongo/browser persistence test.

## Published image and installed gate — 21:41 UTC

Runtime source `a996ce38e21bb4a31e6545f22b3c32ca0465d960` is pushed on the
existing workbench branch. Image `lc:r0919-v59-a996ce3` is published in the
existing `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh` registry:

- OCI index: `sha256:20748e8b3ace7552cd3a340959bf024f9064435b8eaa87e0c56f94b948590e73`.
- Runtime manifest: `sha256:ac2afd835fa84007e2420bbd5e9cd14a50adbe336b5a5fb7693448b3201af5e7`.
- Remote index, source label and bound build attestation were verified before
  pulling that exact image for the installed gate.

The gate passed all 318 domain tests (all 295 predecessor cases retained, no
skips), 10 publication-lock tests, 11 actual SDK/stdio cases, seven CPU studies
and 41 independently checked output files. All 28 source-bound runtime hashes
match. The 27 admission tests now exercise the **actual already-patched image
Graph**, including its streamed message identity and END behavior; the Graph's
separately captured hash is unchanged before/after. No installed runtime files
were overlaid and no hosted model calls were made.

Four candidate-source React tests and compiled-bundle presence passed, but are
not live-browser or Mongo persistence evidence. Private gate
`workbench-v59-installed.n36jopqs/acceptance.json`, SHA256
`be2ea29623ce227eb83254563b1b77ba5a70b073c81f13cd640839b8c155a18c`.

## Local customer-state migration rehearsal

The exact v59 image passed the existing isolated retained-state rehearsal:
49 Mongo collections, 81 documents, 334 index definitions, two state files,
eight preserved seeded-agent IDs, original user/password and actual HTTP login
with one conversation/two messages before and after restart. The post-login
snapshot remained exact. Six binding tests passed without skips; the container
was stopped and its data/evidence retained. No cloud calls or model inference
occurred, and Rene's actual client was not changed.

This is local migration mechanics, not fresh cloud activation or customer-path
acceptance. Original custom-agent and uploaded-file categories were empty;
their content migration is not established by this fixture. Private receipt
`rene-replacement/v59-local-acceptance.json`, SHA256
`31b47b063dc40c2337b76778864f8aa1fe4baf1bddcf08dc19eedf9cca1f19d2`.

## Remaining acceptance / deployment blocker

Fresh customer paths, including persisted admission acknowledgement and verified
final browser downloads, remain required on this exact image. The previous
four-person v58 cohort and earlier releases cannot qualify v59. The full ten
dedicated-user cohort and two clean unchanged-release cohorts remain open.
Six user deployments remain blocked by provider Internal responses; observed
quota headroom is not a diagnosis. Rene's existing client remains unchanged
until qualified state-preserving replacement. Backend190 is already deployed.

A bounded project-only read at 21:43–21:46 found no verified unused public-IP
cleanup candidate. All 45 visible allocations were assigned; the only public
one belongs to the existing Kubernetes gateway. None of the 22 visible VMs or
allocations matched the 42 selected retired preview identities/backing VMs.
Seven direct retired-VM reads returned NotFound, including backing VMs of three
endpoint records with previously rejected deletions. Those endpoint records are
not relabelled deleted. These APIs do not reconcile the earlier Serverless/quota
usage counts; provider-side correlation is required. No resources or quotas
were changed. Private report `orphan-preview-readonly-20260919/REPORT.md`, SHA256
`cf6520d1ace1f77b49b73c47fd4b54cc4a81a6b94ff440d66e8a3885164b7625`.

No whole-platform, snapshot-speed, model-quality or clinical-validation claim
is made by these fixes.
