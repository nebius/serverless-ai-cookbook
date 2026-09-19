# Compact whole-study composition — source candidate

This is a generic plan-construction repair, not a new planner, executor, model
choice, automatic continuation, or increased limit. The v49 client/runtime and
all original failed conversations remain unchanged. A new exact-image and
natural-client gate is required before claiming improved customer completion.

## Observed failures preserved

- Scientist09's v49 persisted error explicitly says maximum output truncated an
  `execute_command` tool call before its arguments completed. The saved final
  arguments are empty, so the attempted program's actual byte/token count is
  **unknown**, not measured from a reconstructed program.
- Scientist04 ended incomplete without admission after seven successful
  discovery/skill calls. Provider finish/usage was not retained; do not assign
  scientist09's demonstrated truncation cause to this case.
- Scientist02's prepared-only final response and scientist03's reasoning-only
  incomplete response likewise admitted no study. The latter's 80.139-second
  final generation was not an abort, preemption or hard graph-step stop.
- The v49 installed filtered-stdio owner-binding gate passed, but that narrow
  result did not establish successful natural plan construction. Root's broader
  v49 reconciliation found completed studies only for personas01/05/07.

## Implemented boundary

`compose_scientific_workflow` reuses `STEPS`, `DELIVERABLE`, and the existing
complete-plan validator. A create/edit can contain several related steps and
deliverables; finalization may accompany the last group. It does not run code,
contact model services, or admit inference. Python stages remain saved-script
references. Explicit step-ID/name upserts retain order; dependency errors remain
errors rather than an implicit scientific reorder.

Closed canonical files publish as hash-named immutable revisions through the
existing verified publisher. The existing receipt journal and instance-local
lock preserve edits across interruption; a hash compare rejects stale edits.
Exact repeated requests return their own saved revision and never roll back a
newer head. Reading only the draft directory recovers current state. Finalized
plans enter the unchanged existing launcher, which freezes actual input/helper
bytes, preserves operation identity, and remains the sole admission path.

Selected MindEval discovery now explicitly documents the already-supported
native `state.judgment.judgment` score mapping, full transcripts and config.
No scoring algorithm or scientific parser was replaced.

## Measured construction tradeoff

The source tests construct equivalent representative plans, not a guessed
reconstruction of the truncated historical program. Byte counts include the
actual retained test workspace paths and canonical JSON; they are not tokens.

| Representative plan | Largest tool arguments | Construction + launch calls |
|---|---:|---:|
| Preparation +12 native phases +saved-script analysis +report, one-shot inline | 3,671 B | 1 |
| Same15 phases via three grouped edits | 2,054 B (other edits1,124/956 B; launch376 B) | 4 |
| Six native retained MindEval records, typed helper/no custom program | 1,571 B (launch376 B) | 2 |

The grouped15-phase plan reduces peak argument size by44.0% at a cost of three
additional calls versus ideal one-shot submission; it does **not** require one
call per phase. No preflight/discovery calls are included in either count.
No measured speedup, natural-adoption improvement, or original failed payload
size is claimed. The additional typed tool schema is23,679 UTF-8 bytes under
compact JSON serialization (the existing complete study schema22,725 B);
this tool-definition context cost is explicit, not hidden as a free reduction.

Private measurement receipts under `U/composer-v50-tests.4XBBTm/workspace/`:

- `test_grouped_plan_reduces_peak0/composition-measurement.json`, SHA256
  `56193cd97385c8c9376a43c623935bc618248c25204c3cb052bed3de3954be76`.
- `test_native_mindeval_plan_need0/mindeval-composition-measurement.json`, SHA256
  `e854dd57cda831c859793d1e815b1290bbecdece7641c84a4a2a7445be1076f3`.

`U` denotes the operator's protected unattended-study evidence root; these
portable notes contain no conversations, tokens or hidden transcripts.

## Gates

Source regressions cover exact shared schemas; grouped create/upsert/remove;
stale/invalid edits; immutable historical replay; two interruption boundaries;
tamper rejection; missing files and dependency order; process-separated stdio
composition; unchanged idempotent admission, input freezing and CPU completion.
The combined core/workflow/execution/receipts/configuration/MindEval suites pass
165 tests in35.51 seconds. Ruff, Node syntax and whitespace checks pass. The
private JUnit receipt is `U/composer-v50-tests.4XBBTm/junit.xml`.

The committed `scripts/qualification/installed_stdio_gate.cjs` now adds a real
LibreChat `processMCPEnv` + SDK test that composes one group, closes stdio,
reconnects to finish/finalize the draft, launches it once, closes again, and
verifies independent worker completion and same-owner readback. Run it
on the **new immutable image**, without source/runtime overlays, with network
disabled. The existing owner/clinical-binding negative cases remain in this
gate. Installed execution and new uncoached natural acceptance are pending;
no cloud mutation or additional natural prompt was made by this source change.
