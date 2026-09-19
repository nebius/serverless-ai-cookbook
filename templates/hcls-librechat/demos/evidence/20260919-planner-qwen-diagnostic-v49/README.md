# Qwen planner comparison: admitted, but report failed

This is **one diagnostic on the existing scientist09 v49 preview**, not release
acceptance, a default-model switch, or a new MindEval benchmark. The unchanged
scientific task was to analyze six retained consultations without simulation or
judging. Only its output root changed to `unattended-20260919-qwen-planner-r1/`.
No recovery prompt, retry, or methodological hint was supplied.

## Controlled configuration

- Client source `4bd45eaafb6112ec2cae5df253c2403d07d792c3`, image index
  `sha256:202b76200becd455cbed9a402e3b9b12d6d03f8da692f787e5a12d0471c3824f`;
  endpoint `aiendpoint-e00n4wg7d95xcytvyq`, bound by the protected deployment and
  clone receipts.
- The connected `Nebius Token Factory` catalog listed
  `Qwen/Qwen3-235B-A22B-Instruct-2507` before submission.
- A private diagnostic clone changed the original DeepSeek planner to that
  Qwen model. The 32 tools, instructions, provider, skills, recursion settings,
  8,192 output tokens and 131,072 context setting stayed unchanged. The existing
  `reasoning_effort: low` remained; no incompatibility adjustment was made.
- Only clone identifiers, display name, creation/update timestamps, and its
  model/model-parameter model ID differed. The original agent was byte-equivalent
  in the retained serialized captures before and after the experiment.
- The seeded agent was not editable through Agent Builder. A narrowly scoped
  authorized operator clone added read access for this existing user; it did not
  change the default agent, account roles, keys, limits, or endpoint configuration.
  The clone was selected through the actual UI before the one submission.

## Observed result

Conversation `f535f22b-ed2c-5aa3-a70c-911bc9f1a4b2` received its only user message
at 2026-09-19 16:06:09.269 UTC. The assistant finished at 16:06:27.943 UTC.
It used six tools: workflow discovery, workspace status, three local shell
commands, and one analysis-only durable-study admission. **There were no new
hosted scientific model calls, consultations, or judgments.** Planner and title
generation were, of course, new Token Factory calls.

Study `322e4f43-ff1b-5b50-a0c2-4ab9195915a0` was admitted at 16:06:25.149 UTC
and failed at 16:06:27.387 UTC. The planner selected six compact JSON exports
from `mindeval-study-v19/runs/`, without inspecting the available recovery
verification/full records. The installed deterministic helper correctly stopped:

```text
ValueError: MindEval requires full retained run.state/config, not a compact summary.
```

No final report, measurements, or complete transcripts were published. The six
copied compact records and failure diagnostic remain preserved. The plan also
declared `records` and `transcripts` directories as final deliverables, although
the workflow publishes declared files; execution did not reach that second
potential contract error. Do not report it as an observed publication failure.

The final chat said the study was launched and directed the user to Runs. It
did not claim the study had completed, but it did not observe its immediate
failure. Runs and the durable API exposed the failure; the engine was idle.

The original DeepSeek v49 attempt failed before durable admission while emitting
an oversized tool call. Qwen reached admission faster in this single comparison,
but **neither attempt delivered the requested scientific report**. This sample
does not establish Qwen superiority or justify a production planner switch.
Retained normal transaction metadata exposes title usage only (328 prompt,
8 completion tokens); it is not total planner usage.

## Protected evidence and limitations

All raw configuration, records, browser captures and private transport are under
`/home/tux/secure-handoff/scientific-unattended-20260919/planner-comparison-qwen09-v49/`.

| Receipt | SHA-256 |
| --- | --- |
| `prompt-proof.json` | `da46358b1296183b6abf41839661b23e15fac6196176849f5cbd52e5a43c7ff6` |
| `04-cloned-config.json` | `21da16b289477f144538e1bf2837b5a3995e26a2dfcf42e9230de93317640251` |
| `08-final-study-and-messages.json` | `a94fd2bd4ce7046f470c7ba0cee065b6f4d52731a6c1269d9e40cdf1110b9167` |
| `10-terminal-operator-capture.json` | `79b055ac28186df24ce49bd2f885e0fa8bfe1dc8efee794cda0ce2dc5e81b1a5` |
| Retained helper `diagnostic.txt` | `d64237711665a02fdbbfabb5b9ff1f3b3817285b98518a830bbe585a206edde7` |

The initial stale-session/management 401 observations and one successful
ordinary UI login are retained separately. No authentication settings or limits
were changed. Browser closure was not tested in this short failed study, and no
download success is claimed. Original failed conversations and inputs were not
rewritten or marked successful.
