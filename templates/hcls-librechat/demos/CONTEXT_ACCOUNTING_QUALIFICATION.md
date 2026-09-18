# Qualification defect: false context exhaustion

On 2026-09-18, fresh v17 scientist07 (aging) and scientist10 (recorded
robotics) conversations failed before inference with purported tool overheads
of 151,949 and 113,402 tokens. Scientist04 also produced a blank reasoning-only
answer. These are retained failed customer journeys, not capacity exclusions.

The pinned LibreChat `utils/tokenizer.ts` switches every string longer than
4,096 characters to a UTF-8-byte count, including its `createExactTokenCounter`.
This affects ordinary scientific instructions and typed JSON schemas. Deferred
discovery could therefore make valid input appear too large for the unchanged
context budget. It is not exponential `$ref` expansion: all 61 captured backend
tools normalize to 268,871 bytes in the pinned runtime.

The same offline corpus, using the actual pinned tokenizer:

| Measurement | Tokens |
| --- | ---: |
| Original runtime accounting, before its existing 1.4 tool multiplier | 210,850 |
| Whole-string o200k tokenizer, reference measurement | 59,869 |
| Bounded-chunk repair, with conservative boundary allowance | 62,819 |

The repaired count does not raise the 4 KiB tokenization-call bound or any model,
context, completion, tool-call or admission limit. It keeps Unicode surrogate
pairs intact, adds 5% plus 16 tokens per chunk boundary, and retains byte-count
fallback when the tokenizer is unavailable or fails. All captured schema counts
cover the whole-tokenizer reference. Measuring both paths for the complete
corpus took 57 ms in one local check; this is diagnostic CPU evidence, not a
customer latency benchmark. The tokenizer is a local estimate, not the GLM
provider's authoritative bill. Existing provider calibration remains unchanged.

Separate fixes include dynamically exposing caller-authorized model tools while
keeping their schemas deferred, explicitly registering existing MindEval and
clinical-workflow tools on the general agent, and marking reasoning/tool-only
final responses visibly unfinished. No typed contract was replaced by an opaque
generic argument, and existing inference is never retried automatically.

GLM-5.3 reasoning is mandatory according to the official
[thinking documentation](https://docs.z.ai/guides/capabilities/thinking-mode).
Its [API supports low/high/max effort](https://docs.z.ai/api-reference/llm/chat-completion).
A live Nebius contract probe accepted `reasoning_effort: low` with the same
8,192-token completion budget. Both variants returned a visible answer on the
small probe (default 47 reasoning tokens, low 11); this does not establish a
scientific-workflow quality improvement. Deployment selection remains explicit.

Private evidence: `secure-handoff/scientific-qualification-20260918/browser-evidence/`
contains the original scientist04/07/09/10 v17 transcripts, pinned schema audits,
and the reasoning probe. Full provider reasoning is private and not reproduced
here. Fresh real workflows, actual output downloads and human-visible recovery
are still required before a release can be considered usable.
