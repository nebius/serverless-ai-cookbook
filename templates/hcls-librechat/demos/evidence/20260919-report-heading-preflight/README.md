# Report heading formatting — v52 source candidate

The separate Kimi v50 diagnostic first selected compact MindEval summaries,
then corrected to all six retained full native records. Its second admitted
study still failed: the document title was a meaningful single line of exactly
381 characters, rejected by the deterministic helper's arbitrary 160-character
heading cap. Neither failed study nor the original report-only conversation is
rewritten or accepted by this repair. Raw source proof remains private at
`U/planner-comparison-kimi09-v50/{exact-title-validation,independent-check}.json`.

## Bounded repair

- Remove only the document/section heading character caps. Preserve heading
  text verbatim and require a nonblank single line without CR/LF.
- Reuse one metadata-formatting validator in report assembly, MindEval report
  publication and whole-study pre-admission validation.
- Express heading formatting and the helper's **existing** one-to-sixteen
  report-section cardinality in the shared typed schema. Invalid metadata can
  no longer be admitted merely because its paths exist. No new section limit
  is invented and no execution/model/context/tool/resource/retry limit changes.
- Preserve saved draft semantics, scientific input bytes, operation identity,
  numerical algorithms, report tables and the existing publisher.

## Measured source gate

165 focused report/MindEval/preflight/composer/discovery/engine tests pass in
6.46 seconds, including 35 new metadata cases. Tests cover 381- and 4,097-character
document/section headings, native-record completion, blank/CR/LF rejection before
admission, unchanged idempotent composition, schema/helper cardinality agreement,
and formatting checks before attempting to read missing report sources. Ruff
and whitespace checks pass. Initial fixture-import lint findings were fixed;
no runtime test failure was observed. The first pytest invocation emitted
unrelated cleanup warnings for older PostgreSQL socket directories; the retained
run uses its isolated evidence directory and completes without those warnings.

The exact retained 381-character title reproduces rejection in the frozen v51
helper. The candidate finalizes and completes that same six-record CPU study
using the existing composer and launcher. Its five final files plus completion
manifest verify as nonempty with exact byte lengths/SHA256; all 21 helper-manifest
artifacts also verify. No scientific/provider calls or cloud writes occur.

For a normal title, all 18 scientific report/data/transcript files remain
byte-identical to the old helper. The long title changes only the document
heading: all 17 numeric/raw-record/transcript files remain identical, preserving
126 literal messages and 30 supplied criterion scores. Helper/provenance hashes
correctly identify the new implementation; these are not expected to be equal.

Protected evidence in `U/report-metadata-v52.lizsEc/`:

- `junit.xml`, SHA256 `eb7f8215370a285a25775119d90d03790acceb8f47bfd8f86e5dda1da46e5bd1`.
- `retained-replay.json`, SHA256 `6146863a97f4e4d367c997d89c85952bc4f9946da149c8e028638548005d5ee0`.

This is source/offline retained-data evidence, not installed v52 or natural-client
acceptance. No planner is selected by this change. Root owns the immutable build,
fresh client qualification and any later customer handoff or migration.
