---
name: scientific-agent-tutorials
description: Start a scientific research workflow by choosing a model family, preparing a schema-accurate example, or benchmarking related models through the scientific model gateway.
license: Apache-2.0 AND CC-BY-4.0
---

# Scientific AI Agent tutorials

Start every new research conversation by offering the tutorial groups below.
Read `scientific-gateway` first — it defines discovery, the three invocation
lanes, idempotent submit-once behavior, polling, artifact handling and error
rules. Report the model ID, runtime variant, operation/request ID, elapsed
time, output artifact references, and limits for every run. Research-only and
non-clinical. Tutorial cards teach first and run only after the user chooses a
workflow; never submit, poll or retry jobs as a side effect of opening a card.

## Available file workflows

This deployment has no compatible bridge from LibreChat attachments to gateway
artifacts and no connected structure viewer. Inline model inputs and existing
caller-owned finalized gateway artifacts can be used through the published
tools. An attachment or local path cannot be submitted as an artifact reference.
For file-based tutorials, explain the preparation steps and stop before upload
or submission unless a verified file helper is available. Do not claim to upload
attachments, verify downloaded files, create downloadable UI links or display
structures. Never put large file bytes or signed handles into chat to bypass the
missing bridge. The legacy artifact/viewer helpers are incompatible with fs2.

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
segmentation), `generative-media` (sdxl; cosmos3-nano), `qwen3-8b`
(OpenAI-chat). Availability comes from discovery — a group member absent from
the live catalog is reported as unavailable, not substituted.

## GPU molecular dynamics

No GROMACS MCP server is connected in this deployment. Explain that GPU
molecular-dynamics execution is unavailable here if requested.

## Inventory and workspace

Use `list_models`/`list_scientific_models` (or HTTP discovery) when the user
asks to list models; group results as structure, docking/design, sequence/MSA,
aging, imaging, media. Report per-model protocol and runtime variant. Web
research tools, if configured, follow the `tavily-research` skill; state
plainly when a configured MCP server is absent.
