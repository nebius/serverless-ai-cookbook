# VBench prompt inputs

The default batch contains 200 prompts from the official [VBench content-category lists](https://github.com/Vchitect/VBench/tree/fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490/prompts/prompts_per_category), 25 from each category: animal, architecture, food, human, lifestyle, plant, scenery and vehicles.

- Publisher: [VBench contributors, Vchitect/VBench](https://github.com/Vchitect/VBench).
- Pinned revision: `fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490`.
- License: [Apache License 2.0](https://github.com/Vchitect/VBench/blob/fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490/LICENSE), reproduced unchanged in [LICENSE](LICENSE).
- Source files and SHA256 checksums: [source.json](source.json).
- Selected source lines, unchanged prompt text, video seeds and CSV checksum: [prompts.source.json](prompts.source.json).

The preparer walks the eight category lists in alphabetical order. Python's `random.Random(42)` selects 25 prompts without replacement per list; a separate seeded generator supplies video seeds. No generated clips were used to choose the prompts or seeds. The files each contain 100 source prompts. CSV wrapping, IDs, category tags, line numbers and seeds were added for this recipe; prompt wording was not rewritten.

These are **published generation prompts**, not production footage or a dataset of real camera recordings. The VBench authors designed this suite for testing video generation. See their [prompt-suite documentation](https://github.com/Vchitect/VBench/blob/fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490/prompts/README.md).

This 200-prompt batch, with one generation seed per prompt, is for running and inspecting a reproducible workload. It does **not** follow the complete VBench sampling and scoring protocol and must not be reported as a VBench score. The recipe does not install the VBench evaluators or compare against a leaderboard.

Verify the bundled selection without network access:

```bash
python3 scripts/prepare_data.py --verify
```

Regenerate it from the checksum-verified upstream files, or prepare a larger batch:

```bash
python3 scripts/prepare_data.py
python3 scripts/prepare_data.py --per-category 100 --output data/full-catalog.csv
```

The second command creates 800 prompts and a matching `full-catalog.source.json`. It prepares input only; generation is a separate paid step. Cached source files are stored in ignored `.state/vbench-source/`. Fetching uses GitHub's public contents API and is subject to its anonymous rate limit.
