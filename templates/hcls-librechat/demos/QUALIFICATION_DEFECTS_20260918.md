# Qualification defect ledger — 18 September 2026

This is an active campaign ledger, not a readiness report. Raw conversations,
requests, operation IDs, artifacts and deployment receipts remain in the protected
`/home/tux/secure-handoff/scientific-qualification-20260918` evidence directory.

| ID | Observation | Classification | Repair / retest |
| --- | --- | --- | --- |
| Q01 | General chat MCP/execution uses the deployment's model key and workspace, even when the demo panel has a different per-user key. Ten logins in one instance would not emulate ten scientists. | Deployment limitation | Ten isolated dedicated workbenches, ten keys, three lab buckets. All login/catalog/storage bindings verified. Shared multiuser runtime remains outside the qualified claim. |
| Q02 | Runs cannot automatically recover ordinary model calls after a browser/chat disconnect. | Customer recovery defect | Customer-scoped paginated history API plus automatic workbench discovery, atomic per-run cache; backend `0804ea256` deployed Helm152. Live v13 workbench recovered prior API/R11 operations from an empty chat DB. Final-release regression still required. |
| Q03 | Real structural scientist consumed 16 tools/~94.6k context, model succeeded, but requested structure comparison/report was not delivered. Recovery incurred eight Python errors and still no RMSD. | End-to-end workflow failure | Full duplicate catalog instructions conflicted with compact workbench tools. Compact filtered discovery, exact deferred-tool naming, lossless result-to-workspace resolver and batched analysis instructions in `de0c67f`. Fresh unchanged-release retest pending. |
| Q04 | Complex-structure scientist spent ~120k context preparing data, then tight status polling exhausted a turn after admission. | End-to-end workflow failure | Reduce unnecessary schema/data roundtrips, bounded status wait, preserve durable run and avoid claiming completed analysis. Fix/retest in progress. |
| Q05 | Initial campaign harness interpreted `operation: predict-structure` as a nested object, failing after three durable admissions. | Test harness defect, not platform failure | Same idempotency keys recovered the existing operations without duplicate compute. Direct-vs-enveloped parser test added. Keep original harness errors in evidence. |
| Q06 | Initial harness elapsed time measured only the resumed process segment. | Measurement defect | Subsequent cohorts measure from durable request start; original accepted/completed timestamps remain authoritative for the first cohort. Do not quote resume-segment time as model/customer latency. |
| Q07 | Query-only Boltz2 returned valid structures with variable experimental agreement (1BPI repeats differ substantially). Confidence did not rank reference accuracy reliably. | Measured scientific quality, not automatically a software bug | Independent CA RMSD/lDDT, protocol/training-overlap caveats, and genuine MSA-assisted paired studies. Semantic completion is not scientific validation. |
| Q08 | MolMIM claims CMA-ES but samples fixed noise and sorts QED; fallback returns unchanged input and underfills. Portable graph omitted Perceiver residual and fused activation behavior; tokenizer lost stereobonds. | Confirmed runtime/scientific-method defects | Source `86ef55721`: pinned real CMA-ES, graph/tokenizer repairs, exact yield or explicit exhaustion. Twelve CPU tests including retained checkpoint pass; isolated GPU candidate testing underway, production not yet changed. |
| Q09 | Scientist02's bad signed A3M upload failed verification but stayed queued, occupying its only concurrency slot and blocking Boltz2. | Confirmed lifecycle defect | `17fe42abd` terminalizes immutable verification failures with an honest failed outcome and frees admission; preserves retry of missing bytes/transient errors. 48 focused tests pass including real local PostgreSQL; 68 related tests pass (15 integration skips in that separate command). Deployed Helm153, image index `12c7d691eb511855a38a2a823d0441e2af8065c3fa2ea9d8a81eb22e6b996ac8`. No limits changed. An upload with no bytes remains retryable and must be completed/cancelled; do not confuse that distinct state with this immutable-verification defect. |
| Q10 | GenMol requested16 unique molecules but returned15 with success; upstream and adapter both discard invalid candidates. | Confirmed yield defect | `487ddedf4`: bounded replenishment of only missing candidates, exactN success, structured exhaustion and counters. Ten CPU tests pass;38/38 isolated L40S and38/38 isolated H100 requests pass. H100 includes a real second draw after one discarded candidate. Public runtime promotion/retest pending. |
| Q11 | ProteinMPNN1QYS/1TIM HTTP failures coincide with unresolved backbone positions represented by upstream X tokens. | Confirmed runtime boundary defect | `673409230` retains explicit unresolved-position metadata and rejects unexpected X at resolved positions; no invented/deleted residues.36/36 isolated H100 requests pass, including18 historical failures,144 returned sequences. Public runtime promotion/retest pending. |
| Q12 | Verified raw result JSON under `.scientific-runs` exists in workspace but authenticated download gives404; native artifact-backed structures did not render. | Confirmed client artifact defects | Client `aba05a0` allows dotfiles through existing confined authenticated download and resolves native artifacts with unchanged4MiB bound/hash verification. Client tests pass; v14 real browser retest pending. |
| Q13 | Real scientist report claimed calibration from a single structure and softened poor complex metrics. | Scientific communication defect | v14 instructions distinguish confidence/reference accuracy, prohibit calibration claims from one example, and require explicit limitations. Test natural chat narratives, not only operation success. |
| Q14 | Generic runner did not parse OpenFold3 nested CIF; ProteinMPNN reference evaluator counted CA-bearing instead of all input residues. AF3 output packaging also needs inspection. | Qualification harness defects | Preserve original receipts/journal; rerun offline evaluators without duplicate GPU work. Parser correction is not a platform repair or additional model call. |
| Q15 | Proteina analysis-stage input download exhausted connection retries during gateway rollout, after successful GPU stages. | Confirmed artifact delivery failure | `69f2ecbfc`: readiness-gated primary Service, existing artifact Service only as fallback within unchanged bounded retries.52 focused tests pass; broader173 pass plus one reproduced pre-existing execution-map qualification assertion. Deployed Helm154; complete customer rerun remains required. |
| Q16 | Proteina final public artifacts contain raw generated structures, but reported self-refolding metrics refer to AF2 structures that were never exported. | Confirmed scientific artifact-role defect | `141768b42` exports explicit raw/refold roles and CSV-linked per-design provenance, joining actual design identifiers rather than filename order.97 focused tests including retained real handoff pass. Independent raw→refold RMSD matches CSV within1.5e-7Å. Legacy in-flight artifact bounds remain compatible. Helm155 rollout underway; full new-operation qualification pending. |
| Q17 | v15 natural-language studies fail before model admission across protein design, docking, genomics and speech; repeated preparation/tool mistakes consume the interaction budget. | Cross-domain agent/workbench readiness failure | Preserve chats and operator interventions. Test a separately pinned stronger available planning model with the same user prompt and unchanged budgets, alongside correcting stale instructions/tool contracts. A working API or manually executed helper does not close this gate. |
| Q18 | An explicitly selected available chat model was rejected by the workbench's hardcoded model intersection. | Client provider configuration defect | v16 `bedff830` positively includes the explicitly selected model only after checking the live authenticated provider catalog. GLM5.3 scientist03 comparison is running with unchanged tool/output limits. No readiness claim from an initial better planning turn. |
| Q19 | Batch, native and upload receipt writers assume POSIX chmod/atomic rename. On the actual bucket mount chmod fails and five tested rename variants produce empty destination files, including fsync variants. | Confirmed client storage/recovery defect | Unit-only tests missed both behaviors. Shared verified persistence and crash recovery are being implemented and tested against the real mount. No v17 acceptance before mounted-filesystem and same-operation recovery tests. |
| Q20 | Scientist03 supplied Proteina target_id PD-L1 from its PDB filename; GPU generation failed with a generic error. Two pinned scientific target configurations reference that same PDB. | Input guidance/validation and error-reporting defect | Do not silently alias a filename to one of two different hotspot/design configurations. Add exact variant target discovery, early actionable validation, and visible child-process errors; preserve original failure and retest natural scientist selection. |
| Q21 | Mixed study: all20 Qwen forced-tool requests failed; all20 JSON-object mode requests passed;20 plain-chat JSON extractions contained reasoning tags and failed strict JSON parsing. | Advertised-mode/configuration investigation; distinguish model formatting from service rejection | Retained148-call cohort (`general-r1`) has93 verified,27 semantic failures and28 serving failures. Diagnose forced-tool and other failures before changing deployment flags. Native JSON mode is not evidence of full tool-call support. |

