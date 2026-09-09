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
