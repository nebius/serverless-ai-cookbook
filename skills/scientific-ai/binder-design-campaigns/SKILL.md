---
name: binder-design-campaigns
description: Plan and run bounded hosted Proteina-Complexa, BoltzGen, Mosaic or BindCraft campaigns, retaining target identity, seeds, filters, artifacts and negative candidates. Use for comparative binder-design batches and follow-up evaluation, not unsupported upstream deployment recipes.
license: Apache-2.0 AND CC-BY-4.0
---

# Binder-design campaigns

Read `scientific-batch` for transport and `protein-binder-design` for the
RFdiffusion/ProteinMPNN route. Adapt domain guidance from NVIDIA BioNeMo's
Complexa target/design/sweep/evaluate skills to these hosted Apps; do not launch
upstream Docker/NGC services or assume an upstream CLI flag is a gateway field.

## Freeze the experiment

Record target identity, selected chains/epitope, intended design operation,
sequence/structure source, binder constraints, exact model/runtime, seeds,
candidate count and filter thresholds. Define acceptance metrics and budget
before submitting a sweep. A PDB filename is not necessarily a target task ID.
Ask only for missing scientific choices, not approval already given for the run.

Read [model distinctions](references/model-contracts.md) for the selected App,
then its live `get_model_schema`, parameter schema and `input_artifact_contract`.
Do not load every model schema when only one is being used.

## Execute and evaluate

Use the installed durable scientific study for multiple bounded jobs and
dependent analyses. Each distinct parameter/seed combination has one stable
idempotency key and receipt directory. Respect queue/concurrency policy; pending
capacity is not a reason to change a key. Preserve failed/filtered/empty outputs
in the campaign table. Do not loosen filters or select only successful seeds to
make a campaign appear successful.

Download every manifest-declared design, sequence and score artifact; verify
hashes before interpreting them. Compare exact chains and residue numbering
when refolding or computing RMSD/contacts. Use the existing design-artifact,
structure and report phases where available. Retain candidate lineage from
target and seed through sequence, backbone, refold and final selection.

Report per-model candidate counts, accepted/rejected filters, measured latency,
queue time if available, and compute usage only when returned/measured. Scores
from different model families are not calibrated to each other. Confidence,
contacts and RMSD do not prove binding or efficacy; shortlisted designs remain
research hypotheses for independent evaluation.