Snapshot/fast-start qualification does not automatically transfer to any repaired
runtime digest. Existing checkpoints remain tied to their prior exact runtime;
new candidate tests must establish compatibility or use ordinary loading.

## Checkpoint at approximately 20:40 UTC

The campaign is active until 06:04 UTC. These updates supersede earlier
in-progress deployment notes above; they do not close the customer workflow gate.

- GenMol and ProteinMPNN were promoted through the owner API after Helm157.
  Their 216-case public retest is active; original failures remain retained.
- MolMIM and the Qwen parser configuration were promoted after Helm158, along
  with Proteina target discovery/pre-GPU validation. A mixed108-case public
  replay is active. Qwen thinking-plus-JSON-object semantic limitations remain
  explicit; the parser repair does not establish universal answer correctness.
- Proteina raw/refold provenance is live in157. The first Helm155 attempt
  omitted the matching admin bootstrap baseline and failed. The old gateways
  continued serving; atomic rollback156 recovered. Source29184a211 added the
  fourth immutable map and actual startup validation before successful157.
  The target Apps were temporarily unpublished while drained. Retain this
  deployment failure and interruption; do not claim a seamless cutover.
- Workbench v17 verified small receipt writes against the actual bucket mount
  and independent S3 reads. v18 fixes false tool-schema token accounting:
  210,850 estimated tokens became62,819 against59,869 full-reference tokens.
  Real chats no longer overflow before inference, but several still fail to
  produce promised reports. Model planning and helper integration remain open.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q22 | CT label mode passed9/9; all18 point/combined prompts failed. | Coordinate Tensor/NumPy compatibility fixed in f610deaef, then GPU testing exposed a second missing `skimage.measure` dependency. The first candidate remains failed. Source10aa18eb9 pins dependencies and executes real MONAI component selection at build; candidate v2 H100 replay pending. No live CT promotion yet. |
| Q23 | Evo2 eight8192-prefix/512-output requests exhausted GPU memory and were retried. | Channel-tiled modal-state calculation reduces temporary memory without changing weights/precision. Actual H100 state, logits and seeded-output comparisons are bitwise identical. Full candidate replay underway. A further real test found single-threaded health requests time out during long generation; threaded health plus serialized generation candidate under qualification. |
| Q24 | Pinned client counted strings over4096 characters as one token per UTF-8 byte. | Actual full tokenizer comparison and real schema/chats verify conservative bounded counting repair in v18. No context/output/tool-limit increases. |
| Q25 | Large reasoning-only completions appeared finished without an answer. | Retain default-model failures and explicit same-budget planning-model comparisons. Visible incomplete response and durable recovery are client requirements, not permission to treat reasoning as a delivered report. |
| Q26 | Serial shell commands each waiting30s admitted overlapping long jobs; user limit1 then rejected later stages. | A wait budget expiring does not mean a terminal operation. Implement reusable durable sequencing and existing-receipt recovery. GET `/v1/me` source350663c5b exposes existing caller policy without changing it; next release pending. |
| Q27 | CXR JSON-object requests yielded invalid labels or truncated free-form strings. | Opt-in exact-label bounded JSON Schema recipe passed40/40 public requests over the same20 images and4096 budget; original13/20 success,7 failures preserved. Weak-label exact match remains7/20, not clinical qualification.29/40 execution-attribution records unknown; investigate rather than invent identities. |
| Q28 | Changing a campaign's selected scientist set on resume could repartition cases across keys. | Harness now freezes case ownership and refuses altered resumes or silent legacy migration. Five regression tests pass; this is test reliability, not extra model executions. |

Speech study:119 terminal cases,118 non-empty full-duration transcripts and one
empty German MultiMed193 result. Weighted lexical WER: English Nemotron17.11%,
multilingual Nemotron20.11%, Parakeet23.78%; German multilingual17.02% over101
clips. English consists of two real acted consultations and their quiet and
band-limited versions, not six independent consultations. Overlapping speaker
reference alignment and perturbation dependence remain limitations. These are
not medical-safety scores or clinical-suitability evidence.

Observer retained one actual `/readyz`503 at18:39:31, separately from the initial
wrong-path404 probes. No blanket uptime claim follows from sampled observations.

