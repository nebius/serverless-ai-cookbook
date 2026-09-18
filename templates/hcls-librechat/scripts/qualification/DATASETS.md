# Scientific qualification datasets and evaluators

These scripts prepare public scientific inputs and measure model outputs. They
do not launch GPU work. The campaign manager coordinates customer identities,
public requests, available capacity, timing and release receipts.

## Reproduce preparation

Install `requirements-evaluators.txt` in an isolated environment, then run:

```sh
python datasets.py --output /secure/campaign/datasets --repetitions 3
python -m unittest -v test_evaluators.py
python evaluators.py --manifest /secure/campaign/datasets/cases.json \
  --case-id openfold2-1ubq-A-r1 --result /secure/run/result.json
```

The manifest contains payloads validated against the actual hosted contracts,
experimental-reference URLs, SHA-256, local paths, selected chains and explicit
protocol deviations. Each download is frozen on first preparation. Reusing a
directory preserves its bytes. A fresh directory obtains a new dated cohort.
Failed preparation remains in `preparations` and does not become a passing case.

For the expanded campaign, use `--include-batch --include-auxiliary
--include-aging --design-backend /path/to/k8s-inference`. Additional generators
are intentionally separate so an expensive public download is not repeated
when another study is extended:

```sh
python complex_cases.py --output /secure/campaign/complexes
python medical_cases.py --archive /secure/Task09_Spleen.tar --output /secure/campaign/ct
python general_cases.py --structure-manifest /secure/campaign/datasets/cases.json --output /secure/campaign/general
python followups.py --manifest /secure/campaign/datasets/cases.json --results /secure/campaign/completed-native --output /secure/campaign/msa-followups
```

`followups.py` only prepares requests from completed, valid, informative MSAs;
it does not submit inference. Preserve source operation identities and alignment
hashes when comparing against query-only inputs. A search returning only its
query is valid service output but cannot support a homolog-information study.

## Prepared campaign, 18 September 2026

The immutable generated manifests are outside Git under the campaign's secure
evidence root. Source code, provenance rules and this protocol belong in Git;
credentials, signed URLs and generated payloads do not. Earlier manifest
versions remain unchanged after execution starts.

| Manifest | Cases | Scope |
| --- | ---: | --- |
| `qualification-datasets-v5` | 895 | 20 Apps: folding, docking, design, MSA, inverse folding, molecules and aging |
| `qualification-complexes-v1` | 45 | Three real heteromers × five folding Apps × three repetitions |
| `qualification-medical-v2` | 27 | Nine real CT scans × label-only, point-only and combined prompts |
| `qualification-msa-followups-v2` | 114 | 38 completed informative alignments × three folding Apps |
| `qualification-general-v1` | 148 | Evo2 32, Qwen 60, SDXL 36 and chest-X-ray 20 |

These 1,229 executable cases cover 25 Apps at fixture level, not release
qualification. The manager owns the additional speech and Cosmos studies.
`cases/coverage-v1.json` enumerates all 32 Apps, their distinct modes and missing
coverage. A case count is not a substitute for unique targets, actual client
execution, batch/lifecycle behavior or scientific accuracy.

The coverage matrix now separates `current_evidence` from superseded
`historical` gaps. Its dated references point to retained public cohort receipts
or explicitly isolated candidates, with hashes for frozen summaries. Counts are
scoped to the named retest, not cumulative proof of all modes. In particular,
MolMIM finite-search exhaustion remains failure, Proteina ligand/AME isolated
execution is not public qualification, and Cosmos isolated snapshot restoration
does not close the pending ordinary-customer snapshot gate. Unchanged rows make
no new release claim. Run `python -m unittest -v test_coverage.py` for these
machine-readable distinctions; the manager's defect ledger retains the full
sequence of original failures, deployments and retests.

The main 895-case manifest includes eight matched folding Apps (60 cases each),
36 redocking jobs, 36 design jobs across the five originally requested Apps,
40 MSA searches, 180 ProteinMPNN requests, 48 MolMIM requests, 36 GenMol requests,
19 PhenoAge jobs and 20 AltumAge jobs. Native OpenFold3 exposes a fixed seed;
repetitions there are not independently seeded samples.

## First experimental cohort

Twenty proteins span 20–247 residues and diverse folds: Trp-cage, a designed
zinc-finger fold, crambin, engrailed homeodomain, BPTI, protein G, villin,
chymotrypsin inhibitor 2, cold-shock protein, protein L, ubiquitin, barstar,
tenascin, Top7, thioredoxin, lysozyme, myoglobin, adenylate kinase, GFP and TIM.
OpenFold2 and Boltz2 receive matched single-sequence inputs; the Boltz alignment
contains only the query. These historical experimental structures can overlap
training data. They measure a real reference-based workflow and deployment
behavior, not held-out generalization or the model paper's original benchmark.

