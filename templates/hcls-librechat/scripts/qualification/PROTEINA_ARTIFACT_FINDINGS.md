# Proteina generated versus refolded structures — 18 September 2026

This is a source-grounded artifact diagnosis and offline repair evidence, not a
live-release or binding-efficacy claim. The campaign manager owns deployment.

## Confirmed retained-handoff repair

The retained evaluate handoff was fetched through the ordinary scoped public
artifact API, verified against SHA-256
`1aceb5ccf8414a41b687714680fec90c932f7b5e2e05c30b919d09b5cb08977e`
(122,918 bytes), and inspected without GPU recomputation. It contains both exact
CSV-selected AF2 refolds. Importantly, `id_gen=0` points to the filename with
`id_1`, and `id_gen=1` to the filename with `id_0`. All binder/CSV sequences agree.

The repaired collector exports two raw and two refolded PDBs, sanitized CSV with
logical artifact links, and a per-design provenance JSON. The independent
evaluator reproduces the CSV binder CA RMSDs as 1.870793488 and 2.039330298 Å,
with absolute differences 1.45e-7 and 5.42e-8 Å. Both refolded geometries pass the
defined CA checks; both raw geometries fail, and those measurements remain
visible. Two paired structures per design are not counted as two designs.

Backend source `141768b42` includes 97 passing adapter/companion tests, including
the actual retained handoff, reversed ordering, broken joins, path boundaries,
and in-flight upgrade compatibility. New requests receive both roles; already
admitted historical requests retain their frozen raw-only contract with explicit
legacy/unqualified-refold labels. The independent evaluator has 40 passing
tests. This evidence does not qualify ligand/AME modes, new live deployments,
experimental binding, or an Amber-relaxation claim.

## Observed public result

Case `proteina-complexa-pdl1-s1-n1`, operation
`a7398a7c-13f6-49ba-8cc7-fb9fbbbdc2ee`, completed on 18 September 2026 through
the public scientific-batch API. The request used one sample, seed 1 and 100
diffusion steps. Two designs are expected because the pinned upstream pipeline
uses two BestOfN replicas per input sample; this is not an overproduction bug.

The output manifest exposes a metrics CSV and two PDBs. Both PDBs preserve the
115-residue target chain A. Designed chain B has 88 residues. Its consecutive
C-alpha distances span 0.77–8.23 Å; 57–62% fall outside the original evaluator's
2.5–4.5 Å envelope. This is present in the actual coordinates and sequential
residue numbering, not a structure-parser ordering error. The target's
distances are normal, 3.69–3.91 Å. The raw designs have 20/32 interchain CA
contacts below 8 Å and no interchain CA pairs below 2 Å; these coarse contacts
do not establish binding.

CSV confidence and self-consistency columns are produced by a separate
refolding stage. They must not be presented as quality scores of the currently
exported raw coordinates without naming their different role.

## Exact upstream source contract

Pinned source revision: `54058860d43444c7289873f77d3e50b5b02348cd`.

- [`binder_eval.py`](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/evaluation/binder_eval.py):
  `pdb_path` is the generated input structure. The selected best refolded
  complex path is stored separately as `self_complex_pdb_path`, while its
  confidence values are stored in the `self_complex_*` columns.
- [`binder_metrics.py`](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/metrics/binder_metrics.py):
  `run_binder_eval` runs the requested folding model, compares generated and
  refolded coordinates, and preserves each refolded `complex_pdb_path`.
- [`colabdesign_utils.py`](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/utils/colabdesign_utils.py):
  for this protein-target/self-sequence protocol, AF2-Multimer writes
  `<sample_root>/AF2/<design_name>_self_seq_0_model1.pdb`. This is prediction
  followed by `save_pdb`; it is **not** an Amber-relaxed structure.
- [`refolded_structure_utils.py`](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/54058860d43444c7289873f77d3e50b5b02348cd/src/proteinfoundation/utils/refolded_structure_utils.py)
  also identifies `self_complex_pdb_path` as the selected refolded structure.

The current platform collector reads only the raw `pdb_path` column, then
sanitizes every path-bearing CSV column. This exports the raw design and loses
the refolded artifact/metric association. The public result therefore cannot
independently reproduce the quoted refolding metrics.

The CSV's `generation_args_nsteps=400` is also not proof that generation ignored
the requested 100: evaluation constructs flattened metadata from its separately
loaded config, and only the generation invocation receives the nsteps override.
Actual generation logs/config must be reconciled; do not replace runtime
provenance with evaluation defaults or infer a cache replay from this alone.

## Recommended collector change and tests

1. Resolve both `pdb_path` and `self_complex_pdb_path` from each unsanitized
   source CSV row. Require the declared files inside the exact run workspace;
   do not guess paths or silently substitute one role for the other.
2. Export raw/generated and AF2-refolded structures with distinct semantic roles
   and deterministic artifact names, retaining both. Never call AF2 output
   “relaxed” or raw generation “final validated prediction.”
3. Emit a per-design provenance document linking `id_gen`, generated sequence
   SHA-256, CSV row/metric prefix, raw artifact name and selected refolded
   artifact name. Include the actual folding runtime/checkpoint identity from
   the execution receipt and actual generation parameters, not default CSV
   metadata. Keep host filesystem paths out of the public document.
4. Validate matching sequence/target chains and compute independent raw-versus-
   refolded RMSD and geometry. Keep poor raw design geometry visible. Refolding
   success is not experimental binding validation.
5. Update role-aware output validation/counting: two replicas means two designs,
   not four designs when each design has raw and refolded files. Missing,
   duplicated, cross-workspace, wrong-sequence or missing-metric associations
   must fail clearly. Test the no-winner scientific outcome separately.
6. Retrieve the existing evaluate handoff, verify both refolded PDBs and their
   CSV links without GPU recomputation, then qualify the final changed release
   through public customer-shaped requests and immutable output manifests.

Sibling observations: Mosaic currently exports binder-only coordinates, so its
interface cannot be independently inspected despite an ipTM value. BoltzGen
exports binder+target and the initial retained pairs have plausible backbone
geometry and CA contacts. RFdiffusion backbone geometry is plausible at the
tested 48/76/256-residue lengths. None of those observations establishes
experimental binding or complete App/customer qualification.
