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

## Remaining acceptance

Root must freeze/publish the immutable image, run the full installed gate
(including the actual already-patched Graph), and qualify fresh customer paths.
Six user deployments remain blocked by provider Internal responses; observed
quota headroom is not a diagnosis. Rene's existing client remains unchanged
until qualified state-preserving replacement. Backend190 is already deployed.
No whole-platform, snapshot-speed, model-quality or clinical-validation claim
is made by these fixes.