Observer correction: the first health probe used an unmounted `/healthz` route.
It was changed to the actual `/readyz` contract. That diagnostic 404 is not a
platform availability incident. Helm render comparisons include hooks and
`--is-upgrade`; install-mode hook differences are not deployment changes.

No readiness verdict or paper-reproduction claim follows from these canaries.
Experimental-reference accuracy, service reliability, complete user deliverables,
capacity waits and testing limitations are reported separately.

## Checkpoint at approximately 21:26 UTC

- GenMol/ProteinMPNN public repaired cohort is **216/216 semantically verified**.
  This verifies requested molecular/sequence outputs, not experimental efficacy.
- CT candidate v2 completed **54/54** isolated H100 cases (nine public scans,
  three prompt modes, twice). Evo2 v2 completed **96/96** original cases plus
  two serialized concurrency calls; 260 production-timing health checks passed.
  Exact-runtime public promotion is in progress, not yet customer-qualified.
- Public control plane Helm160 includes exact LeRobot manifest roles, canonical
  artifact-manifest discovery and compressed-byte verification. The corrected
  Proteina request has passed admission and is evaluating its generated designs.
- Workbench v19 scientist01 completed its requested structure report in one
  natural turn. Independent Gemmi/NumPy analysis confirms scientist02's poor
  barnase–barstar result (global CA RMSD15.949Å); a follow-up was required to
  finish its deliverables. Neither study reproduces a paper benchmark.
- v22 client preserves complete MindEval records in content-addressed workspace
  files. Scientists05/08 are now testing chemistry and full-recording medical
  documentation in real browser sessions. Scientist06's previous complex study
  is allowed to finish before its identity is handed to the genomics workbench.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q29 | A valid owned Proteina gzip artifact failed its internal size/hash check although the public stored bytes matched. | Internal HTTP reader transparently decompressed `Content-Encoding: gzip`. Source e2d2e1ff8 uses raw stored bytes, tested for gzip and plain content; deployed160. Keep the original failed admission. |
| Q30 | LeRobot manifest roles were undiscoverable and malformed owned manifests surfaced as misleading404s. | Public discovery now exposes exact source-kind entry names/types and the canonical manifest schema; actionable owned-input errors are422/MCP-32602. No ownership information is disclosed for unknown artifacts. Deployed160; complete LeRobot transformation still blocked by Q31. |
| Q31 | Recorded Cosmos MP4 succeeds with fresh loading but fails after existing GPU snapshot restore at VAE upsampling with CUDA `operation not supported`. | Matched identical-input, same-H100 comparison isolates the restore path. Existing checkpoint must not be treated as qualified. Retain actual restored-worker stderr, use a tested fresh-load fallback, and requalify any replacement snapshot. Fix/promotion in progress. |
| Q32 | Cosmos requested64 video frames but the actual output contains65; response metadata claimed64. | Pinned upstream temporal grid rounds upward. Exact frame handling and independent media verification are required before LeRobot action/frame alignment can pass. Original output retained. |
| Q33 | Restored model worker stderr lived only in a checkpoint-directory file, lost when its Pod was removed. | Outer serving-wrapper log bridge is under test; derive path from the actual checkpoint directory, forward only new lines and preserve source traceback without replaying donor logs. |
| Q34 | Workbench Runs temporarily returned503; an MCP call returned500 without a recovered durable admission. Outer access middleware also manufactures `No response returned` on client disconnect. | Narrow pure-ASGI access logger20c167d6b passes87 focused tests; rollout pending. This proven middleware defect does not establish the cause of every historical500/503. Earlier MolMIM inner200/SSE with zero bytes and incomplete stream remains a failure, not success. |
| Q35 | Root resumed three evaluator cases with system Python lacking NumPy after model work had succeeded. | Harness/operator error, not model failure. Original failures retained; same-operation receipts rescored in the pinned evaluator environment, no duplicate GPU submissions. Pre-admission dependency checks and pinned requirements now prevent this class of mistake. Resume-inclusive elapsed time is workflow latency, not pure inference time. |
| Q36 | MindEval report omitted full transcripts; one narrative invented an unsupported significance threshold. Aging report used slightly different formula coefficients and initially attributed the resulting offset to the runtime. | v22 losslessly exports full records outside context. Independent checks match all48 judgment cells and32 PhenoAge rows to their declared source/coefficients; retain original narratives and corrections. Scientific interpretation remains a separate gate from valid API outputs. |

Deployment-tool note: client-side `kubectl apply` duplicates a large renderer
bundle in its last-applied annotation and exceeds Kubernetes' annotation limit.
The attempted map creation did not change Helm or App runtime references. Use
server-side apply for these exact immutable maps; retain this failed preparation
alongside the subsequent rollout rather than presenting it as a clean first try.

## Checkpoint at approximately 22:27 UTC

- CT and Evo2 successor runtimes were promoted after Helm163 and passed **27/27
  and 32/32** public cases respectively. The earlier161 attempt failed on an
  incorrectly prefixed evidence digest and rolled back162; actual Registry
  startup validation now covers this contract. No failed deployment is hidden.
- ProteinMPNN additionally passed **48/48** multichain cases (three public
  crystal complexes; all, first, second and reversed chain selection; two seeds;
  two omission policies), with192 sequences. Per-chain boundaries, not just
  concatenated sequence length, are verified. No affinity/efficacy claim.
- Scientist03 completed Proteina and BoltzGen with independently verified
  artifact/metric provenance. Scientist04's RFdiffusion→ProteinMPNN→OpenFold2
  chain completed but had8.03548Å mapped self-consistency RMSD despite82.465
  mean pLDDT; its corrected report and contradictory original chat are retained.
- Scientist06 completed12 chloroplast continuation requests with exact pinned
  prefixes/seeds/output checks. Model elapsed34.309s, accepted-to-completed
  sum107.253s, whole workflow390.58s: inter-step overhead is not GPU time.
- Voice coverage passed11 native/streaming cases and seven ASR proxy checks.
  Sortformer full-consultation DER19.68%/18.20%; these are measured quality
  limits, not merely service success. Voice receipts live in the linked task.
