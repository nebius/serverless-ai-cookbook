---
name: diffdock
description: Dock a research ligand to a protein structure, retain ranked poses, and compare them without corrupting atom correspondence.
license: Apache-2.0 AND CC-BY-4.0
---

# DiffDock research docking

Public App `diffdock`; typed MCP tool `infer_diffdock_native`. Discover the
current schema before preparing inputs. See `scientific-gateway` for credentials,
durable operation IDs, idempotency and artifact retrieval. This predicts docking
poses; it does not establish binding, efficacy or clinical suitability.

## Input preparation

The current native adapter accepts:

- `protein`: actual UTF-8 PDB text containing ATOM records, not a filename.
- `ligand`: SMILES and `ligand_file_type: "txt"`.
- `num_poses`:1–4; `time_divisions`:3–20; `steps`:1–20 and no greater
  than time_divisions; `random_seed`:1–2^31-1.
- Defaults: one pose,20 time divisions,18 steps,seed1.
- No `save_trajectory` or `skip_gen_conformer` in this bounded adapter.

The live schema wins if these settings change. Read the real receptor file into
a request JSON using a file-based Python command; do not paste entire structures
into chat, tool descriptions or shell arguments. Retain input hashes, receptor
chain preparation, ligand chemistry and exact model settings.

Use the installed native client with the finalized JSON file:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-native.py \
  --model diffdock --input /workspace/study/input.json \
  --output /workspace/study/run --idempotency-key STUDY_LOGICAL_REQUEST
```

Consult `--help` for wait/recovery options. A timed observation is not a finished
model run. Never submit a new key to recover the same intended job. For multiple
studies, use the existing durable scientific-workflow helper rather than shell
backgrounding or simultaneous submissions under a one-operation key.

## Results and visualization

Retain the full JSON result. `ligand_positions` contains ranked molblocks and
`position_confidence` contains their scores. Do not silently reorder confidence
and pose arrays. Use the existing operation-aware structure viewer rather than
copying coordinates into a tool call. A negative score is not a failed API call;
a high score is not proof of correct docking.

## Experimental-reference comparison

A redocking comparison needs a held-out experimental ligand and the same
receptor coordinate frame as the prediction. Do not feed those reference ligand
coordinates into a SMILES-only docking input and claim a held-out experiment.

For multiple runs prefer `workbench_compare_docking_batch`: supply a `runs` list
of distinct `run_id`, optional scientifically justified `group_id`, and actual
`reference_file` plus `result_file` or `prediction_file`. Confirm
`same_coordinate_frame: true`. It invokes the same tested helper once and saves
a complete combined report and CSV, with separate per-group run counts,
top-ranked-pose counts and all-pose counts. Omitted group IDs use exact reference
hashes. Never call all-pose counts top-ranked selections or infer group identity
from filenames. Reuse the deterministic combined report; an optional narrative
must agree with the explicit denominators and retain non-comparable poses.

For a combined study report use `workbench_assemble_report` with the existing
deterministic Markdown and CSV sections. It preserves numerical strings and
checks table widths; it does not validate an optional narrative. Choose a new
output directory, preserving earlier reports and their failures.

For a single run use `workbench_compare_docking`. Supply workspace-relative
`reference_file`, `result_file` (or predicted SDF `prediction_file`), and
`same_coordinate_frame: true` only after confirming that frame. It invokes the
same tested helper below, returns deterministic ranked metrics and retains the
complete mapping, method and input/output hashes. Quote those saved values in
the report; do not implement another atom-index calculator. The CLI equivalent:

The typed tool also saves `report.md` and `rows.csv`, already rendered from the
verified metrics. Reuse them. `rank_facts` gives exact tied best/worst RMSD and
highest/lowest confidence ranks; a best-geometry pose need not have the lowest
confidence. These extrema do not by themselves demonstrate correlation.
Optional `threshold_queries` explicitly names `confidence_above` and
`rmsd_below_angstrom` for strict descriptive counts on unrounded values. No
threshold is chosen by default, and a descriptive count is not validation.
Use `/opt/scientific-client/bin/python` for RDKit chemistry scripts, not system
Python. In the CLI, a custom output stem also prefixes the generated CSV/report.

```sh
/opt/scientific-client/bin/python /opt/bionemo/molecule-analysis.py \
  --reference /workspace/study/reference-ligand.sdf \
  --result /workspace/study/run/result.json \
  --same-coordinate-frame \
  --output /workspace/study/docking-comparison.json
```

Confirm the shared receptor frame before that flag. The helper computes unfitted
heavy-atom pose RMSD over exact graph/stereochemistry-preserving mappings. It
does not align the ligand, repair chemistry, normalize protonation/tautomers or
invent a success threshold. It saves atom correspondence, input hashes, library
versions, all ranked results and model confidence separately. Changed chemical
identity or incomplete symmetry enumeration is explicitly not comparable.

Important mapping rule: `prediction.GetSubstructMatches(reference)` returns
prediction indices in reference-atom order. Reversing this correspondence can
produce plausible but false RMSDs. See the
[RDKit matching reference](https://www.rdkit.org/docs/source/rdkit.Chem.rdchem.html).

Report top-ranked and best-of-N pose agreement separately, with N and the
predeclared study threshold. Do not fit away a docking error. No result here is
an AutoDock score, binding-affinity measurement or biological validation.
