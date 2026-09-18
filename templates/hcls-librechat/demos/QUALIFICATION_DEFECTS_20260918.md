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