- Two H100 preemptibles stopped during live work. Capacity loss is not a model
  failure. Original observer totals included registered stopped GPUs; additive
  ready/schedulable counts now distinguish usable capacity without rewriting
  old measurements. Requests/recovery during this event remain under observation.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q37 | Medical agent sent a278-word summary instead of the full1366-word transcript; the next file-input tool existed but was not seeded into the agent's allowlist. | Workbench source-fidelity/integration defects. v24 allows the actual typed file tool; one new job consumed the exact6817-byte ASR transcript, independently hash-verified. Original summary and tool-schema errors remain failed evidence. |
| Q38 | Automated clinical review normalized ASR “dire light” into a drug name without explicit support, despite instructions; an unclear citation also omitted a supported stool-test fact. | Medical-document quality limitation. Extend existing one-shot citation relocation to unclear and re-review, without auto-acceptance. Drug normalization remains unresolved; clinician checking is required. Full transcript transport does not establish clinical safety. |
| Q39 | Chemistry agent repeatedly reversed RDKit atom mappings, disabled chirality, described wall time as GPU time and misrepresented GenMol SAFE mask token semantics. | Scientific analysis/reporting defects. Strict tested docking helper establishes exact unfitted graph/stereo-aware comparisons; a typed workspace analysis surface is being added because merely documenting the helper did not change fresh agent behavior. Original incorrect analyses retained. |
| Q40 | OpenFold3 complex job hung after a multiprocessing feeder failed to allocate shared memory; GPU remained occupied until public cancellation. | Confirmed runtime defect, not capacity. Pinned inference config inherited ten training-style data workers with64MiB /dev/shm. Source84a466792 uses inline loading and no worker prefetch/persistence; thin exact-image candidate is under real H100 testing with unchanged resource bounds. Production replay/promotion pending. |
| Q41 | CP164 migration initially could not pull its digest from the retained repository: image was published to a sibling repository by operator error. | Deployment/operator defect. Exact repository was repaired; release preflight cfcd66c now reads and hashes that exact published manifest before Helm mutation. Migration/gateways subsequently became healthy, but164 still failed for Q42. |
| Q42 | GPU-observer DaemonSet counted stopped preemptible nodes as rollout targets because it tolerated every NoSchedule taint;164 upgrade timed out and165 rollback is pending. | Platform preemption/release-lifecycle defect. Source4992432d3 narrows default toleration to dedicated GPU workloads, preserving configurable explicit pool keys. Live recovery will set the same exact list; no timeout/limit increase or readiness bypass. Not yet deployed at this checkpoint. |
| Q43 | Fresh Cosmos V4 fully warmed checkpoint copied42GiB but exceeded existing600s CRIU capture limit; prior r7 restore remains CUDA-incompatible for this input. | Snapshot path unqualified. Failed capture is unusable and original checkpoint untouched. Isolated bounded logging/storage optimization is underway; fresh loading succeeds, but snapshot acceleration is not claimed. |

## Checkpoint at approximately 22:59 UTC

- Helm166 deployed with the narrowed GPU-observer toleration. Helm167 then
  deployed only the reviewed CXR runtime maps; its owner configuration was
  applied through the existing drain/ETag workflow. Initial public CXR replay
  now records the actual Pod, node and GPU UUID. Full replay remains in progress.
- OpenFold3's isolated repaired image completed three independent public
  complexes/seeds in38.8–45.0s with unchanged resources. This repairs execution,
  not prediction quality: whole-complex CA RMSD remains14.4–18.9Å. Helm168 is
  deploying its exact execution map together with the preemption repair below.
- Qwen's separate repaired chat/JSON/forced-tool replay passed60/60. Resumed
  MolMIM testing still records structured bounded generation exhaustion where
  the requested constrained yield cannot be met; those are not successful
  molecular-design outcomes and must remain visible to the scientist.
- Cosmos V4 public native inference completed in15.655s; total wait was about
  464s including newly provisioned preemptible capacity and runtime startup.
  Output was independently decoded and hash-verified. Full LeRobot replay is
  running; metadata preservation alone will not establish motion fidelity.
- Cosmos's new quiet-logging snapshot captured in153.73s within the unchanged
  600s limit. Strict same-GPU restore used30.40s CRIU plus5.61s CUDA; donor
  output hashes matched, and unseen cases passed. This is a warm-cache isolated
  result, not yet cross-node or public snapshot qualification. The original
  failed verbose capture and old incompatible checkpoint are preserved.
- Fresh v24 scientist02 and07 studies remain incomplete:02 completed two
  Boltz2 requests but failed Protenix file preparation;07 created unnecessary
  uploads and failed an append on the mounted bucket before any model call.
  v26 adds a typed existing-runner workflow interface and is being built.
  v25 scientist05's16 deterministic docking comparisons were correct, but its
  report still misidentified an extremum. No blanket workbench pass is claimed.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q44 | ESMFold2 operation405cc84b was scheduled on a preemptible node that shut down before the container started. An explicit DeletionByTaintManager disruption was classified as a nonretryable model error; the caller waited1331s. | Capacity loss is not a model failure, but misclassification is a software defect. Sourceb60bdf3f5/cb12da775 recognizes exact disruption evidence without hiding OOM, execution timeout or explicit application errors.169 tests pass; deployment168 and live replay pending. Original failed operation remains immutable. |
| Q45 | All four advertised Proteina ligand/AME variant cases failed although protein-target workflows had passed. Ligand generation/filter succeeded before evaluation failed; AME generation failed immediately. | Broader advertised-mode defects. The ligand Biotite text-mode error masks an earlier RF3 CuEquivariance/PyTorch import failure and empty result. AME correctly configures NAD/OXM, but its feature loader rejects Hydra ListConfig because it accepts only list/tuple. Separate Task Deck ticket owns pinned-source fixes and original-payload replay; no capacity excuse or silent feature removal. |

Cosmos fresh runtime now independently verifies exact frame count, dimensions
and differing requested FPS. The suspected25→24FPS output issue was disproven
by a real fresh test; no speculative repair was applied. LeRobot still requires
the final public action-aligned transfer test after runtime promotion.

## Checkpoint at approximately 23:31 UTC

- Helm168 deployed the OpenFold3 inline loader and exact preemption
  classification repair. All three original public complex requests completed
  on their first new attempt. Poor reference agreement remains explicit:
  whole-complex CA RMSD18.212/15.323/19.053Å and native contact recall
  0/0.0556/0. These are execution repairs, not accurate binding predictions.
- The ESMFold2 request formerly lost to preemption completed in106.623s on
  a new replay. Its original1331s failed operation remains retained. Replaying
  successfully does not itself demonstrate another live eviction/retry cycle;
  the original disruption evidence is separately covered by controller tests.
