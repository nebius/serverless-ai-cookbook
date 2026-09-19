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

## Exact installed v52 follow-through

Frozen source `e4005cea9e8dd4429064104a53861e8a877016a9` was published as
OCI index `sha256:0c2a60ea79d3a2ff27c3927964ad5ddb95b02c7f21d94a86990b40200a29f182`
(amd64 runtime `sha256:5d82cb257547ce928dd0d7bc011638d4fc31b78e702f38c176dcb6625ea7596b`).
Task-owned Docker tests used that immutable image with network disabled. Only
test scripts, evidence and disposable workspaces were mounted; installed
renderer, LibreChat MCP environment processing, SDK transport and runtime
modules were not overlaid.

All 11 baseline SDK cases pass, including three CPU studies completed after
stdio disconnection. A separate real installed-MCP test rejects a compact
MindEval input before admission, preserves that failed draft, reconnects,
corrects it to full native records, rejects a known directory deliverable, then
finalizes and admits exactly one study through the unchanged launcher. An
independent worker completes it with the exact retained 381-character heading.
Its two-record fixture is synthetic transport evidence, not a new six-case
scientific or natural-client result.

Independent readback verifies all 22 nonempty final files/manifests across the
four CPU studies and the four installed runtime hashes against frozen source.
There were zero model/provider calls or cloud mutations. An initial private
readback test split on a literal escaped newline and failed its heading-length
assertion; that test is retained. The corrected test-only successor passes;
no runtime or image change was made.

Protected evidence: `U/workbench-v52-installed.bCjsMm/`:

- `acceptance.json`, SHA256 `81ea27c1a46f56f95d14da4adf09a0c856b17da3ecb91b17074b04c3ff4b9784`.
- `stdio-installed-gate.json`, SHA256 `37fea8455ddb2576e58cf6d456c65e4da4af4e9d2d1bde3ee4f5d79654960b5d`.
- `semantic-stdio-gate.json`, SHA256 `55dd1496163fe4a25ff152a8ce1337243ce5c5d5a0577efd3432d4f5470cf375`.
- Private semantic test SHA256 `b07de9412091215bbc2714654cb6411885285976d2193e4ffe4d968d4b9b7854`.

The private Rene replacement helper is prepared with this exact image and an
explicit Kimi-K3 planning candidate, retaining low reasoning and the existing
131072/8192 context/output settings. Six binding tests pass. Preparation is not
a cloud migration, current customer-state verification or a qualified default
planner decision. Plan SHA256:
`0ff062e7b42d5bd4817d95daae595f499988f23e563850e8c1dc4c0aac449464`.
Natural v52 acceptance remains a separate gate.
