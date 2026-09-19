# Ten scientist journeys: retained customer-experience assessment

Evidence cutoff: **2026-09-19 04:32 UTC**, before the campaign's 06:04 deadline.
This is an end-of-window handoff checkpoint, not the campaign owner's final
verdict or operation-count aggregation. No new calls, deployments or artifact
corrections were made for this assessment.

Real customers obtained useful, independently checked files in several bounded
journeys. That is not evidence of ten clean completions or one qualified final
release. Some reports needed substantive operator correction; the latest
robotics journey still lacked a complete customer-delivered dataset/report.
Clinical drafts retained useful source evidence but remained incomplete and
unsuitable for a medical-readiness claim.

## Rubric and attribution

The rows follow the **original expanded study assignments**, not later reuse
of the same numbered API credentials for unrelated tests. The earlier R3–R11
campaign used different assignments and is not substituted here.

- **Verified delivery:** the requested bounded files were retrieved and their
  reported checks independently reproduced. Actual browser download is stated
  separately; workspace/API retrieval alone does not prove a clickable UI path.
- **Recovered delivery:** useful files exist, but explicit technical or
  methodological intervention was required. This is not an unassisted success.
- **Partial delivery:** some requested outputs exist, but the report, provenance,
  requested constraints or final customer retrieval remains incomplete.
- **Assistance:** an ordinary continuation only asks the agent to finish/reopen
  existing work. It is distinct from teaching the analysis method, correcting a
  conclusion, repairing source/deployment, or downloading results as an operator.
  Same-turn self-correction is recorded but is not operator intervention.

These are delivery assessments, not scientific pass/fail scores. A faithfully
reported negative result can be a useful research deliverable. A successful
operation, plausible structure, changed pixels or a keyword in quoted context
cannot establish the requested scientific or clinical conclusion.

## Original personas and retained outcomes

