---
name: single-cell-analysis
description: Prepare raw-count AnnData, run hosted scVI or scANVI fit-transform, and inspect retained latent embeddings and UMAP outputs with batch/label provenance. Use for single-cell integration, not unexposed differential-expression or cell-label prediction APIs.
license: Apache-2.0
---

# Single-cell integration

Read `scientific-gateway`; discover App `scvi-scanvi` and its public schema.
This App fits a model per input dataset. It is not inference against a shared
pretrained atlas, and a GPU snapshot is not a cache of this customer's analysis.
Primary method reference: https://docs.scvi-tools.org/en/stable/tutorials/index.html

## Prepare and submit

1. Inspect the actual `.h5ad`: cell/gene IDs, shape, sparse format, counts source,
   `obs` columns and missing values. `X` must contain finite, nonnegative raw
   integer counts, not log-normalized values. Check the entire matrix in bounded
   chunks; a small top-left sample is not proof of valid data. Preserve raw
   input and provenance if moving counts from a named layer into a new file.
2. Select `scvi` for unsupervised integration. For `scanvi`, additionally select
   the real label column and explicit unlabeled category present in that column.
   Verify known labels and the unlabeled subset. Do not invent biology labels
   or batch columns. Record filtering and highly-variable-gene choices rather
   than silently changing the supplied dataset.
3. Get the exact published upload field and research acknowledgement from the
   schema. Upload outside chat; do not send multipart worker URLs directly or
   copy HDF5/base64 into a tool argument. Retain the selected batch/label keys,
   seed, latent dimensions and epochs. Current worker bounds include 64 MiB,
   100,000 cells, 50,000 genes and 20 epochs; live gateway bounds take priority.
4. Use a durable native job and retain verified output artifacts. Workbench
   client helpers are optional in other MCP clients; see gateway portability.

## Inspect real outputs

The current runtime exports `integrated.h5ad`, `latent_embeddings.csv`,
`umap_embeddings.csv`, a preview and trained-model files. Check row count,
finite values and exact cell-ID alignment before joining metadata. Preserve the
manifest, model/packages, training settings and input hash. UMAP geometry alone
does not demonstrate successful batch correction or conserved biology.

The adapter does **not** currently export scANVI predicted labels/probabilities
or a differential-expression API merely because upstream scvi-tools supports
them. Report that gap when asked. A labeled benchmark needs its own split and
metrics; do not leak reference labels into the claim of predictive performance.
