---
name: scientific-agent-tutorials
description: Start a scientific research workflow by choosing an App or model family, preparing a schema-accurate example, or benchmarking related models through Scientific AI Apps.
license: Apache-2.0 AND CC-BY-4.0
---

# Scientific AI Agent tutorials

Offer only the tutorial group relevant to the user's scientific question.
Read `scientific-gateway` first — it defines discovery, the three invocation
lanes, idempotent submit-once behavior, polling, artifact handling and error
rules. Report the model ID, runtime variant, operation/request ID, elapsed
time, output artifact references, and limits for every run. Research-only and
non-clinical. Tutorial cards teach first and run only after the user chooses a
workflow; never submit, poll or retry jobs as a side effect of opening a card.

## Available file workflows

The current LibreChat workbench has authenticated Workspace uploads/downloads,
verified file clients, durable study execution and a native structure viewer.
Discover actual files before using them: an ordinary chat attachment or local
path is not automatically a gateway artifact. Use the installed upload helper
to finalize native artifact inputs; batch phases upload their own source and
manifest. The viewer handles supported native results, not arbitrary batch
collections. For another MCP client, check its available file executor/viewer;
do not claim LibreChat-only tools exist there. See `scientific-gateway` and its
portable-client reference. Never paste large file bytes through chat.

## Protein folding and structure

Native: `boltz2`, `openfold2`, `openfold3` (each with its exact payload
contract). Batch: `scientific-batch` (alphafold3, openfold3-openbind,
protenix-v2, esmfold2, esmfold2-fast, proteina-complexa). Keep native vs batch
lanes distinct. Example: show a schema-accurate request for a short fixed
sequence (e.g. the openfold2 four-field example) and how the same input maps to
MCP and HTTP lanes; run only on explicit choice. Benchmark with one fixed
sequence: compare latency, status, confidence fields, artifact sizes; surface a
failed job with its error category without blind retries.

## Molecular docking and design

Native: `diffdock`, `genmol`, `molmim`, `proteinmpnn`. Batch: `rfdiffusion`,
`bindcraft`, `boltzgen`, `mosaic`. Workflows: `drug-discovery-pipeline`,
`protein-binder-design`. Scores and generated structures are hypotheses.

## Sequence, evolution, and MSA

`evo2` (DNA generation) and `msa-search` (A3M alignments), then
`msa-structure-prediction-pipeline` into MSA-capable structure models.

## Genomics, aging, imaging, and media

`aging-models` (altumage methylation aging; phenoage clinical aging),
`imaging-models` (nv-reason-cxr-3b chat reasoning; nv-segment-ct CT
segmentation), `microscopy-segmentation` (Cellpose), `sam2-segmentation`
(prompted image/video masks), `single-cell-analysis` (scVI/scANVI),
`speech-workflows` and `clinical-asr-evaluation` (transcription and comparison),
`clinical-documentation` (source-linked draft reports), `generative-media`
(SDXL, Cosmos and Wan), `qwen3-8b`
(OpenAI-chat). Availability comes from discovery — a group member absent from
the live catalog is reported as unavailable, not substituted.

## GPU molecular dynamics

No GROMACS MCP server is connected in this deployment. Explain that GPU
molecular-dynamics execution is unavailable here if requested.

## Inventory and workspace

For example data, use `scientific-starter-data`; never invent fixture ownership.
Use focused `workbench_list_apps` when available, otherwise
`list_models`/`list_scientific_models` (or HTTP discovery) when the user
asks to list models; group results as structure, docking/design, sequence/MSA,
aging, imaging, media. Report per-model protocol and runtime variant. Web
research tools, if configured, follow the `tavily-research` skill; state
plainly when a configured MCP server is absent.
