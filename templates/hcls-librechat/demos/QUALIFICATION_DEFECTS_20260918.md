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
