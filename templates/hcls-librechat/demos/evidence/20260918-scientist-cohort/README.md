# Ten-scientist live cohort — 18 September 2026

This is a customer-shaped qualification of the Scientific AI Workbench, not a
claim that ten published papers were reproduced. Every row used public or
synthetic data and a live, caller-authorized platform App. A run is called a
reproduction only when its input preparation, evaluation protocol and reported
metric match the cited work. Most rows are deliberately classified as bounded
inference or workflow acceptance because that distinction is important to a
scientist.

The exact protected requests, responses, immutable artifact manifests and file
hashes are retained outside Git in the release evidence directory. This file
contains no credentials or customer data.

## Release under test

- Workbench source: through commit `029d8f3` on
  `agent/scientific-ai-workbench-v2-20260918`.
- R3 exercised the complete clinical and MindEval workers. R4 corrected the
  authenticated Workspace download path. R5 introduced artifact-backed JSON
  result resolution; R6 aligned it with the production direct-result envelope.
  R8 pinned the existing agent to a chat/tool-call-qualified model, R9 preserved
  exact returned precision, and R10 added result-level evidence boundaries.
- The live catalog exposed 32 authorized Apps and the MCP process loaded 61
  typed scientific tools.
- All native and batch submissions used stable idempotency keys. Artifact-backed
  results were downloaded and checked against advertised SHA-256 and byte size.
- R11 browser acceptance used the existing Scientific AI agent and the real
  OpenFold operation. It returned the exact confidence, pTM and inference-time
  values in 23.2 seconds without new compute or a provider error, and kept
  absent fields as bounded observations rather than unsupported-capability
  claims.

## Cohort

