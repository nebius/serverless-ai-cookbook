# Life Science Serverless AI Cookbook

This index collects healthcare and life-science examples in the Serverless AI Cookbook. Keep every example nonclinical, reproducible, and clear about input data and expected artifacts.

## Recipes

| Recipe | Workload | Runtime | Safety and data notes |
| --- | --- | --- | --- |
| [`monai-medical-imaging-job`](./monai-medical-imaging-job/README.md) | Synthetic MONAI 3D segmentation inference with optional Object Storage output | Nebius AI Job | Synthetic data only, no PHI, not diagnosis or clinical validation |
| [`openmm-simulation`](./openmm-simulation/README.md) | GPU-backed molecular dynamics simulation with OpenMM | Nebius AI Job | Public/bundled PDB examples; scientific protocol must be adapted and validated |
| [`parabricks-deepvariant`](./parabricks-deepvariant/README.md) | NVIDIA Parabricks DeepVariant genomics pipeline | Nebius AI Job | Uses tutorial or staged genomics data; follow data governance for real samples |

## HCLS Guardrails

- Use synthetic, public, or explicitly approved data only.
- Do not include PHI, patient records, customer-confidential data, or unpublished proprietary sequences.
- Do not present examples as diagnosis, treatment guidance, triage, clinical decision support, or validated medical evidence.
- Start with the smallest viable GPU and a bounded timeout.
- Persist only the artifacts needed to inspect or reproduce the run, and document cleanup.