Docking uses six actual crystal complexes: trypsin–benzamidine (3PTB), ABL–imatinib
(1IEP), streptavidin–biotin (1STP), AKT1–allosteric inhibitor (3O96), estrogen
receptor–4-hydroxytamoxifen (3ERT), and estrogen receptor–estradiol (1A52).
The ligand is removed from receptor input, and its SMILES are derived from the
experimental ligand graph. Crystal ligand coordinates are evaluation-only.
Each case uses a specified protein chain; waters and cofactors are removed.
Thus these are controlled redocking studies, not PDBbind benchmark reproduction.
RCSB ModelServer SDFs sometimes carry a 2D header despite experimental 3D
coordinates; RDKit's warning is retained and understood. No coordinates are
flattened or changed.

Three heteromer studies use barnase/barstar (1BRS A+D), trypsin/BPTI (2PTC E+I)
and chymotrypsin/eglin (1ACB E+I). Canonical input sequences are distinct from
coordinate-observed residues. Independent metrics include interface C-alpha
contacts, interface RMSD and partner RMSD after fitting the receptor. These
metrics are not DockQ or CAPRI scores. No templates or homolog MSAs are supplied
in this initial complex study.

The design study includes Proteina-Complexa PD-L1 targets, BoltzGen PD-L1
binders, Mosaic ubiquitin hotspots 8/44/70, both BindCraft MPNN lanes and
48/76/128/256-residue RFdiffusion backbones. Geometry and yield are only initial
constraints: target preservation, contacts and independent refolding remain
separate evidence, and experimental binding is not established computationally.
Proteina's BestOfN pipeline generates two replicas per requested sample.

## Other primary scientific data

- **PhenoAge:** 512 distinct complete-case NHANES 2009–2010 adult participants
  from the CDC DEMO_F, BIOPRO_F, CBC_F and CRP_F tables. Units are converted to
  the published formula exactly, including CRP mg/dL. An independent 60-digit
  Decimal implementation is the numerical reference. The study includes 16
  individual samples and batches of 32, 128 and 512. It does not evaluate
  mortality prediction or population estimates; age 80 is top-coded.
- **AltumAge:** all 16 original published example methylation profiles, with
  the complete 20,318-CpG panel and provided chronological ages. Independent
  NumPy float64 inference reads the original H5 weights; column reversal and
  explicit 1%/5% reference-median imputation test mapping and missingness.
  These are example data, not a held-out generalization benchmark.
- **CT segmentation:** original Medical Segmentation Decathlon spleen NIfTI
  scans and expert masks, under CC BY-SA 4.0. The official archive MD5 is
  `410d4a301da4e5b2f6f86ec3ddba524e`. Nine of the first ten training scans fit
  the API's 32 MiB envelope. The remaining 41,413,046-byte scan is explicitly
  `blocked_input_contract`, not silently downsampled. Point prompts use an
  expert-mask-derived interior location: assisted and automatic scores must
  not be conflated. VISTA label 3 means spleen; point-only output uses label 1.
  Expected training overlap and limited organ coverage prevent clinical claims.
- **Chest X-ray:** 20 distinct NIH ChestXray14 patient images, mirrored as JPEG
  in `BahaaEldin0/NIH-Chest-Xray-14` at pinned revision
  `932bcdba9d7d9590704d4f20bc70fc2c3a1bbad7`. Per-image SHA-256 and conversion
  provenance are retained. Labels are report-mined weak labels, not expert
  adjudication, and inputs are not original DICOM. No clinical qualification.
- **Evo2:** benign Arabidopsis chloroplast reference NC_000932.1, four loci,
  256–8,192-base prompts and 64–512-base continuations, two seeds. Alphabet,
  length and timings are checked; GC and reference identity are descriptive,
  not functional validity or variant-effect prediction.
- **Qwen/SDXL:** supplied scientific metadata extraction across chat, JSON and
  tool calls; and scientific illustration prompts across seeds/step counts.
  Images require independent visual review. Illustrations are not observations
  or anatomical truth; these fixtures do not establish paper reproduction.

## Metrics and verdict boundaries

- Structural outputs: exact input sequence, reference alignment/coverage,
  finite coordinates, least-squares C-alpha RMSD, and C-alpha lDDT within 15 A.
  `tm_score_kabsch` and `gdt_ts_kabsch` use one fixed sequence alignment and one
  Kabsch fit. They are not optimized TM-align/GDT scores, nor all-atom lDDT.