| Persona / original customer task | Best retained client delivery by cutoff | Assistance and unexpected friction | What remains unproved or blocked |
| --- | --- | --- | --- |
| **01 — single-protein structure comparison**: predict ubiquitin and compare with experimental 1UBQ, preserving inputs/results/methods. | **Verified delivery, v36.** One natural turn, one prediction; independent structure/confidence checks and actual browser download of the 1,411-byte methods note. Measured 76-residue C-alpha RMSD 3.1440 Å. | 46.709s conversation; two invalid wait-argument calls self-corrected. No operator continuation in this fresh run. | One single-sequence example, not general predictor accuracy or biological validation. Earlier failed client baselines remain. |
| **02 — heteromer comparison**: Boltz2 and Protenix on 1ACB/2PTC, exact supported settings and experimental comparisons. | **Recovered delivery, v37.** Four structures, contacts and whole/per-chain RMSDs independently match; corrected 7,088-byte report downloaded in the browser. | One ordinary continuation **plus a separate explicit methodology correction** of the false universal seed7 claim; Boltz's request had no seed setting. Three analysis scripts self-corrected. Earlier artifact-metadata rejection and reversed chain mapping required client/backend repairs. Existing Boltz results were reused, not a fresh four-call v37 cohort. | Correctly reported poor query-only Protenix reference agreement remains (whole-complex RMSDs 18.508/18.023 Å, zero native contacts). Neither corrected prose nor successful execution makes those predictions accurate. |
| **03 — PD-L1 design comparison**: Proteina-Complexa and BoltzGen files, count/provenance and model metrics. | **Recovered delivery, v18/v22.** Retrieved Proteina addendum has all 56 checked numerical entries and eight sequence hashes; separate BoltzGen report, ranking CSV and structure were retrieved. | Wrong target, raw-gzip input rejection, incomplete reports and object-store directory handling needed repairs/continuations. Explicit pinned-source review corrected the mistaken yield interpretation: `num_samples=4 × best_of_n.replicas=2` gives eight search outputs, not eight independently requested samples or MPNN sequence clones. | No new clean natural replay after the later runtime repairs. Filter completion/confidence is not binding efficacy, and the later API-only Proteina variant studies do not replace this journey. UI click-to-download was not independently re-established by this assessment. |
| **04 — design/sequence/refold funnel**: Mosaic, BindCraft, RFdiffusion, ProteinMPNN and OpenFold2 with auditable correspondence. | **Recovered delivery, v23.** All five original operations completed; retrieved 8,656-byte versioned report and supporting files retain the actual provenance-bound 76-position comparison. | HTTP429 from overlap, a background workflow lost with its shell, and failed analysis scripts remain. Recovery explicitly taught hash-bound residue correspondence for a poly-glycine backbone; a further report correction fixed confidence/count statements. This was substantive assistance, not merely “continue.” | Refold-versus-design C-alpha RMSD 8.0355 Å is poor self-consistency despite mean pLDDT 82.465. Different targets/protocols cannot be ranked as a model leaderboard. No binding or experimentally useful design claim; browser-click delivery not newly verified here. |
| **05 — docking and molecular generation**: reference-frame redocking, exact chemical measurements and reproducible report. | **Verified bounded successor delivery, v37.** Four DiffDock runs plus one 16-molecule GenMol run; all 16 pose and 16 molecule rows independently agree, with actual browser download of the 15,020-byte report. | One ordinary continuation and one self-corrected wrong-path script; no manual numeric coaching in this fresh study. Earlier inverted atom mappings, incorrect prose/counts and ignored uniqueness instruction remain failures; original MolMIM 7/8 exhaustion remains an explicit search shortfall. | The new prompt explicitly excluded a MolMIM rerun: v37 is not new MolMIM coverage, but that exclusion is not a failure to follow its prompt. GenMol masks are not heavy-atom bounds. Poor estradiol poses (best 15.787/17.283 Å) remain alongside good benzamidine examples; no affinity/efficacy claim. |
| **06 — plant-genome continuation**: six frozen chloroplast windows × two seeds, capability limits and retained results. | **Recovered delivery, v23.** Twelve requests/results and every length, GC/diversity/reference comparison independently checked; corrected 7,252-byte report retrieved. | Earlier Evo2 shared-memory deadlock was a software failure, not ordinary queueing. Original report confused milliseconds with seconds; version2 required correction. Later smaller genome studies under another key and chemistry/planner experiments do not count as a fresh completion of this persona's original twelve-case task. | Continuation is not variant-effect/likelihood scoring or reproduction of the Evo2 paper. Six reference-identical suffixes do not rule out training overlap. UI click-to-download not newly re-established here. |
| **07 — aging-clock reproducibility**: exact NHANES units/coefficient version and AltumAge feature-order matching. | **Verified delivery, v34.** One natural turn; all 32 PhenoAge and 17 AltumAge outputs independently reproduced, original rows retained, assembled 13,279-byte report matches browser-downloaded bytes. | 150.054s, 17 tool calls, no failed tools in this fresh run. Final URLs were inline code rather than clickable anchors; navigating to the exact URL enabled download. Earlier invented reference architecture/coefficient mismatch, unnecessary uploads and an unsolicited invalid probe remain recorded. | Only one matched AltumAge sample across orders, not 16 paired replications. Numerical reproducibility is not population, diagnostic or clinical validity. |
| **08 — speech-to-evidence-linked medical draft**: three English ASR Apps, German clip and the complete original English consultation. | **Partial clinical delivery, v39.** Four real ASRs and the full unchanged 6,817-byte draft input; seven clinical files plus index browser-downloaded and hash-matched. Literal source phrases/context replaced the earlier invented medication spelling. A separate full retained German ASR draft also produced seven verified browser downloads. | English needed two ordinary continuations; the separate German draft needed one. Earlier shortened input and v36 invented medication remain rejected. Live v39's WER code/table differed and keyword-based completeness prose was unsupported; tested offline corrections were **not deployed/adopted**. | Neither draft is a complete/validated medical report. English selections cover 18/20 declared segments, not all facts. German planned examination/blood draw remain context/review rather than selected plan facts; “Befunde” blurs self-report versus measured findings. The short non-patient negative correctly produced no report but only a generic error; its typed UX fix is source-only. |
| **09 — six MindEval consultations**: two profiles × three clinicians, full transcripts, judgment provenance and cautious comparison. | **Recovered delivery, v19/v22.** Six complete 21-message records and all transcripts independently downloaded/hash-checked; all 126 original message contents preserved. Corrected 9,582-byte report retrieved. | Original export truncated transcripts; v22 recovered the same records without new inference. Report interpretation required explicit correction, including removal of an unsupported significance cutoff. | A remaining prose count says 12 pooled axes where saved analysis has 10. Axes are not independent replicates; two profiles do not establish comparative clinical efficacy. Later API MindEval tests are not a fresh natural-browser recovery. |
| **10 — recorded robotics augmentation**: native video plus LeRobot dataset, unchanged wrist media/numeric records and temporal comparison. | **Partial delivery, v39.** Third turn ended 04:26:29; native video succeeded/downloaded. LeRobot succeeded **3.789s after** the response, so its interim status was honest. Customer workspace had a 4,357-byte report but zero-byte provenance. At 04:29, separate operator recovery decoded the dataset and verified 6,144 nonvideo values and exact untouched wrist bytes/pixels; it explicitly did not qualify natural delivery. | First two turns stalled; third took 405.573s/28 tools, recovered wrong-parallel-plan429 and hit two 30s status disconnects. NumPy serialization and incomplete local result recovery remained. Earlier wrong V2V choice and unselected-camera re-encoding are preserved. | Complete customer retrieval/provenance/report remains open. Operator recovery and scripted release179 success do not close it. Whole-sequence controls do not guarantee isolated relighting, action alignment or policy-training utility. Client v41 deployment was still blocked by provider `Internal` at cutoff; backend updates cannot repair the old client by implication. |

