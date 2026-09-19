# MindEval semantic preflight — v51 source candidate

This fixes the observed admission gap in the preserved
[v49 Qwen diagnostic](../20260919-planner-qwen-diagnostic-v49/README.md).
That planner selected compact summaries, which passed file-path validation but
failed after durable admission. Its plan also declared helper directories as
final files; execution never reached that second potential error. The original
conversation, failed study, compact files and diagnostic remain unchanged.
The separate frozen v50 natural comparison is not modified by this source work.

## Bounded change

`report-assembly.py` now exposes one read-only record loader used by both its
existing MindEval publisher and the study admission validator. It checks all
existing record files for the same native state/config, nonempty literal
transcript, judgment-envelope and existing score/unique-ID requirements. It
does not transform native `state.judgment.judgment`, impute missing judgments,
reconstruct records, select alternative files or submit consultations. Checked
bytes must match the input hashes frozen by preflight. Earlier-step outputs
that do not yet exist remain deferred to the same runtime helper.

The composer uses that same validator when finalizing. Invalid plans retain
their saved draft and return an MCP tool error with an actionable full-record
message; they do not admit a study. A planner can select an actual full record
and finalize a new immutable revision in its existing turn. Admission rechecks
the complete plan; existing IDs, parameters, idempotence and execution remain
unchanged.

Selected discovery identifies exact helper directory names (`records`,
`transcripts`, `sources`) as not-file deliverables. Admission rejects those
directories, explicit directory syntax and existing workspace directories.
Concrete files such as `records/000.json` remain valid. The validator does not
guess arbitrary native/custom-script output types from their names.

## Source and retained-input gates

The focused suite passes 130 tests, including all-record checks (invalid first,
middle and last records), native/missing/malformed judgments, duplicate IDs,
deferred dependencies, unchanged valid admission, directory-versus-file output
contracts, and actual process-separated MCP rejection/correction without
admission. Existing report tests pass unchanged. One prior composer fixture
was missing an already-required run ID; the fixture is corrected rather than
relaxing the report's validator. Two initial new-test harness errors (invalid
write-json fixture and missing private execution-directory binding) were fixed;
they are not product/runtime failures. Ruff and whitespace checks pass.
The combined original core/workflow/execution/receipts/configuration suites,
report tests and new regressions pass **222 tests in 36.78 seconds**, retained
in `core-junit.xml` beside the focused receipt.

The protected replay uses the exact six compact files retained from the failed
diagnostic and the already-verified six full native records. Compact input now
rejects before admission/finalization. Full records pass. Compared with the
frozen v50 report helper, all 18 scientific files are byte-identical: report,
methods, rows, score tables, metrics, combined/raw records and full transcripts.
All 21 candidate manifest artifacts verify their byte sizes and hashes.
Provenance/helper/completion bytes change as expected to identify the new helper.

The unchanged measured data contains six consultations, two profiles, three
clinicians, five distinct criteria, ten profile×criterion cells, 126 literal
messages and 30 supplied score rows. These are distinct denominators, not a
clinical-efficacy or statistically independent comparison claim.

Protected evidence under
`U/semantic-preflight-v51.ujq3mn/` (`U` is the private unattended evidence root):

- `junit.xml`: SHA256
  `6df30228dd0695f88e511fed5d277cf4b77974e185d1a00ee5b87525e4a1748d`.
- `retained-replay.json`: SHA256
  `5ed45ba2d510a3011631ac5b510598402d5814d5de04a12f140cfcb819094d70`.

No cloud writes, scientific model calls, new provider calls, default-model
changes, budget/timeout/retry changes or deployment occurred. Immutable-image
and new natural-client adoption remain separate pending gates; neither v49's
failure nor v50's existing cohort is retroactively marked successful.