- Docking: matching heavy-atom ligand topology, symmetry-aware RMSD in the
  original receptor coordinate frame, centroid error, top-one/top-N below 2 A.
  Ligands are not independently superimposed, which would conceal bad poses.
- Service semantic completion, scientific accuracy and paper reproduction are
  separate. A chemically valid but wrong pose can pass the first and fail the
  second. No accuracy threshold is retrofitted after observing predictions.
- Repeated seeds are repetitions of the same scientific input. Report unique
  targets separately and do not treat repetitions as independent samples.
- Inverse folding retains all ATOM residues and numbering gaps. An X at an
  unresolved position must remain explicitly mapped and machine-readable.
  Recovery is measured only on resolved N/CA/C/O positions. Incomplete
  backbones are reported as partial scientific coverage; downstream refolding
  requires an explicit gap policy, never silent deletion or invented residues.
- Molecular scores are independently recomputed with RDKit. Requested yield,
  validity and similarity are distinct from optimization, synthesizability
  and efficacy. The initial MolMIM implementation sampled random latents while
  advertising CMA-ES; initial GenMol could underfill requests. Preserve those
  findings and require release-specific reruns after the manager's fixes.
- CT geometry/affine integrity and label semantics precede foreground Dice,
  IoU, precision, recall and volume. Empty foreground is not useful completion.

The input contract supports native `arguments`, or a scientific-batch envelope
with `preparation.inputs` to be uploaded before constructing `input_manifest`.
Paths resolve relative to the generated manifest. The runner supplies durable
idempotency keys and follows terminal artifacts. `evaluate(case, result, base)`
expects materialized artifact bytes, not only an artifact pointer.

Native artifact uploads require explicit `preparation.artifact_fields` entries
with `field` (dotted path or path-element list), `transport: "artifact"`, media
type, compression, local path, size and SHA-256. Existing `argument_path`
entries for inline PDB strings are provenance hints, not instructions to
replace a string with an ArtifactRef. This distinction prevents invalid typed
requests while exercising actual large-file upload/finalization paths.

## Corrections remain visible

`reevaluate.py` corrects evaluator defects without rerunning a model. It saves
the original evaluation by hash and appends a correction event containing the
old verdict, reason, immutable result hash and `gpu_rerun: false`. It updates
authoritative receipts; `--rebuild-summaries` is only for completed cohorts.
Corrections discovered so far include OpenFold3's nested structure envelope,
optional CIF occupancy, AlphaFold3's leading CIF provenance comments, and a
ProteinMPNN input residue with C/O but no CA. These were harness defects, not
model failures. Genuine runtime/quality failures remain in the evidence.

## Primary sources

- [RCSB PDB usage and CC0 policy](https://www.rcsb.org/pages/policies)
- [Ubiquitin experimental structure](https://www.rcsb.org/structure/1UBQ)
- [Trp-cage experimental structure](https://www.rcsb.org/structure/1L2Y)
- [Crambin experimental structure](https://www.rcsb.org/structure/1CRN)
- [ABL–imatinib structure](https://www.rcsb.org/structure/1IEP)
- [lDDT original paper](https://doi.org/10.1093/bioinformatics/btt473)
- [DiffDock source and research protocol](https://github.com/gcorso/DiffDock)
- [OpenFold source](https://github.com/aqlaboratory/openfold)
- [Boltz source](https://github.com/jwohlwend/boltz)
- [Medical Segmentation Decathlon paper](https://www.nature.com/articles/s41467-022-30695-9)
- [VISTA model metadata](https://github.com/Project-MONAI/model-zoo/blob/dev/models/vista3d/configs/metadata.json)
- [NIH ChestXray original paper](https://openaccess.thecvf.com/content_cvpr_2017/html/Wang_ChestX-Ray8_Hospital-Scale_Chest_CVPR_2017_paper.html)
- [NIH public dataset terms and label provenance](https://docs.cloud.google.com/healthcare-api/docs/resources/public-datasets/nih-chest)
- [Arabidopsis chloroplast reference paper](https://pubmed.ncbi.nlm.nih.gov/10574454/)
- [CDC NHANES 2009–2010 laboratory data](https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2009)

Tavily research request IDs: `b7c9ffbc-e545-4c48-8c0e-18369a441e7f`,
`7bb1e474-a016-4948-837e-21da4f2974a7`,
`82c4c7e8-63cd-40f1-adec-6080f85e51e2`,
`1ad4e87e-9ddc-47ff-b575-1d4918c619ce`.