## Waiting, capacity and intervention are different measurements

Keep conversation time, active execution, service intervals and GPU occupancy
separate. For01, the 46.709s conversation included a 3.024631s service operation
and 1.279685s model-reported inference; none is a substitute for the others.
For06, the twelve-case workflow was 390.58s, summed service intervals107.253s,
and model-reported generation34.309s. The retained verifier explicitly does not
attribute the difference to queue/poll/GPU overhead without traces. For05,
172.936s and108.593s are the two active chat turns; intervening reviewer idle is
not a model latency. Ten's late terminal event is not evidence of a 405s GPU job.

The campaign exercised one active operation per key, real cold starts and
capacity waiting. But the RFdiffusion429 from overlapping calls, Evo2 deadlock,
client 30s observation failures, malformed artifacts and provider model404 are
not legitimate capacity waits. Endpoint creation `Internal` was not proven to
be a quota boundary. Limits were not raised to obtain these outcomes. Historical
missing Pod/node/GPU attribution remains unknown; do not assign a ready Pod or
zero GPU use retrospectively. Root's accounting report owns measured totals.

Operator repairs, supported preview replacements and explicit new planner
cohorts were substantial campaign work. GLM's retained unavailable-model404
preceded an explicitly selected DeepSeek0813 cohort, not silent fallback; later
catalog reappearance did not rewrite that failure. The latest rows span several
client/backend releases. They cannot qualify one homogeneous release, ten users
sharing one execution instance, or chat persistence across replacement.

## Practical remaining customer gates

1. Finish the robotics request through the actual deployed client, with readable
   provenance, complete downloaded bundle/report and honest temporal comparison.
   Preserve the already-successful operation; don't infer delivery from backend
   status or replace this with the separate scripted179 study.
2. Demonstrate deployed, reproducible clinical reporting methodology: exact
   scorer version/normalization, source-linked coverage with omissions, and an
   actionable no-report outcome. Existing offline/source-only repairs do not
   establish adoption, clinical completeness or medical correctness.
3. Treat the recovered03/04/06/09 reports as assisted research deliverables;
   substantively corrected methods are not clean natural first passes. Retain
   02's methodology correction and05's original MolMIM exhaustion; do not
   silently convert the latter into new successful generation coverage.