- CXR's repaired public response attribution was present on20/20 permissive
  JSON requests, with13 valid outputs and7 original formatting failures. A
  separate exact-label JSON-schema cohort passed20/20. Runtime attribution,
  output-format reliability and diagnostic accuracy are distinct measurements.
- The mixed MolMIM/Qwen108-call cohort completed80 verified and28 failed
  operations. All60 Qwen calls passed; MolMIM returned20 requested outcomes
  and28 structured finite-search exhaustion errors. An honest error improves
  failure semantics but does not fulfill a scientist's molecular-design request.
- Fresh v27 scientist05 completed a four-call genomics study and independently
  verified report in one turn. A matched v25/v26 comparison reduced workflow
  time121.775→63.680s while model time remained about11.6s. This is a narrow
  overhead comparison, not a platform-wide or whole-conversation speedup.
- Proteina ligand/AME repairs remain isolated. The real H100 Python-header and
  Triton JIT prerequisites now pass, and actual RF3 produced a structure and
  nonzero reward. All original variants and the protein-target regression must
  still finish before public promotion. Earlier candidate failures are retained.
- Cosmos's warmed replacement snapshot passed strict restoration on two
  physical H100s and the actual production Pod renderer. Cross-node CRIU/CUDA
  restore28.534+6.042s excludes164.594s image pull. Ordinary public snapshot
  admission is still unqualified; the bundle is not yet selected in production.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q46 | Public LeRobot operationb46eb725 generated both H100 videos but failed dataset packaging: source `next.done` was scalar while its declared feature shape was `(1,)`. | Lossless scalar-to-singleton normalization and dtype/shape preflight repaired in1a873c3b. Exact published coordinator image replay preserved all6144 non-video values across128 frames/two episodes/two cameras. Fresh ordinary public replay is pending Helm169; re-encoded unselected video is not byte-identical, and physical motion fidelity remains separate. |
| Q47 | App Logs returned HTTP200 with `data.state=unavailable`; the backend requested5000 lines for every ordinary page and exceeded the unchanged8s Loki timeout. | Exact smaller201-line query succeeds. Source574e9d72e fetches the requested page plus lookahead and expands only for a split timestamp boundary. Existing5000-line ceiling remains;16 focused log tests and96 integration tests pass. Public169 rollout/retest is in progress. |
| Q48 | v26 aging scientist completed four model calls but failed to deliver its report after two turns. Its hand-reconstructed AltumAge network omitted/misordered layers and reported an approximately262-year discrepancy. | Independent original-H5/scaler calculation agrees with17 actual Altum outputs within1.553e-5years;32 PhenoAge rows agree with declared rounded-v1 coefficients within3.02e-14years. A reusable typed analysis tool is being deployed in v28. Correct model outputs do not close natural workflow completion; the failed report attempts remain retained. |

Root-owned live rollout169 contains the repaired LeRobot coordinator execution
map and bounded App Logs reader; other serving owner settings and the four live
scientific snapshot registrations are preserved. No limits, quotas, tool budgets
or production customer concurrency settings were increased.

## Checkpoint at approximately 00:06 UTC, 19 September

- Helm169 deployed the repaired LeRobot coordinator. Ordinary public parent
  `a04f37db-1c2b-4e8a-b776-d60225078ed5` completed both video generations and
  returned a dataset reopened with pinned LeRobot0.6.1. All6,144 checked
  non-video values match over128 frames/two episodes/two cameras. Total
  latency406.806s includes156.20s fresh image pull; inference16.574/15.367s.
  This is artifact/action alignment evidence, not physical-motion validity.
- Helm170 deployed source1ad44fce0, image2172e19536a3, preserving all four
  existing scientific snapshot registrations. The registered new Cosmos
  snapshot remains unselected (`Never`) while ordinary edge-transfer runs.
  Cross-node isolated restore is not yet ordinary public snapshot acceptance.
- A new public ESMFold2 operation`cf771dd7-ac0f-42d9-bd09-8b6497270c01`
  completed in114.767s. Its CPU preparation and GPU folding attempts now carry
  the actual node/Pod IDs; the folding stage additionally carries its observed
  GPU UUID. Admin inventory agrees:1CPU node/0GPUs and1GPU node/1GPU.
  Older immutable receipts are not silently backfilled or rewritten.
- Independent Gemmi/NumPy recomputation confirms all four v26 complex-study
  coordinate metric sets within1.45e-7Å and exactly matches all contact counts.
  The generated narrative still gives an incorrect local-fit summary range;
  correct metrics do not establish a clean end-to-end report.
- Proteina's original five repaired variant/protein pipelines completed in
  isolation. Explicit100-step ligand/AME test settings produced malformed raw
  geometry. A matched ligand seed7 run at the upstream400-step baseline passes
  the limited CA-geometry check and reduces raw→refold RMSD55.67/56.12Å to
  1.666/0.811Å. The public API already requires an explicit diffusion_steps;
  there is no hidden100-step production default to repair. Other400-step
  variants and exact public deployment remain pending. No affinity claim.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q49 | Live log-page comparison exposed one skipped row per page despite bounded reads succeeding. | Loki's backward end is exclusive. Source1ad44fce0 includes the boundary by1ns before applying the duplicate offset; regression mocks now model the real exclusivity.170 live comparison:500 single-read rows equal the first500 of three200-row pages exactly; each page0.76–0.92s. No timeout/row ceiling increase. |
| Q50 | Scientific public result attempts omitted known node/GPU IDs even though existing lifecycle facts contained them. | Source1ad44fce0 projects existing operation/attempt/Pod-scoped correlations at terminal publication. Five focused provenance cases cover missing evidence, CPU, GPU, retries and isolation; new ordinary ESMFold2 result and admin counts verify the live repair. Parent serving-runtime defaults must not be read as aggregate multistage GPU usage. |
| Q51 | Two already-deleting GPU-observer Pods on provider-confirmed STOPPED nodes prevented normal DaemonSet rollout progress. | Exact Pod/node/provider snapshots were retained, then only those two obsolete observer records were removed.170 subsequently reached13/13 updated and Ready within the unchanged10-minute deadline. This required operator recovery and is not an automatic-preemption recovery pass. Nodes and customer jobs were not deleted; durable provider-aware cleanup remains to be addressed. |
| Q52 | v29 bounded30s execution observation raced the existing30000ms MCP transport deadline, producing two recoverable tool timeouts. | Durable jobs continued and were recovered without duplicate inference. v30 reserves5s transport margin, reports effective25s observation, and tests a real26s job across pending/terminal reconnect. Original timeout evidence remains; no transport, job, tool-round or output limit increase. Fresh live retest pending. |
| Q53 | Typed deterministic per-run chemistry/aging metrics are correct, but handwritten cross-run narrative still invents denominators, extrema or causal explanations. | v29 deterministic per-run docking reports fix the earlier extrema mistakes, but its final report says three of four top-ranked3PTB results despite only two such runs. Generic multi-run aggregation is being implemented. v28 aging completed after a continuation; historical reconstruction cause wording remains unsupported. No natural-workflow pass from numeric artifacts alone. |

