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

## Exact installed v51 follow-through

The immutable source `1fbbaf09f710692dd63f818cfeebde1e6bdfd1fc` subsequently
passes on OCI index
`sha256:a48f373b30db574d76f96646e308ceb03ad330f100a0af89e2899402dd7a9803`,
amd64 manifest
`sha256:f7c7067f49270e1c39827e6c4467ca5338364a53474e26b0efc91503c5b99b66`.
Both Docker-only tests used networking disabled, the installed renderer,
LibreChat `processMCPEnv`, SDK stdio transport and scientific interpreter;
only qualification tests were mounted. No installed runtime was replaced.

The frozen committed stdio gate passes all 11 cases: three CPU studies finish
after client disconnect and verify 12 nonempty artifacts/manifests on a separate
readback. Ownership negatives still reject, and clinical credential cases stay
preflight-only without workers/provider calls.

A separately SHA-bound private test exercises the actual installed MCP semantic
boundary. A full first record plus compact second record fails both composer
finalization and direct admission, with zero studies. Reconnecting to correct
the inputs exposes the separately tested directory-deliverable error. Removing
that invalid directory finalizes the same scientific plan, preserving the old
draft and compact bytes. The unchanged launcher admits exactly one study;
repeated admission returns its same ID. After closing the client, the independent
worker completes; another stdio connection reads completion and verifies all
nine declared artifacts plus the manifest. Native record bytes and supplied
judgment measurements are preserved. These installed fixtures are synthetic;
the real six-record byte-equivalence replay is the separate source test above.

All four changed installed runtime files match the frozen source hashes.
All three task Docker containers were removed normally after success; private
workspace files and receipts remain retained. No cloud/customer migration,
planner selection, hosted inference or natural-study acceptance is claimed.

Protected receipts in `U/workbench-v51-installed.F2M4qk/`:

| File | SHA256 |
| --- | --- |
| `acceptance.json` | `c6304b6b292014f6942b8bf68b8afbcd0798f1558a4660ddf3b7e636d3c6d682` |
| `stdio-installed-gate.json` | `d26f230ea15303f8266fb949accdf143b6700e90dcfdf42f64fd94c0727d8c53` |
| `semantic-stdio-gate.json` | `ccf38320d617e7acf8d5277d83c2b176f19604134fc24896ca255fcd3cd7f515` |
| private `semantic-stdio-gate.cjs` | `a7a00391b4868379e46a0a1d0abbc35feb4b5a989856398eb6860b15f67f0b86` |

The frozen committed `installed_stdio_gate.cjs` is SHA256
`65d92ced82dd0e7ae8f942ea941a5703c0269a56e9fb3adff72a5426b11581a9`.
The proposed Rene candidate has a separate preparation-only binding at
`U/rene-replacement/v51-binding.json`, SHA256
`fdcdfb0ad5ae1b438656954ebfadf86eee9b25471b1be76b0ffcf4b6123aa0ce`.
It records seven unchanged startup/seed/owner/worker/composer source files,
the four changed preflight modules and exact image identity. Planner choice
remains explicitly pending; no deployment command or migration was executed.
The prior v50 local customer-state/login proof remains historical, not a v51
rerun or cloud-cutover approval.
