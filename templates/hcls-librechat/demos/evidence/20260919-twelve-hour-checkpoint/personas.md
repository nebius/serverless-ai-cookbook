# Ten-scientist checkpoint: what customers actually received

This is a synthesis of retained evidence, **not another test or readiness review**.
The original assignments and evidence through04:32 UTC are preserved in the
[ten-persona assessment](../20260919-persona-customer-experience/README.md).
Only08 and10 below incorporate the later natural v42 studies, completed by
05:21:21 UTC on19 September2026. Other numbered API-key reuse, scripted tests
and later backend repairs do not become fresh completions of those personas.

Useful research deliverables reached customers. **Ten clean, unassisted journeys
on one final release were not demonstrated.** Ordinary “continue existing work”
requests differ from teaching the analysis method or correcting conclusions;
both remain visible below. A delivered negative scientific result can be useful,
but successful execution does not make a prediction accurate.

## Customer-delivery matrix

| Scientist and original work | Best retained delivery | Assistance / remaining customer friction | Scientific or coverage limitation |
|---|---|---|---|
| **01 · single-protein structure** — OpenFold2/ubiquitin versus experimental1UBQ | v36: one natural turn, prediction, independently checked structure/confidence and actual browser download;46.709 s. | Two invalid wait arguments self-corrected. Earlier failed baselines remain; not a zero-error run. |76-residue C-alpha RMSD3.1440 Å is one comparison, not general structure accuracy. |
| **02 · protein complexes** — Boltz2/Protenix on1ACB and2PTC | v37 recovered four structures and checked contacts/whole/per-chain RMSDs; corrected report browser-downloaded. | One ordinary continuation **and explicit methodology correction** of the false universal seed7 claim. Existing Boltz results reused; not four fresh v37 calls. | Poor query-only Protenix agreement remains:18.508/18.023 Å whole-complex RMSD and zero native contacts. No binding or general accuracy claim. |
| **03 · PD-L1 design comparison** — Proteina-Complexa/BoltzGen | v18/v22 recovered reports, ranking/structure and verified Proteina numerical/sequence provenance. | Target/input/runtime repairs, continuations and explicit pinned-source yield interpretation were required. No clean natural replay after later repairs; this assessment did not newly verify UI clicks. | Four requested samples × two best-of-N search replicas are eight outputs, not eight independent requested samples. Confidence/filter completion is not binding efficacy. |
| **04 · design→sequence→refold** — Mosaic, BindCraft, RFdiffusion, ProteinMPNN, OpenFold2 | v23 recovered all five original operations and a provenance-bound76-position comparison/report. | Overlap429, background-shell loss and analysis errors; operator taught residue correspondence and corrected report statements. Substantive assistance, not just continuation. | Refold/design RMSD8.0355 Å is poor self-consistency despite mean pLDDT82.465. Different targets/protocols are not a valid leaderboard. |
| **05 · docking/chemistry** — DiffDock and GenMol, with earlier MolMIM search | v37 bounded successor: four docking requests,16 poses and16 generated molecules independently checked; report browser-downloaded. | One ordinary continuation and a self-corrected wrong path; no manual numerical coaching in this successor. Earlier incorrect analyses/uniqueness handling remain. | MolMIM was explicitly excluded from the new prompt, not newly qualified; its original7/8 exhaustion remains. Poor estradiol poses coexist with good benzamidine examples. No affinity claim. |
| **06 · plant-genome continuation** — six windows × two seeds | v23 recovered twelve outputs and checked lengths, GC/diversity/reference comparisons; corrected report retrieved. | Original milliseconds/seconds error required correction; earlier shared-memory deadlock was software failure, not legitimate queueing. No new UI-click proof in this assessment. | Continuation is not variant-effect/likelihood scoring. Reference-identical suffixes do not exclude training overlap or reproduce the paper. |
| **07 · aging clocks** — NHANES/PhenoAge and AltumAge ordering | v34 one-turn numerical delivery;32 PhenoAge and17 AltumAge outputs independently reproduced; browser-downloaded report,150.054 s. | No failed tools in that successor. Final paths required navigation rather than clickable anchors. Earlier incorrect reference methods and unsolicited probe remain. | Only one matching AltumAge sample across orders; numerical reproducibility is not held-out mortality/clinical validity. |
| **08 · speech/medical documentation** — English study plus German drafts | v42: English full-source draft, full German draft and expected short-source **no-report** outcome;24 actual UI downloads verified. Four WER bundles and one source-selection bundle replay exactly. | English needed **two ordinary continuations**; German full/negative each one turn. No fresh ASR: four earlier operations reused. Ad hoc comparison falsely counts0 accepted facts versus actual32; prose still makes a false omission and unsupported WER explanation. | Literal offsets/context do not prove clinical meaning, speaker attribution or completeness. Full German has no human-reference WER. Typed negative UX works; no clinician/patient-use qualification. |
| **09 · MindEval** — two profiles × three clinicians | v19/v22 recovered six complete21-message records, all126 original messages and corrected report. | Original export truncation and unsupported significance threshold required explicit correction. Remaining prose says12 pooled axes where saved analysis has10. | Axes are not independent replicates; two profiles do not establish clinical efficacy. Later20-profile API batches are separate from this natural journey. |
| **10 · recorded robotics** — native transfer plus two-episode LeRobot augmentation | v42 delivered both outputs, nonempty provenance and report; four actual UI downloads match storage.128 rows/6,144 nonvideo values and untouched wrist media independently preserved. | **Two ordinary continuations**,733.373 s end-to-end. Wrong tool names, non-seekable NPZ write and overlap429 self-recovered; no method/tool coaching. Final paths still needed Workspace navigation. | Whole-sequence transfer selected correctly, but action alignment/policy utility remains unproved. “Luminance” was RGB mean;63.6 s admission/activation was mislabeled pure cold start; motion/frame counts cannot establish contact/trajectory preservation. |