Current source coverage explicitly preserves32Apps and13 scoped evidence rows,
including remaining BoltzGen protocol/RFdiffusion motif gaps, Proteina public
variant failures and MolMIM finite-search exhaustion. Source coverage refresh is
not a requalification of every release. Existing MSA/refold campaigns and other
customer work continue; the review deadline remains06:04UTC.

## Checkpoint at approximately 00:44 UTC, 19 September

- Fresh scientist07 v30 completed the four-call aging study in one natural
  chat turn,00:10:22.873–00:12:31.704UTC. Downloaded input/result byte hashes,
  every exported CSV row and reference recomputation agree:32 PhenoAge rows
  within3.02e-14years and17 AltumAge rows within1.553e-5years. The actual report
  correctly separates modalities, declares the one overlapping sample and
  avoids a clinical-validity claim. This narrow workflow passes; no general
  agent or all-scientist qualification follows from it.
- Fresh scientist06 v31 completed its five intended model operations in
  99.387s from first admission to last completion with no MCP observation
  timeout. All16 pose metrics and16 molecular-property rows were independently
  verified. It needed one continuation and wrote a malformed summary table.
  A subsequent v32 read-only recovery still rewrote tables/narrative incorrectly.
  The new deterministic report assembler is separately verified live against
  source bytes; natural adoption and a matched planner-model comparison remain
  in progress. These are not clean end-to-end passes.
- Strict ordinary Cosmos snapshot requests passed on new physical H100s:
  original accepted-to-complete64.303s (ready48.325s,inference15.939s), held-out
  shape43.162s, and recorded LeRobot parent174.54s. Restoration actually used
  the exact warmed snapshot with fresh-load fallback forbidden. Original
  CRIU29.390s+CUDA5.314s is a restore-phase measurement, not total cold start.
  The dataset preserved all6,144 non-video values,128 frames,two episodes and
  two cameras; motion/appearance correctness remains a separate unmet gate.
- Nine dedicated native Cosmos cases decode successfully across T2I,T2V,I2V,
  V2V,two geometries/frame rates and generated audio. These output-contract
  checks do not establish action-aligned robotics augmentation.
- Source3466eb493 contains the repaired Proteina runtime selection, explicit
  transfer size and complete LeRobot schema/example. Imageaf687f0860cc was
  deployed to healthy serving replicas during Helm171, but the observer
  DaemonSet stalled on another already-deleting Pod on a STOPPED node.
  The unchanged10-minute deadline expired.172 automatic rollback is in progress.
  The node returned and removed its obsolete observer naturally before any
  requested force-removal approval/action. Do not describe171 as settled.
- BoltzGen's new small-molecule protocol completed all eight public stages in
  1,210.64s and retained exact ligand heavy-atom identity/basic structure checks.
  A peptide case completed764.68s; its first independent verdict was wrong
  because the fixture expected unresolved terminal residues that pinned
  upstream explicitly removes. A separately labelled, source-backed evaluation
  correction preserves the original manifest/result/failed verdict, without
  a repeated model call. Neither case establishes binding efficacy.

| ID | Additional observation | Classification and current action |
| --- | --- | --- |
| Q54 | Identical DiffDock request bytes/seed19 gave substantially different poses on the same live Pod and GPU. | Request seeds reached Torch/NumPy but not RDKit ETKDG preprocessing. Candidate6302f8eb9 explicitly propagates the seed, retaining retry count and weights. Isolated24-call/12-pair H100 test makes all preprocessing repeats byte-identical;6/12 GPU pairs still exceed the predeclared0.01Å/0.001confidence numerical thresholds (largest coordinate difference0.0352Å). Results preserved; c49c8567a selects deterministic CUDA kernels and is awaiting matched GPU replay. Live runtime unchanged; no old snapshot qualification inherited. |
| Q55 | LeRobot edge-transfer coordinator omitted exact size and silently resized returned448x256 video to640x480. Dataset readback alone concealed the lower-resolution model result. | Raw child artifacts and exact old coordinator prove the defect. A new coordinator preserves size and rejects unrequested dimension/FPS/frame-count changes without resizing.48 focused and29 reader tests pass; exact-image replay/public successor qualification pending. Historical format-only passes are not silently relabelled full acceptance. |
| Q56 | Default V2V keeps only first-frame conditioning; generated robot motion can diverge although actions/timestamps remain numerically unchanged. | Real decoded-frame inspection and pinned upstream semantics confirm this is not full-clip action-aligned augmentation. Full-video transfer preserves motion better in exploratory flow measurements, but old geometry distortion and altered objects prevent policy-readiness claims. Truthful tool/provenance descriptions and a bounded exact-size transfer quality comparison are underway. |

No quotas, customer concurrency, transport deadlines, reasoning/output budgets
or rollout limits were raised. The first completed isolated DiffDock Pod and
ConfigMap were removed normally after all logs, outputs and hashes were saved;
the test is reproducible from the retained immutable image and manifest.

### 19 September, 01:50 UTC — customer-shaped checks continue

- Helm174 is settled with the protocol-aware BoltzGen repair. Exact original
  antibody and redesign public replays remain in flight; isolated stage success
  is not yet whole-workflow acceptance.
- Q54: final DiffDock image `9766b4fb2a22787874bd8d90306980a4cb1ff9808941f0f1ae429d8b8f7cc948`
  completed 48 isolated calls in two fresh H100 processes on different GPUs.
  All same-input coordinates and confidence values match exactly across these
  processes; the predeclared tolerances were not relaxed. Root causes included
  unseeded conformer generation, nondeterministic GPU kernels, and an unseeded
  import-time torsion normalization table. Weights and inference budgets remain
  unchanged. Generated SDFs now explicitly identify 3D coordinates. Public
  promotion/replay and new-image cold-start evidence remain pending; no old
  snapshot evidence transfers. Original failures and intermediate candidates
  remain retained.