4. Keep independent reference checks in the delivery gate. Confident reports
   repeatedly misread correct model files; a service-success dashboard alone
   missed those customer-facing errors. No automatic ten-persona completion
   total or readiness score is assigned here.

## Evidence and version boundaries

Documentation correction at 05:21 UTC: row03 previously misdescribed the two
best-of-N search replicas as sequence/refold replicas. The pinned-source result
in the browser campaign ledger establishes `num_samples × best_of_n.replicas`;
this wording correction adds no experiment or independent scientific replicate.
The original 04:32 evidence cutoff and all intervention limitations remain.

The detailed [natural browser ledger](../20260918-scientist-cohort/EXPANDED_BROWSER_CAMPAIGN.md)
preserves prior releases, failures, source/image pins and report hashes.
The [clinical reproducibility note](../20260919-clinical-reporting-reproducibility/README.md),
[German clinical cohorts](../20260919-german-clinical-v39/README.md),
[scripted robotics179 note](../20260919-lerobot-public-r179/README.md), and
[bounded admin/observer177 note](../20260919-admin-observer-r177/README.md)
cover distinct scopes; none silently upgrades the natural-client rows above.
All-App/protocol coverage and numeric operation aggregation are separate owner
deliverables, not repeated as persona completion counts here.

Protected paths below are relative to campaign `browser-evidence/`. They are
receipt references, not public URLs; raw chats/payloads and signed links remain
private. SHA256 binds original bytes. Rows03/04/09 are capture receipts, with
the substantive independent checks in the linked ledger; they are not mislabeled
as fresh browser-click tests.

| Persona / receipt | SHA256 |
| --- | --- |
| 01 `scientist-01-v36-independent/final-receipt.json` | `db31bf5efa996314f8ab2be72197f974ceb6f5b8e18e4f8ec68961732f32981a` |
| 02 `scientist-02-v37-corrected-report/receipt.json` | `11cde5161dbf9737f9332cb11ee73d85a17db2f93a604fe8844b51cc89341e46` |
| 03 `scientist-03-v22-final-v4/receipt.json` | `6938fa8275c663dc25db528490a371136609bcaf8abf54488ee55f95c1beba56` |
| 04 `scientist-04-v23-final/receipt.json` | `a6176fe1e5dd521f3c3999883c44f65b07b7c19042aae459a851cb151189f016` |
| 05 `scientist-05-v37-independent.json` | `7f2b3f173cc11760889c4274f8775d19717eaa5e9c31d39787d6c81882afca38` |
| 06 `scientist-06-v23-independent-verification.json` | `b6408f5b58f4bc0d763c57533eb23d3ab4aae10fda075f32fac93b5542afc5d7` |
| 07 `scientist-07-v34-independent/final-receipt.json` | `14ca589fafa6f0786e5d5bcdc83c8e6c1618323e52817d4b4a2b51ed3c850152` |
| 08 `scientist-08-v39-final/acceptance-receipt.json` | `bc3586eaa02fa4144d5c41a838c96dbc244c0b0d8ce05b54ad46277612c45d7f` |
| 08 separate German `scientist-08-herzrasen-v39-final/cohort-completion-receipt.json` | `43fc5b4cc3bc7a774bc15f339f4662dc12780b798e33c6861f0586b7f266d912` |
| 09 `scientist-09-v22-recovered-deliverables/receipt.json` | `5dcf57818d1a18ad4b8ab5ab8ddda5e0835a5bd6dd4af7ed24150c36b5cffccf` |
| 10 `scientist-10-v39-third-turn-final/receipt.json` | `2d43e9c3e58c1cf6d16cde2cd5821a57ffc7585b89e5f07a84c6c6e6f217cf7c` |
| 10 separate operator recovery `scientist-10-v39-third-turn-independent/independent-validation.json` | `e0717d6eb3e2ce5a049b2e190b9eb8c4744ba542f256c81f3cdcea65a499b5d1` |

The underlying inputs, original incorrect reports and failed admissions remain
unchanged. The assessment does not contain credentials, endpoint addresses,
patient payloads or guesses about unavailable measurements.