Rows01–07/09 derive from the linked historical assessment and its exact receipt
index, not a fresh re-execution. Detailed successor evidence:
[clinical08 v42](../20260919-natural-clinical-v42/README.md),
[robotics10 v42](../20260919-robotics-natural-v42/README.md), and the
[full natural-client ledger](../20260918-scientist-cohort/EXPANDED_BROWSER_CAMPAIGN.md).
Earlier substantive interventions and failures were not erased by later delivery.

## What changed for08 and10

Both used client source`7674a107eeeb2fce5782030c872adad91e966add`, image index
`sha256:ffc003193e5e26886ad1c5f3278b2e6a07e6c1dd51234131c8da901b0256fc81`,
DeepSeek-V4-Pro-0813/low, unchanged8192 output/131072 context and original keys,
buckets and tool/concurrency budgets. Original prompts changed only their output
directories. Their broader conversations span the CP182 rollout, not one frozen
182-only release; no model-runtime change was introduced by that rollout.

**Clinical:** English took810.688 s/three user turns; full German130.983 s/one;
negative70.097 s/one. The actual new draft jobs took37.720 and56.134 s; the
expected negative completed in4.122 s. Two uploads and three clinical jobs are
counted separately; all four ASR operations were reused, not newly executed.
Pinned measurements are now used naturally
and reproduce exactly: English262/1412,315/1412,341/1412 errors/reference words;
short German3/25. The separate agent-written comparison still looks for the wrong
document fields, confuses rejected wording with absent meaning, and incorrectly
attributes WER deletions to case/punctuation removed by its own normalization.
The German agent also confused missing human-reference text with inability to
measure source selection. Operator-only accounting is not credited as natural
delivery. These are report-analysis defects distinct from working ASR/service,
literal-source checks and the fixed `no_supported_clinical_facts` response.

**Robotics:** native operation`2d71b327-b9ff-483e-a623-ca8324ab5a67` and dataset
operation`ec11ee3f-d64c-4cc3-ab92-71d7386d9ddc` completed. The dataset includes two
native inference children; uploads/probes are not extra model calls. The selected
camera changes and untouched-camera preservation were verified, but native and
dataset settings differ, so their quality is not a matched-parameter comparison.
Delivery closes the earlier missing-artifact/provenance gap for this bounded
successor, not the physical-validity or narrative-accuracy gap. No30-second status
disconnect occurred in this fresh study. No final customer file was manually
corrected to obtain a pass.

The [clinical receipt](../20260919-natural-clinical-v42/receipt.json) is bound by
SHA256`d93ad8ee30b4414f3e2eb1493de5ddb1ceac73d37f060aa79ed68b4a2ec04d11`.
The robotics note binds its exact operations, dataset/video and four downloaded
files. Protected raw conversations and payloads remain outside Git.

## Model/mode gaps, without turning personas into an all-App test

The [all-App overlay](../20260919-campaign-coverage/README.md) is a separate
**04:37:11** evidence snapshot covering35 captured App instances/33 identities:
32 H100 campaign models, deliberately excluded GLM5.2 and two disabled clones.
Its configuration inventory is not execution attestation. This synthesis does
not update that historical matrix or replace the campaign owner's newer totals.

- **Breadth versus customer delivery:** bounded API results exist for additional
  Apps including AlphaFold3, ESMFold2/Fast, OpenFold3/OpenBind, MSA search, CT/CXR,
  diarization/TTS, SDXL and Qwen3-8B. That is not a natural scientific workflow
  for each App, nor proof of every advertised option. GLM/clones remain excluded.
  Native Qwen3-8B is not the separate Token Factory planner/patient/judge service.
- **Design protocols:** bounded Proteina protein/ligand/AME and all six BoltzGen
  protocols are evidenced across different releases, with raw versus refolded
  roles and evaluator reassessments preserved. RFdiffusion motif preservation
  and downstream computational refolds do not establish affinity, developability,
  stability or a newly clean03/04 customer journey.
- **Scientific quality/search:** MolMIM finite-search exhaustion, poor complexes,
  low contact recovery and extreme docking poses remain observed limitations.
  MSA-assisted monomer tests do not qualify every paired-complex/ligand path.
  Aging formula agreement and source-faithful clinical excerpts are not clinical
  generalization or correctness.
- **Snapshots:** the overlay binds strict Cosmos CUDA/CRIU witnesses to the exact
  native runtime and checkpoint. The LeRobot coordinator is not itself GPU
  snapshotted. Other Apps receive **no new exact-current-runtime snapshot
  qualification from this overlay**; older implementation evidence is not
  discarded, but cannot transfer automatically across images/GPUs/options.
  Warm-host-cache restoration is not empty-node/image-pull cold start.
- **Elastic behavior:** global operation counts, waiting/capacity/preemption and
  fairness are owned by the final campaign report, not inferred from this table.
  GPU reservation is not utilization; customer elapsed time is not GPU time.
  The [capacity note](../20260919-capacity-wait-fairness/README.md) and
  [recovery reassessment](../20260919-batch-recovery-reassessment/README.md)
  retain their explicit windows and the still-unqualified live recovery gate.

The immediate remaining gate is trustworthy end-to-end scientific delivery:
retain correct model bytes **and** correct schema-bound analysis, cautious
interpretation, usable downloads and recoverable progress. API success alone
did not establish that. This note assigns no10/10 score or platform-wide go-live
decision; the campaign owner's checkpoint report records the overall decision.
