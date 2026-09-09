# BioNeMo Research Workbench

## Start here

The default chat is the tools-enabled **BioNeMo Research Workbench** on
GLM-5.3-Flash. Its landing page presents four grouped tutorial cards. Clicking
one starts a tool-enabled chat for Protein Folding & Structure, Docking &
Molecular Design, Sequence & MSA, or Genomics & Cell Biology. Every tutorial
first queries the live catalog, then lists the available models in that group,
shows a bounded example, and offers a reproducible benchmark across comparable
models, skills, and MCP calls. They do not spend model capacity until the user
chooses a specific run. All examples are research-only and non-clinical.

## Protein folding and structure

OpenFold2, OpenFold3, and Boltz2 are structure prediction models. ESM2 and
ESM-C provide supporting embeddings and scoring. The tutorial shows exact,
bounded requests and a fixed-input benchmark plan first; choose a model run
only when ready. A successful PDB/mmCIF result opens in a large inline 3Dmol.js
panel with rotation, zoom, reset, and representation controls.

## Molecular docking and design

DiffDock scores ligand poses; GenMol and MolMIM generate molecules; RFdiffusion
creates backbones; ProteinMPNN designs sequences. Use the bounded composed
workflow for GenMol → DiffDock → Boltz2, or RFdiffusion → ProteinMPNN →
OpenFold3. Treat scores as hypotheses requiring wet-lab validation.

## Sequence, evolution, and MSA

Evo2 generates DNA/RNA sequence outputs. MSA Search produces alignments, and
the MSA-to-structure tutorial passes one bounded alignment into OpenFold3.

## Genomics and cell biology

AlphaGenome, scVI/scANVI, Cellpose, ESM2/ESM-C, and Parabricks services are
available through the model MCP catalog where configured. Large files should be
uploaded or staged, never pasted into prompts.

## Full model inventory

Ask “list every model” to call the model inventory tool. Group results by
structure, docking, design, sequence, MSA, genomics, imaging, and embeddings.
The inventory reports readiness and backend without exposing credentials.

## Benchmarking

Ask for a benchmark with a fixed public input. The assistant should run the same
input through selected related models, record cold/warm latency, status, output
size/schema, and artifact links, then present a comparison table. Never compare
different inputs or silently retry failed model jobs.

## Instance operations

The `instance-admin` tools are intentionally enabled for this owner-controlled
endpoint. They can install packages, run scripts, download files, convert data,
and inspect the container. Prefer `/workspace` for durable work and report every
command and generated artifact.
