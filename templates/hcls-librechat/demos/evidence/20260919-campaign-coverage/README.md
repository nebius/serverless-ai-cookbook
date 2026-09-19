# All-App coverage overlay — 19 September 2026

Evidence cutoff: **2026-09-19T04:37:11.014231+00:00**. This is a coverage index, **not a
platform-readiness verdict**, scientific validation, or the final 06:04 report.
No new model calls, deployment, resource changes or quota changes were performed
for this task.

The [machine-readable overlay](../../../scripts/qualification/cases/coverage-overlay-20260919T0437Z.json)
pins 50 reviewed evidence files by full SHA256 and preserves exact protected
copies. It records four independent dimensions for every model: service/API,
natural LibreChat delivery, scientific correctness and GPU snapshot evidence.
The [ten-persona customer-journey assessment](../20260919-persona-customer-experience/README.md)
is a separate 04:32 checkpoint; its client experience must not be inferred from
API-scale cohorts.

## Inventory and identity boundary

The 03:59 admin capture contains **35 App instances across 33 model identities**:
the 32 H100 campaign models, disabled/unavailable GLM-5.2-FP8, and two disabled
clones of Qwen3-8B and Protenix. The overlay retains all 35 distinct App IDs/public
names and their captured states. Canonical-model tests do not qualify disabled
clones. GLM was intentionally excluded from this H100 campaign; historical
B300 evidence is not transferred.

Historical 32-App matrix SHA256:
`349d162c08885cbe7de9988fcb408237b01a2850db4504973c7661861d9001da`.

Captured 35-App inventory SHA256:
`504f2f7ebf5c94b856c1d24b58b93f5d6aa659dc112510a374eb8c458f32759e`.

Release 179 ConfigMap capture SHA256:
`873cba6673ad29dd9ddc235f939162a5b8842b9bd14bb266ef93d571fea4a9a3`.

The selected runtime image/revision or scientific execution identity is projected
for 29 models where the captured deployment maps provide it. The remaining
canonical routes are explicitly not projected by this helper; that is not an
unavailability verdict. Configuration selection is **not execution attestation**:
old operations retain their actual release, image, client and input identities.
No historical results are relabelled as release 179 acceptance.

## What changed since the historical matrix

- **Proteina-Complexa:** protein, ligand and AME pipelines now have public
  terminal evidence. Raw generation and self-refolded predictions remain
  separate. The original release 173 study passed basic geometry for 6/8 raw versus 8/8
  refolded outputs; a distinct 400-step sensitivity case does not erase the
  original 100-step failures. Three four-sample PDL1 requests also completed.
- **BoltzGen:** all six named protocols now have bounded terminal evidence,
  across different releases. Peptide/nanobody terminal-trimming and antibody
  full-polymer/missing-coordinate reassessments are separately retained,
  source-backed evaluator corrections—not extra inference or rewritten passes.
  The earlier protocols were not all rerun on release 174.
- **RFdiffusion:** the motif scaffold is no longer merely prepared: exact motif
  sequence and 0.11294 Å mapped C-alpha RMSD passed the frozen fixture.
  The 196 completed downstream refolds cover 192 ProteinMPNN designs plus four
  Mosaic designs; further RFdiffusion followups still running are not counted
  complete by this overlay.
- **OpenFold3/OpenBind:** the historical matrix placed the inline-loader repair
  under the wrong App. Actual operation receipts identify
  `openfold3-openbind`, a separate scientific-batch path from native
  `openfold3`. The correction is explicit without modifying the old matrix.
- **DiffDock:** release 179 has verified public replica attribution and paired
  numerical agreement across two actual H100 workers. One older-reference
  discrepancy remains; half the tested top-ranked poses miss the 2 Å criterion,
  and the approximately 705.87 Å outlier remains. API repair is not broad
  docking accuracy.
- **Cosmos/LeRobot:** the release 179 scripted recorded-data replay verifies
  exact untouched wrist media, actions/state/timing and actual selected-camera
  dimensions, with strict snapshot witnesses. It is not natural LibreChat
  completion and does not prove physical action-label/policy-training validity.
  Selected object/contact details can still change.

## Every model, without conflating evidence layers

“Bounded public results” means terminal evidence for the reviewed inputs and
modes—not every advertised path or an all-green failure denominator. The JSON
contains per-mode scope, exact references, scientific limitations, old gaps and
separate snapshot statements.

