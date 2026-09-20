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
Prefer the typed `run_scientific_workflow` tool with its native `steps`, each
containing `kind`, `id`, `model`, `input_file` and `idempotency_key`, plus a
workspace-relative output directory. It constructs the canonical plan,
preflights paths and returns one execution job to poll. An existing plan-file
mode remains for recovery; do not hand-write a plan for a new ordinary study.
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
estimates, not medical assessments. Runtime and numerical qualification require
evidence from the exact model version and reference method.

## Independent analysis of saved results

Use `workbench_analyze_aging` with `model_id` and a `cohorts` list of explicit
`label`, `input_file`, `result_file` workspace-relative paths. It reads exact
request/result files outside chat and returns retained deterministic CSV,
metrics, report and source hashes. It does not call either model again.

For PhenoAge also pass `coefficient_version`:
`levine-2018-supplement-rounded-v1`. The independent60-digit evaluator uses
the declared primary supplement equations. Do not substitute DNAm PhenoAge,
pyaging's alternative mortality conversion, or higher-precision coefficients
and label their differences a serving error.

For AltumAge the original pinned H5 and robust scaler are packaged. The helper
reads the actual model_config layer order, including SELU activation and
BatchNormalization; do not guess a network from alphabetically sorted weight
groups. Feature names and beta columns are aligned together. Missing values
only use the explicitly selected imputation policy. Multiple cohorts compare
only exact overlapping sample IDs with matching normalized inputs/policy:
one canonical sample versus16 reversed samples is a one-sample invariance
comparison, not16 pairs. All17 predictions can still be independently checked.

Optional `reference_ages_file` maps exact sample IDs to known chronological
ages. Those label errors are descriptive, not proof of generalization or
medical validity. Quote the saved deterministic row table and preserve any
numerical disagreement; never alter the reference to obtain a passing result.