- Q55: exact-size ordinary LeRobot replay on173 passed independent readback of
  128 frames, two episodes/two cameras and all6,144 non-video values. Actual raw
  generated clips are640×480, not resized448×256 outputs. Q56 remains separate:
  appearance changes and motion proxies do not establish action-aligned robotic
  policy training suitability.
- Scientist07's unchanged aging study completed in one natural v34 turn,
  150.054s, with independent checks of32PhenoAge and17AltumAge rows. Downloaded
  report is13,279 bytes, SHA256
  `96dc52b8738c21cdde7b2737a7d5579639eb1affae75e016b6624a5bf2d016ee`.
  Inline-code workspace URLs still required manual navigation; the general
  renderer fix is included in candidatev36, not yet browser-qualified.

| ID | Observation | Classification and action |
| --- | --- | --- |
| Q57 | Natural scientist02 used invented Protenix inner-manifest roles/MIME. The model schema omitted the exact roles, the client discarded top-level manifest contracts, and the server misreported the invalid request as `scientific_profile_unavailable`. | Original rejected request255c7295… retained; no operation was admitted. Backend80ffcc4d6 publishes adapter-derived contracts for all11 scientific Apps and validates roles before compilation;95 focused tests pass. Client2d3df06 consumes the real top-level shape and rejects mismatches before uploads, with51 tests and15 actual descriptor variants checked. Same Protenix parameters form the expected two-stage plan with correct metadata offline. Combined deployment and unchanged-request natural recovery remain pending. |
| Q58 | A successful Cosmos request during a multi-replica overlap returned unknown Pod/node/GPU attribution; zero GPU count represented missing evidence, not zero consumption. | The singleton fallback cannot select the actual serving Pod when two are ready. Candidate5df175740 adds exact response identity at the Cosmos adapter with a verified same-Pod adapter→GPU mapping;104 focused tests pass. New template is prepared; actual overlapping multi-Pod inference and billing-attribution acceptance remain pending. Historical missing values are not guessed. |

Clinical candidate3cf02bb rejects unsupported normalized medication names using
literal source anchors. In the retained original-transcript replay the extractor
again invented the normalized brand; the deterministic gate withheld it and kept
the unclear source phrase for review. This fixes the demonstrated lexical
contract, not clinical correctness, completeness or fitness for doctors.

The new combined workbenchv36 is built, not yet deployed. No overall
customer-ready verdict follows from these narrower fixes.

### 19 September, 02:50 UTC — public repeatability and real-client regressions

- Releases175,176 and177 settled;177 runs control-plane source55fa9d930.
  Model profiles and scheduling limits were preserved. The earlier01:50
  deployment state above is historical, not the current status.
- Q54: two public12-case cohorts on the seeded DiffDock runtime returned24
  verified outputs. Across public repeats, maximum coordinate difference is
  0.000400000000013Å and confidence difference0.0002570152283, within the
  unchanged0.01Å/0.001 thresholds. Scientific quality remains6/12 distinct
  complex-seeds below2Å top-ranked RMSD; the approximately705.87Å outlier remains.
  All24 public operations lack runtime identity; this is Q63, not evidence of
  zero GPU use. Isolated-process qualification and public operation counts
  remain separate.
- Q57: all11 public scientific descriptors now expose exact input roles.
  The retained malformed Protenix request is rejected before admission with
  actionable invalid-argument detail. Natural scientist02 recovery onv36 did
  not reach a model tool because the planner provider returned404 (Q62).
- Q58: the new Cosmos response identity is proven with two simultaneously
  Ready Pods, both using CUDA/CRIU restore. Natural LeRobot child operations
  3a1e3e9e… andac59ce1d… identify different actual serving Pod UIDs and GPUs.
  Historical unknown identity stays unknown. This closes the narrow
  multi-replica attribution defect, not Q56 robotic action alignment.
- Natural scientist01 completed its structure study and downloaded the report
  onv36; two rejected overlong wait arguments and automatic recovery remain
  in the chat. Scientist08 completed four ASR calls but produced an unsupported
  medication name in the report. Scientist10's returned dataset preserves128
  rows and6,144 non-video values, but prefix-conditioned generation does not
  fulfill the original full-trajectory intent, and unselected video changes
  through re-encoding (Q64). Successful artifacts do not erase these failures.
- A new13-case held-out batch across BindCraft, Mosaic and RFdiffusion uses
  the frozen dataset manifest, new seeds/lengths, four existing identities and
  unchanged one-operation-per-key limits. Existing196-case design-to-refold
  work continues separately. None is counted complete while still pending.

| ID | Observation | Classification and action |
| --- | --- | --- |
| Q59 | Real admin scientific-run detail returned503 under the existing2s database budget. The query computed latest lifecycle rollups globally before filtering the requested subjects. | Sourcec48a567 uses indexed per-subject latest-row lookup, with unchanged semantics and timeout. Deployed177:24/24 real reads returned200, median0.415s/max1.284s. The original503 and retry remain retained; this is sequential bounded acceptance, not arbitrary-load capacity proof. |
| Q60 | A GPU observer was OOMKilled at its unchanged128Mi limit because its entrypoint imported the full gateway/controller stack. | Source55fa9d930 isolates dependency-light startup. Deployed177:15/15 observers Ready with0 restarts,32–35Mi observed; new BindCraft/Mosaic GPU Pods receive real allocation annotations. The same-node canary had0 restarts and was normally removed after evidence retention. Long-soak and stopped-node cleanup are separate. |
| Q61 | Clinicalv5 allowed invented “Dioralyte” from literal “dire light” because both model-produced medication flags werefalse and anchors empty. | Exact-source-phrase extraction and deterministic span validation replace reliance on flags. Frozen5598646 additionally displays complete cited context beside every selected phrase, preserving dose/return conditions. Retained source replay has22 selected facts/32 phrases but only16/20 segments covered. Missing details and all negative candidates remain documented; not clinical readiness/completeness. |
| Q62 | Token Factory stopped listing/serving the configuredGLM5.3 planner midcampaign. A direct request returned404 model_not_found; current client startup catalog remained stale. | Provider model availability, not authentication or proven shared-cache corruption. Original02/05/10 failed chats are retained. Explicitly selected DeepSeek-V4-Pro-0813 passes bounded tool-capability checks. Newv37 previews use that declared planner with unchanged context/output/tool budgets; no silent fallback or readiness claim before natural replay. |
| Q63 | Every request in the two public DiffDock repeatability cohorts returned unknown Pod/node/GPU identity during multi-replica serving. | Generic HTTP wrapper omitted the response-identity protocol. Source7e8c0f0f8 adds verified same-GPU-container identity; wrapper-only successor0c717984… preserves model code/weights. Real-GPU regression, promotion and multi-replica public attribution remain pending. |
| Q64 | Unselected LeRobot wrist-camera pixels change because the whole dataset is decoded and re-encoded; the original task requested unchanged camera bytes. | Mean pixel differences approximately1.3 show that reader tolerance is insufficient for this requirement. Preserve the original passing structural check and separate failed exact-preservation verdict. A pinned-layout-aware media preservation repair is being investigated. |

