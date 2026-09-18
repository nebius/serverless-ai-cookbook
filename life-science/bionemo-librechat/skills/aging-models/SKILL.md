---
name: aging-models
description: Predict biological age from DNA methylation (altumage) or clinical biomarkers (phenoage) via the scientific gateway native lane.
license: Apache-2.0 AND CC-BY-4.0
---

# aging models (native): altumage, phenoage

Typed tools `infer_altumage_native` and `infer_phenoage_native` on the
`bionemo-models` MCP server (LibreChat suffixes tool IDs). Shared rules:
`scientific-gateway`. Both are strict, exact-field contracts; call
`get_model_schema` for the live schema — its example wins over this skill.

## altumage (typed tool `infer_altumage_native`)

Methylation aging. Requires exactly 20318 unique CpG site names plus 1–128
samples, each with exactly 20318 beta values (nulls only with
`missing_values: "reference_median"`). This is a large payload — send it as
real uploaded/requested data, never hand-typed. Do not shorten the CpG list.

Use the installed native file client for a real dataset. Prepare one JSON file
with `cpg_sites`, `samples` (each `sample_id` and `beta_values`) and the explicit
`missing_values` policy, then run:

```bash
/opt/scientific-client/bin/python /opt/bionemo/invoke-native.py \
  --model altumage --input /workspace/study/input.json \
  --output-dir /workspace/study/run --idempotency-key STABLE_STUDY_KEY
```

The helper reads the complete arrays directly from disk, validates the live
schema and sends them outside chat context. The native contract accepts those
arrays inline **in the file-backed API request**, not just artifact references.
Do not create an upload per CpG/sample merely because the dataset is large;
ordinary bounded inputs can use this single request within the existing server
size limit. For larger requests use the existing artifact helper and the exact
advertised fields. Reuse already finalized uploads and original receipt keys.
Never print a 20,318-element array into chat.

For multiple independent cohorts or feature-order checks use the installed
`scientific-workflow.py` native steps to queue these input files sequentially.
Prefer the typed `run_scientific_workflow` tool with that saved plan file and a
workspace-relative output directory: it preflights paths and returns one
existing execution job to poll, without constructing a shell command.
Permute CpG labels and their beta columns together; do not silently reorder only
one side. Preserve missing-value policy and source hashes, and distinguish a
feature-order invariance check from validation of biological age accuracy.

## phenoage (typed tool `infer_phenoage_native`, clinical)

Clinical aging from blood biomarkers: `samples` 1–512, each with `sample_id`
(unique) and exactly these numeric fields: `age_years`, `albumin_g_l`,
`creatinine_umol_l`, `glucose_mmol_l`, `c_reactive_protein_mg_dl` (raw mg/dL,
not log, not mg/L), `lymphocyte_percent`, `mean_cell_volume_fl`,
`red_cell_distribution_width_percent`, `alkaline_phosphatase_u_l`,
`white_blood_cell_count_10e3_per_ul`.

```json
{
  "samples": [
    {
      "sample_id": "synthetic-clinical-0",
      "age_years": 50,
      "albumin_g_l": 45,
      "creatinine_umol_l": 80,
      "glucose_mmol_l": 5,
      "c_reactive_protein_mg_dl": 0.1,
      "lymphocyte_percent": 30,
      "mean_cell_volume_fl": 90,
      "red_cell_distribution_width_percent": 13,
      "alkaline_phosphatase_u_l": 70,
      "white_blood_cell_count_10e3_per_ul": 6
    }
  ]
}
```

## Result

Predicted age (years) per sample. Present as research epigenetic/clinical
estimates, not medical assessments. Live verification status: readiness report.
