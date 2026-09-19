# Launch versus observation wait correction

Retained scientist01 v36 conversation evidence:
`/home/tux/secure-handoff/scientific-qualification-20260918/browser-evidence/scientist-01-v36-progress-0206/messages.json`
SHA-256 `79eee68ed698ce714f429aff3c2e5951427d7869d114685de11fd01befea02b3`.
Calls `call_19d4369d51794e41bce34391` and `call_0947e36b327b4650a69ad1f3`
both used `execute_command_mcp_environment-execution` with `wait_seconds:30`
and `timeout_seconds:600`; the existing maximum10 rejected them. A separate
`read_execution` call with30 was within that tool's contract. Original evidence
has not been edited, and these rejections are not additional model inference.

## Diagnosis

The live-schema source and handlers already agreed: launch default5/max10;
observation default15/max30, with effective observation capped25 inside the
unchanged30-second MCP deadline. No wrong launch30 example was found in the
bundled skills. However, the launch tool's prose omitted its wait bounds while
the observation tool and seeded instructions recommended30; the running-job
response said "observe" without naming the tool. This is an ambiguity consistent
with cross-tool confusion, not proof of the model's internal cause.

The actual image copies
`life-science/bionemo-librechat/scientific-agent-instructions.md` to
`/app/scientific-agent-instructions.md`; `seed-workbench.js` loads that file and
registers both execution tools. Model-serving waits and scientific CLI
`--wait-seconds` are distinct contracts and were not changed.

## Scoped correction

- The launch tool and its wait field explicitly describe0–10, default5, and
  distinguish launch response wait from command timeout and later observation.
- Seeded instructions explicitly prohibit copying observation30 into launch.
- Running-job responses name `read_execution` and return a structured
  `next_observation` containing the same job ID and next offset. It does not
  launch anything automatically or change caller-selected arguments.
- Runtime and schema use the same unchanged wait constants. Invalid launch
  values still fail before creating a job or starting a process; no clamping.

Focused regression tests cover exact exposed bounds/defaults, actual handler
defaults and boundary behavior, invalid values before side effects, executable
continuation arguments, and the actual packaged/seeded instruction path.
The existing stdio reconnect/deadline tests also exercise a real26-second job.
All24 focused/existing execution tests passed with the active control-plane
Python environment (`httpx2` installed); an initial run in the LeRobot-only
environment had23 passes and one missing-`httpx2` dependency failure. That was
resolved by using the existing correct environment, not a source workaround.
Ruff E/F/I passes for the new test; no broad formatting of shared source.
This source change has not been built or deployed by this task. A later actual
client test is still required before claiming the agent no longer makes this
mistake; static consistency is not a successful natural scientist journey.