Evidence is under the protected campaign directory, with portable summaries
and exact source references in linked task cards. No budget, quota, concurrency,
context, output, tool-round or rollout-timeout limits were raised.

## 19 September, 05:44 UTC — later evidence and remaining failures

This additive checkpoint supersedes the earlier pending states only within the
explicit scopes below. It does not change historical receipts or claim that ten
clean natural journeys passed on one final release. The full twelve-hour report
is being assembled at
`demos/evidence/20260919-twelve-hour-checkpoint/README.md`.

- **Backend 182 is deployed**, source `8e747def5`, index `f3a3d6c2…`.
  Frozen regression suite: 2,760 passed, five skipped, 130 deselected. Apps
  list/detail usage queries no longer perform unnecessary full fan-out; fixed
  historical counts match. Eight external API reads, six per-Pod reads and 32
  real-browser admin GETs returned 200. No database/HTTP timeout was raised.
- The snapshot status projection first exposed a strict-SSA 422 on Cosmos and
  Qwen: an empty evidence-selector object was interpreted as removing the last
  owned key, yielding invalid null. Release 180 failed and rolled back to 181.
  The bounded omission of optional empty maps repairs that actual API contract;
  release 182 succeeded. All 21 model specs and 33 generated Pod templates
  remained unchanged. Configured snapshot selection is not measured fast-start
  qualification: unmeasured effective levels remain unavailable.
- **Q63, narrow DiffDock attribution/repeatability:** release-179 paired public
  cohorts have 24/24 actual replica/node/GPU/image/revision joins. New paired
  numerical comparisons pass unchanged tolerances; an older-reference mismatch
  and poor experimental poses remain. See the separate published DiffDock note.
- **Q64, untouched LeRobot media:** both scripted release-179 and natural v42
  successor evidence preserve exact unselected wrist media, 128 rows and all
  6,144 non-video values. The natural successor delivered four verified browser
  downloads after two ordinary continuations. Q56 physical/action alignment is
  still unqualified; metadata preservation does not establish training utility.
- **Q65, complete-result recovery:** v42 naturally adopted lossless recovery
  and delivered nonempty native/dataset provenance. Its first NPZ seek failure,
  automatic recovery, 429 overlap and report-method errors remain visible.
  Admission/activation time was incorrectly called pure cold start, and RGB
  mean was called luminance. Correct files do not fix those statements.
- **Seekable scientific exports:** v43 adds shared explicit local staging and
  verified closed-file publication, without pretending a bucket is POSIX.
  NPZ/HDF5/ZIP/closed SQLite passed real mount plus independent S3 reopening.
  The natural v43 task also produced all four formats with all 6,144 values
  exact and seven byte-verified browser downloads. It needed one continuation;
  five preparation execution errors and a wrong first ZIP boolean comparison
  self-recovered. The initial incorrect 5,120 vector-value count was not
  explicitly corrected; a later 5,504 figure counts floats only. These report
  defects remain, rather than being hidden by the output-equality pass.
- **Clickable downloads remain under repair:** v43 prints six correct workspace
  URLs in a fenced code block. They work by navigation but are not links.
  Narrow renderer candidate `6976499` preserves the original code block and
  adds authenticated workspace links for exact recognized URL-only content.
  Eleven tests and an immutable v44 build pass; live preview creation and
  real-browser acceptance are pending at this checkpoint. No natural study is
  relabelled as a v44 pass.
- **Clinical v42:** two full-source drafts and one expected typed no-report
  outcome, 24 verified browser downloads, five reproducible measurement bundles.
  Four earlier ASRs were reused; there are zero new ASR calls in this successor.
  English still required two continuations. Agent-written analysis used wrong
  fields to report zero accepted facts instead of 32, falsely described a fact
  as omitted, and gave an unsupported WER explanation. German omitted a possible
  source-selection analysis by confusing it with missing human-reference WER.
  Exact literal spans and deterministic metrics are not clinical readiness.
- **Design completion:** all 13 held-out BindCraft/Mosaic/RFdiffusion operations
  are now terminal with checked artifacts, including the original long BindCraft
  search. Its 8,416-second client wait includes approximately 18 minutes of
  placement queueing. The separate downstream refold study completed 220 cases;
  poor self-consistency is retained, not counted as experimental success.
- **Preemptible recovery:** the deployed classifier/controller passes a replay
  of the retained exact taint-evicted Pod status and unchanged bounded retry
  tests. Synthetic Job/Kueue shells are labelled as such. The successful new
  same-payload request is not automatic recovery of the original failure, and
  a new live capacity-loss recovery cycle is still unqualified.

The final read-only 05:38 capture has healthy backend gateways/controllers and
15/15 Ready GPU observers, with one historical observer restart retained.
Twenty-nine schedulable GPU units minus 19 Pod reservations leaves ten resource
units, not ten universally placeable GPUs or a utilization measurement. Older
unhealthy infrastructure/workshop resources remain explicitly listed in the
live-state note; no cleanup or unrelated mutation was performed.

Aggregation now explicitly separates uploaded artifacts from actual inference
children, joins exact retained terminal status captures without inventing
admissions, and treats persistence-history directories as directories rather
than corrupt JSON files. Thirty-four aggregation/latency/workshop tests pass.
Those are measurement repairs, not additional model calls or product passes.
