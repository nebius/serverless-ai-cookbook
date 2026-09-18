# Natural-language scientist cohort

Prepared 18 September 2026, following R11/v13 browser failures. This is a chat
cohort, not a replacement for the sustained operation campaign. The manager
hands each identity over only after its API study releases the key. Every
inference is bounded by the existing one-operation policy; no doubled key use.

Inputs are frozen public research assets from the qualification manifests.
`stage-scientist-inputs.py` imports and reads back their actual bytes through the
ordinary authenticated Workspace API. Each scientist gets a source index under
`/workspace/scientist-NN/study-inputs/study-sources.json`. This is representative
customer data preparation, not evidence that the agent completed the study.

Keep all turns and failures. Each session has an initial scientific question,
an intermediate revisit after leaving the browser, and a request to export a
verifiable report. Do not prescribe a hidden successful tool sequence. Followups
may clarify user intent but any operator repair counts against clean completion.
Download final files independently and correlate operation IDs with Runs.

## Scientist 03 — design researcher

> I am preparing a small computational PD-L1 binder-design comparison, not a
> therapeutic claim. My prepared public target bundles and source provenance
> are in `/workspace/scientist-03/study-inputs`. Please inspect them and explain
> which comparable studies Proteina-Complexa and BoltzGen actually support here.
> You may run one bounded batch with each: four Proteina candidates with seed 7,
> and the BoltzGen supported batch budget from the target bundle, with at most
> twenty generated candidates. Keep normal production filters. Follow the jobs,
> preserve every candidate and rejection reason that the outputs expose, check
> the target/chain and length constraints, and compare diversity and available
> confidence metrics without equating different scores. Save inputs, operation
> IDs, exact parameters, downloaded output inventory, metrics and a methods and
> limitations report under `/workspace/scientist-03/pdl1-comparison`. An empty
> accepted set is useful evidence; do not claim binding or rescue it by silently
> loosening filters. This request authorizes those two bounded batches.

## Scientist 04 — binder and backbone researcher

> I have staged public target/constraint inputs in
> `/workspace/scientist-04/study-inputs`. I want a traceable design funnel, not
> just successful job submissions. Inspect which inputs belong to mosaic,
> BindCraft and RFdiffusion; do not pretend their targets/protocols are matched
> when they are not. Run one bounded design batch for each supported App, using
> the documented target and original filters, no more than two candidates per
> App. Verify actual sequence/backbone constraints, keep no-winner outcomes,
> and choose at most one eligible backbone for sequence design/refolding if
> those Apps support it. Keep all lineage and compare the refold to its own
> designed backbone. Save a concise report with limitations, files and operation
> IDs in `/workspace/scientist-04/design-funnel`. You may run these bounded jobs.

## Scientist 05 — computational chemist

Use staged public 1A52/estradiol and 1STP/biotin receptor and reference-pose files.
Request matched redocking with three seeds and at most five poses per seed;
withhold experimental ligand coordinates from inference. Compare chemically
valid pose RMSD with explicit atom correspondence and symmetry handling, rank
confidence separately, inspect structures, and export unsuccessful cases too.
Ask the agent to explain bound-receptor/training-overlap limitations and not
substitute a confidence score for experimental affinity. Revisit one existing
run after browser reload, without resubmitting it.

## Scientist 06 — genomicist

Use the frozen Arabidopsis chloroplast NC_000932.1 sequence. Ask whether the
deployed Evo2 contract supports the requested per-position scoring or only
generation. Request a bounded continuation study across six distinct sequence
windows and two seeds, compare lengths/alphabet/reference agreement and GC
content, and preserve conditional probabilities only if genuinely returned.
Unsupported variant-effect analysis must remain an explicit gap, not be
approximated by calling generation and reporting a fabricated score.

## Scientist 07 — aging researcher

Use frozen NHANES complete-case adult laboratory rows and the AltumAge published
example, keeping them as different modalities and populations. Request batch
PhenoAge with exact documented units, an independent published-formula numeric
comparison, and feature-mapped AltumAge inference. Check missing-data behavior
without inventing measurements. Export row-level errors and a reproducible
report; do not infer clinical age, causal effect or population validity from
these selected fixtures. Include enough rows to exercise actual batching.

## Scientist 08 — medical NLP researcher

Use full public/acted English and German teaching consultations with available
human reference material, not a tiny substitute. Request transcription across
the supported speech Apps, WER where ground truth exists, drug/dose/negation
disagreements with timestamps where available, then evidence-linked draft
reports and unanswered questions. A transcript missing a fact must not be
repaired silently from outside knowledge. Reports require clinician review;
absence of German full-recording ground truth remains explicit. Test reconnect
and downloading the actual report bundle from the existing clinical workflow.

## Scientist 09 — conversation evaluation researcher

Use public MindEval profiles and the existing workshop API/panel. Request a
small multi-profile, full ten-turn comparison of three available clinician
families with fixed patient and judge/config. Exercise one intervention in a
separate marked run, not in the paired baseline. Export conversations, complete
criterion scores and paired comparisons; retain failed/unfinished judgments,
family-bias limitations and uncertainty. No Sword private endpoint access.

## Scientist 10 — robotics researcher

Use the documented public robot video and bounded LeRobot dataset. Request one
MP4-to-MP4 lighting augmentation, inspect frame count/codec/readability and
temporal fidelity, then one supported LeRobot-to-LeRobot transformation. Check
episode/frame identity, timestamps, actions and observations against originals.
Ask for execution provenance as well as outputs, and preserve unsupported
transformation or schema behavior. No invented GPU execution from a mere wrapper
receipt, and no unrelated generated video substituted for requested augmentation.

## Completion criteria for each persona

Three separate outcomes: platform completed correctly, scientist finished without
operator repair, and scientific protocol/reference agreement. Two consecutive
clean cohorts on the frozen integrated release remain required by the parent
plan. A few successful studies or uploaded files do not satisfy that gate.