| Scientist | Public reference and data | Live result | Reproduction level | Gap exposed |
|---|---|---|---|---|
| 1. Structural bioinformatician | [OpenFold paper](https://doi.org/10.1038/s41592-024-02272-z); PDB 1UBQ ubiquitin sequence | `openfold2` operation `9c8dd226-b98b-4748-82ca-550c44ce194a` succeeded. Mean confidence 72.486, pTM 0.5285, inference 1.251 s; upstream-source runtime, parameter set 1. | Bounded single-sequence inference | The App does not yet assemble the paper's MSA/template pipeline or calculate RMSD/TM-score against the experimental structure. A scientist needs a PDB reference loader and evaluator, not only a PDB result. |
| 2. Structure-model researcher | [Boltz repository and paper](https://github.com/jwohlwend/boltz); the same 1UBQ sequence with explicit MSA | `boltz2` operation `7b94c72b-ee52-4925-8123-375e1f82f491` succeeded. Confidence 0.9273 and pTM 0.9104; one structure. | Bounded inference | There is no side-by-side preparation/evaluation recipe that makes Boltz and OpenFold inputs comparable, and no automatic reference-structure metric or 3D comparison report. |
| 3. Computational chemist | [DiffDock paper](https://doi.org/10.48550/arXiv.2210.01776); platform's public 1UBQ plus aspirin fixture | `diffdock` operation `f2ec367e-0916-4bc1-8c0a-52ea42438cbd` produced one pose with confidence -2.9537 and a trajectory. | Transport and inference acceptance | This is not the paper's PDBBind benchmark. The Workbench needs receptor/ligand preparation, PDBBind-style dataset import, pose RMSD, top-N success and visual comparison. A model confidence is not docking accuracy. |
| 4. Genomicist | [Evo 2 paper](https://doi.org/10.1038/s41586-026-10176-5) and [official BRCA1 notebook](https://github.com/ArcInstitute/evo2/blob/main/notebooks/brca1/brca1_zero_shot_vep.ipynb) | `evo2-40b` operation `2fc741ce-348b-4ee4-9945-4393349323bb` generated 32 bases from `ACTGACTGACTGACTG` in 17.991 s; first token took 16.539 s. | Generation acceptance only | The deployed contract lacks sequence scoring/log-likelihood and embedding operations, so it cannot reproduce the paper's zero-shot BRCA1 variant-effect analysis. This is the clearest missing scientific API. |
| 5. Clinical-aging researcher | [PhenoAge paper](https://doi.org/10.18632/aging.101414); published-formula reference biomarkers | `phenoage` operation `097d2f56-bbf7-4002-991b-1c9ea751bc39` returned 41.9079 years in 0.000049 s of formula execution. | Formula conformance case | A single reference vector is not cohort validation. Scientists need column templates, units, missing-value checks, batch confidence intervals and published-cohort comparison. GPU caching is correctly not applicable. |
| 6. Epigenomicist | [AltumAge paper](https://doi.org/10.1038/s41514-022-00085-y); exact 20,318-CpG synthetic reference vector | `altumage` operation `30f74eb0-bead-4b0c-9d06-e0031be1eca5` returned 38.2212 years, with all 20,318 features and official robust scaling, in 0.0101 s model execution. | Exact-contract acceptance | Real users need array/platform mapping, methylation QC and cohort import. Snapshot status is `not-qualified`; fast execution on a ready worker is not evidence of scale-from-zero performance. |
| 7. Protein-design scientist | [RFdiffusion paper](https://doi.org/10.1038/s41586-023-06415-8); fixed 76-residue unconditional design | Scientific operation `096438ea-9152-4f6c-a2ee-dd8c11863889` passed semantic validation and published a hash-verified JSON result plus PDB. One H100 generated one 76-residue backbone; model-ready 38.335 s, upstream 59.350 s, 59.891 s worker total. | Bounded design inference | End-to-end operation time was 208.9 s because the batch spent substantial time before GPU execution. GPU snapshot was not used. The useful workflow still needs ProteinMPNN, refolding/structure validation, ranking and explicit queue/artifact-load timings in the UI. |
| 8. Medical-NLP scientist | [PriMock57 paper](https://aclanthology.org/2022.acl-short.65/) and public consultation 01 audio/reference | R3 job `07bf8dcef1f71fdfebb6a58a77adc0ac` processed the full 457.9-second English consultation into transcript, evidence-linked report, follow-up questions, review queue and JSON. Approximate normalized WER was 17.83% (253 edits / 1,419 reference words); all five reference-note highlights appeared in the draft. | Complete workflow acceptance, not clinical validation | The report is useful for review but the transcript includes material recognition errors. We need medical-term error rate, speaker/turn evaluation, a clinician-reviewed report score and a visible uncertainty/edit workflow before doctor-facing use. |
| 9. Robotics scientist | [NVIDIA Cosmos Predict 2.5](https://github.com/nvidia-cosmos/cosmos-predict2.5) and a bounded LeRobot v3 public-data fixture | Scientific operation `5fe677bc-7586-4fbf-82c0-5a651c81fad9` preserved actions, processed one selected episode/camera and published a 2.54 MB LeRobot bundle. The LeRobot 0.6.1 validator passed 2 episodes, 64 frames and 128 decoded video frames. | Data-contract and augmentation-path acceptance | The validator proves schema, readability and preserved action transport; it does not prove physical or visual fidelity. The observed stage was CPU-scheduled, so this evidence alone must not be marketed as GPU Cosmos inference. We need pixel/temporal metrics, a dataset diff viewer and an explicit runtime/model receipt. |
| 10. Mental-health evaluation researcher | [MindEval repository](https://github.com/SWORDHealth/mind-eval) and bundled public profile | R3 run `fc67e2c7-6b5e-49ec-9eb5-29c4a5d2338f` completed a two-round patient/clinician conversation and Gemma judge. Five-turn transcript, 20,093 judge tokens, overall score 3.675/6. | Bounded orchestration acceptance | The judge call retried three transport errors and took 557.632 s. A two-round, one-profile run does not reproduce MindEval. Scientists need fixed manifests for patient/judge/config, resumable batch progress, paired confidence intervals and a cost/time forecast before starting a full run. |

## Cross-cutting findings

1. **The platform completes diverse work, but the user key admitted only one
   concurrent model operation.** A parallel cohort received structured,
   retryable `admission_limit_reached` responses with `durable_admission=false`.
   The backend behaved safely and exact idempotent retries succeeded, but the
   Workbench needs a client-side submission queue, position/status and automatic
   retry. Scientists should not have to understand admission semantics.
2. **Inference is not the same as paper reproduction.** Structure, docking,
   genomics and robotics Apps generally expose the model primitive but not the
   paper's data preparation and metric suite. Reproducible study templates and
   evaluators are the largest functional gap.
3. **Performance terminology needs to be stricter.** Native Apps reported
   sub-second `cold_start_seconds` because their workers were already ready.
   That is activation latency for this run, not a demonstrated scale-from-zero
   or GPU-snapshot restore. The UI must separate queue, node provisioning, image,
   weights/snapshot, model-ready, inference and artifact-publication time.
4. **Artifacts are trustworthy but not yet pleasant.** The batch paths produced
   immutable manifests and verified hashes. The Workbench upload was sound; the
   cohort caught that its original plain download link could not authenticate.
   R4 routes downloads through the authenticated client and has a byte-for-byte
   browser regression test.
5. **Runs should appear automatically.** Today an existing operation can be
   reattached safely, but the ten operations had to be added to the Workbench
   history explicitly. Caller-scoped server history should populate Runs
   automatically, including stage timings and evaluation artifacts.
6. **The chat agent must inspect output, not infer it from input schema.** The
   first R4 conversation saw only an operation-artifact pointer and incorrectly
   treated missing inline fields as missing model output. R5 makes the
   Workbench result tool fetch bounded JSON with the caller key, verify byte
   count and SHA-256, then compact arrays/coordinates while retaining scalar
   metrics. The environment-execution tools are also explicitly attached to
   the seeded agent rather than merely configuring their MCP server. R6 also
   exercises the production API's direct result envelope rather than relying
   on the older wrapped fixture shape.
7. **Catalog presence is not chat readiness.** The previously seeded
   `zai-org/GLM-5.3-Flash` remained selectable but failed after tool execution
   with a provider-unavailable response. The default is now
   `Qwen/Qwen3-235B-A22B-Instruct-2507`, qualified with a real function-tool
   call and the exact verified OpenFold result before deployment. The 30B model
   remains selectable but is not the default scientific agent because it
   contradicted explicit evidence boundaries in the customer-shaped test.
8. **A verified value can still be over-interpreted by an agent.** R9 copied the
   requested confidence, pTM and inference values exactly, but initially turned
   observations about one result into App-wide limitations. R10 therefore
   emits machine-readable evidence observations and interpretation boundaries:
   absent fields are not unsupported capabilities, the outer JSON artifact
   size is not a nested PDB size, and confidence is not validation.

## Product assessment

The release is useful as an expert-operated research workbench and all ten
customer-shaped paths reached a terminal result. It is not yet a push-button
paper-reproduction service. The main path from question → authorized App →
durable result → artifact works; the missing layer is domain evaluation,
dataset preparation and queue/performance transparency. Those are the next
features to prioritize before describing the platform as self-service for
arbitrary scientists.
