---
name: bionemo-workbench-tutorials
description: Start a BioNeMo research workflow by choosing a model family, following a working example, or benchmarking related models through the configured BioNeMo MCP tools.
---

# BioNeMo Research Workbench tutorials

Start every new research conversation by offering the tutorial groups below.
Report the backend, model, request ID, elapsed time, output artifact paths, and
limits for every tool run. These workflows are research-only and non-clinical.
Tutorial cards teach first and run only after the user explicitly chooses a
workflow. Do not download public inputs, submit jobs, poll, or retry jobs as a
side effect of opening a tutorial.

## Protein folding and structure

Prediction models: OpenFold2, OpenFold3, and Boltz2. Supporting representation
models: ESM2 and ESM-C. Do not describe the embedding models as structure
predictors.

Example: show a schema-accurate request for a short, fixed sequence and explain
how the same input would be submitted to two selected prediction models. Only
run it after the user chooses the run. For a successful run, use
`bionemo_json_summary` for scores and `bionemo_artifact_download` before
passing its returned path to `protein_viewer`; never place artifact bytes in a
model tool call. The viewer artifact spins by default and supports zoom.

Benchmark: hold the sequence fixed and compare cold and warm latency, completion
status, confidence fields, output schema, and artifact sizes. Surface one failed
job with its error category; do not retry unless the user explicitly requests a
retry policy, and do not compare models with different inputs.

## Molecular docking and design

Available models: DiffDock, GenMol, MolMIM, RFdiffusion, and ProteinMPNN.

Example: use a bounded GenMol -> DiffDock -> Boltz2 workflow, or RFdiffusion ->
ProteinMPNN -> OpenFold3. Treat binding scores and generated structures as
hypotheses requiring experimental validation.

Benchmark: use one receptor/ligand or design target per comparison. Record model
version, fixed inputs, latency, output count, score schema, and generated files.

## Sequence, evolution, and MSA

Available models: Evo2 and MSA Search, with an MSA-to-OpenFold3 workflow.

Example: generate or inspect a short public sequence with Evo2, run MSA Search,
then submit one bounded alignment to OpenFold3.

Benchmark: preserve sequence, alignment parameters, and sampling settings across
runs. Compare success, elapsed time, alignment depth, and structure artifacts.

## Genomics and cell biology

Available models: AlphaGenome, scVI, scANVI, Cellpose, ESM2, ESM-C, and the
configured Parabricks services.

Example: stage an input file instead of pasting a large dataset, invoke the
specific MCP model tool, and return the artifact path plus a concise result
summary.

Benchmark: use a single input cohort or image set and fixed preprocessing.
Compare latency, completion status, output shape, and artifact size.

## Inventory, tools, and workspace

Use the BioNeMo MCP inventory tool when the user asks to list models. Group its
results as structure, docking, design, sequence, MSA, genomics, imaging, and
embeddings; include backend readiness.

Tavily web search is available for current scientific references. The
`instance-admin` MCP provides owner-authorized shell, file, download, package,
and conversion access. Work under `/workspace` and state every command and
artifact that changes the instance.