| Model | Service/API evidence | Natural LibreChat evidence |
| --- | --- | --- |
| alphafold3 | Bounded public results | Not established |
| altumage | Bounded public results | Bounded earlier-client delivery |
| bindcraft | Completed subset; pending work | Not established |
| boltz2 | Bounded public results | Delivered after explicit correction |
| boltzgen | Bounded public results | Earlier-client delivery only |
| cosmos3-lerobot-augmentation | Bounded public results | Natural delivery unresolved |
| cosmos3-nano | Bounded public results | Natural delivery unresolved |
| diar-streaming-sortformer-4spk-v2-1 | Bounded public results | Not established |
| diffdock | Bounded public results | Delivered after continuation |
| esmfold2 | Bounded public results | Not established |
| esmfold2-fast | Bounded public results | Not established |
| evo2-40b | Bounded public results | Bounded earlier-client delivery |
| genmol | Bounded public results | Delivered after continuation |
| glm-5-2-fp8 | Disabled; excluded | Out of scope |
| magpie-tts-multilingual-357m | Bounded public results | Not established |
| molmim | Mixed; finite-search failures | Not established |
| mosaic | Bounded public results | Not established |
| msa-search-pdb70 | Bounded public results | Not established |
| nemotron-speech-en-0-6b | Bounded public results | Draft delivered; clinical gaps |
| nemotron-speech-multilingual-0-6b | Bounded public results | Draft delivered; clinical gaps |
| nv-reason-cxr-3b | Bounded public results | Not established |
| nv-segment-ct | Bounded public results | Not established |
| openfold2 | Bounded public results | Delivered with recovery |
| openfold3 | Bounded public results | Not established |
| openfold3-openbind | Bounded public results | Not established |
| parakeet-realtime-eou-120m-v1 | Bounded public results | Draft delivered; clinical gaps |
| phenoage | Bounded public results | Bounded earlier-client delivery |
| proteina-complexa | Bounded public results | Earlier-client delivery only |
| proteinmpnn | Bounded public results | Delivered after correction |
| protenix-v2 | Bounded public results | Delivered after explicit correction |
| qwen3-8b | Bounded public results | Not established |
| rfdiffusion | Bounded public results | Delivered after correction |
| sdxl | Bounded public results | Not established |

The clones are preserved under their underlying model rows, not dropped or
counted as additional qualified models. Native Qwen3-8B is also distinct from
the separate Token Factory planner/patient/judge deployments used in MindEval.

## Scientific and workflow gaps still matter

- **MolMIM:** repaired real CMA-ES still exhausted 28/48 finite searches at the
  unchanged settings. Those failed outcomes are not labelled service success
  because other cases returned molecules.
- **Protein/complex prediction:** confidence and structural completeness do not
  imply reference agreement. Poor no-MSA complexes and low contact recovery
  remain explicit; MSA-assisted monomer evidence does not qualify paired
  complex MSAs, every ligand mode or experimental binding.
- **Design:** valid sequence, geometry, motif preservation and computational
  self-refolding are not affinity, catalysis, antibody developability or
  experimental stability. Missing-coordinate metadata remains visible.
- **Aging:** numerical agreement with original H5/formula references is shown;
  held-out clinical generalization and mortality calibration are not.
- **Clinical speech/reporting:** reference WER/DER, source-faithful excerpts,
  natural draft delivery and medical completeness are different checks.
  Original hallucinated medication, omitted details, reporting-method
  inconsistencies and incomplete negative-input UX remain documented.
  No model is declared suitable for clinical use by this overlay.
- **Robotics:** byte-exact unchanged channels and valid generated MP4s do not
  establish physically aligned robot actions. V2V continuation is not full
  recorded-trajectory augmentation; even whole-clip transfer can alter objects.
- **Client:** earlier-version successful reports, ordinary continuation,
  explicit methodological correction and scripted helper recovery are labelled
  separately. Provider-blocked v41 deployment and unfinished natural robotics
  delivery cannot be replaced by a successful API call.
- **Operational:** remaining pending work is neither a pass nor automatically
  a software failure. The parent owns waiting-time/capacity classifications,
  deduplicated operation totals, open issues and the final campaign verdict.

## Snapshot boundary

The exact Cosmos native image `5e2680aa1f8332413638ec1bc962c3796a79a314c1c84f5456d32aa916839e32`
and checkpoint bundle `573bf6acacb90461ca0cc06f850f550dc48e34579d79f866da2b1691097ff120`
have strict CUDA/CRIU restore witnesses, including the recorded release 179
transfer children. The LeRobot coordinator is not itself a GPU snapshot.
Warm-host-cache restore measurements do not become empty-node/image-pull cold
start measurements.

For the other Apps this overlay makes **no new exact-current-runtime snapshot
qualification**. Historical capability records are linked, not discarded, but
cannot be inherited after an image/configuration change or generalized across
untested shapes/options. This statement means “not requalified here,” not
“the platform has no snapshot implementation.”

## Reproducibility and remaining ownership

The read-only generator is
[coverage_overlay.py](../../../scripts/qualification/coverage_overlay.py);
reviewed statements are in
[coverage-overlay-notes-20260919.json](../../../scripts/qualification/cases/coverage-overlay-notes-20260919.json).
It refuses incomplete inventory pagination, omitted models/App identities,
missing dimensions/references and unscoped ready/qualified states. It pins
original bytes without rewriting them. Frozen copies remain under the protected
campaign `coverage-overlay-20260919T0435Z/evidence` directory.

Focused tests cover inventory clones/exclusions, source immutability,
configuration-versus-execution distinction and claim-boundary validation.
The parent campaign aggregator owns operation counts and phase timing; this
overlay deliberately does not reproduce or sum them. Later evidence should
create a new timestamped overlay, not mutate this snapshot or its originals.
