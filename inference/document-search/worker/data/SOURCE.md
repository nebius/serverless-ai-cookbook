# Dataset source and license

This example uses **1,000 distinct reference passages** from the `context` field of [Databricks Dolly 15k](https://huggingface.co/datasets/databricks/databricks-dolly-15k/tree/bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a). They are passage-documents for this search collection, not 1,000 complete articles. The original 55-document Python corpus is a separate example and is unchanged.

The [official dataset card](https://huggingface.co/datasets/databricks/databricks-dolly-15k/blob/bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a/README.md) identifies Databricks as the dataset owner and explains that reference texts for certain task categories were selected from Wikipedia. The dataset does not provide original Wikipedia URLs for each passage; this example links to the exact, pinned dataset record instead of inventing an article URL.

## Reproducible selection

- Dataset revision: `bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`.
- Read JSONL records in source order. Keep the first 1,000 `context` values with at least 80 whitespace-delimited words and distinct text after collapsing whitespace.
- Keep passage text unchanged. Use up to 160 characters of its associated instruction as a display title; instructions and answers are not embedded as passage text.
- Record source-line numbers, raw text hashes, normalized text hashes, record hashes and links in `source.json` and the prepared `manifest.json`.
- Selected input: **219,197 words**, **1,367,367 UTF-8 text bytes**, and **1,970 paragraph-aware chunks at 160 words**. Document count and chunk count are separate measures.

Preparation produces `documents.jsonl`, `manifest.json`, `LICENSE` and this `SOURCE.md`. It verifies the downloaded source, bundled card/license and every selected passage against pinned SHA256 hashes. This is a reproducible search corpus; it is not a new retrieval benchmark or a guarantee of factual accuracy.

## Attribution

Copyright (2023) Databricks, Inc. Dataset developed at [Databricks](https://www.databricks.com/).

Reference material includes Wikipedia (various pages), copyright Wikipedia editors and contributors. The official dataset card supplies this attribution.

The dataset is available under [Creative Commons Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/). The full legal text is retained in `LICENSE`. This selection adds source identifiers, titles and verification metadata; passage text is unchanged. Retain the attribution and license when redistributing the selected passage data.
