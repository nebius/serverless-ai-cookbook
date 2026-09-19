# Workflow input-validation diagnostics — source candidate

The original private v60 scientist04 attempt remains a no-admission failure.
Its three composer errors omitted a presentation title and exposed only a generic
schema rejection. Report-title defaults were fixed separately in `62259c5`.
This change addresses actionable errors for genuinely invalid workflow inputs;
it does not change required scientific fields or repair submitted plans.

## Scope

The exact `MCP.js` factory attaches one formatter only to
`compose_scientific_workflow_mcp_environment-execution` and
`run_scientific_workflow_mcp_environment-execution` from the exact
`environment-execution` server. The pinned tool's original `call()` runs first.
After an input-parsing exception, the installed `@cfworker/json-schema` validator
identifies invalid fields. Matching existing kind/method alternatives are used
only to select diagnostics, never to change validation or execute a handler.

The same exception object/type is rethrown. Messages contain at most six
schema-owned field paths/constraints and fewer than 1,024 characters, without
submitted values, unknown property names, or unrelated `oneOf` failures.
Unrelated tools, valid calls, handler errors, budgets, and admission behavior are
unchanged. No dependencies, retries, model calls, or cloud changes were added.

## Focused evidence

Fourteen distinct tests pass, zero skips, in a network-disabled CPU container
using exact v60 image index
`sha256:6d764aca3237cec1ccd234690a191ad89247e08d3f60b7b1f4f1722a6a414dca`.

- The pinned installed factory constructor/attachment region creates the real
  LangChain tool; a real MCP SDK stdio client talks to the execution server.
- All three complete retained rejected payloads report the exact missing title
  path, with **zero handler/SDK dispatches**. Their historical public schema is
  retained as `test-fixtures/workflow-composer-v60-schema.json`, extracted from
  that immutable image. The fixture contains no user payloads.
- Invalid `num_sequences` bounds/type, unknown method, multiple errors, nested
  file references, and tool-call envelopes remain rejected before dispatch.
- Tests preserve the original exception identity and submitted arguments;
  unrelated tools/servers and handler exceptions remain unchanged.
- Valid composer/finalize/admission calls retain byte-identical SDK responses.
  Same-plan replays keep the original study ID and explicit replay flags.

The same fourteen tests also pass against read-only candidate Python source,
including the separate optional report-title change. This is **source-candidate
evidence**, not a successor-image or live UI qualification: candidate mode inserts
the reviewed factory hook in memory. It evaluates only the exact constructor
region, not the entire application service with its unrelated dependencies.
`SCIENTIFIC_VALIDATION_INSTALLED=1` instead requires the actual installed helper
and already-patched `MCP.js`, without applying a runtime patch.

Protected evidence under the established unattended handoff root:

| Evidence | SHA256 |
| --- | --- |
| `workflow-validation-source-r5.log` — installed Python, 14 pass | `acb156900a4cea9c4183c9e48cf84cea2b400446a34d3b4ec2f3a4ccff64b3fb` |
| `workflow-validation-source-current-r1.log` — candidate Python, 14 pass | `0ae7296314baf3e75cb13f93e296174d353d47e7cea3238a05a00c01b3356311` |
| Historical public schema fixture | `d02acc41c8af326fb5c52e796715c858f20dc0ac5bf1b81e5c3c71efa86aa3ef` |
| Original private04 messages | `a3d4c05a33624799e5c4398111b191c8962b88b3c74b553469cbbca0e653420d` |
| Original terminal close receipt | `68fefa3a2457bb681c32a7501cfa7b0fe89e826a174078f0bb63dcf705eee8b3` |

Early test-only attempts remain retained: r1/r2 omitted the required report
deliverable from the valid CPU fixture; r3 incorrectly compared first admission
flags with replay flags. Those assertions were corrected without changing runtime
behavior. No failed live attempt was repaired or resubmitted.

## Successor installed gate

Mount `test-scientific-workflow-validation.cjs` and its sibling `test-fixtures/`
read-only. Set `SCIENTIFIC_VALIDATION_INSTALLED=1` and
`SCIENTIFIC_VALIDATION_RETAINED_MESSAGES` to the unchanged protected private04
messages file; run the test with the image's Node in a network-disabled container
and fresh `/workspace` tmpfs. Leave `SCIENTIFIC_VALIDATION_PYTHON_ROOT` unset.
Require all fourteen tests, no skips. Hash the actual installed
`/app/api/server/services/MCP.js` and
`/opt/hcls-librechat/scientific-workflow-validation.cjs`, plus the source-bound
`patch-server.mjs`. Image build/deployment and live qualification remain pending.
