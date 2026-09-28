---
name: msa-search-nim
description: Search protein homologs through the bounded bionemo_msa_search NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# MSA Search NIM (hosted, bounded)

Use `bionemo_msa_search` with `sequence` for a standard search or `sequences`
for a paired search. Allowed databases are Uniref30_2302,
colabfold_envdb_202108, and all. Results are capped at 500 alignment sequences.
Return A3M/FASTA and JSON artifacts; alignment depth does not by itself prove
structure accuracy.
