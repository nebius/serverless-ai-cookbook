# Dedicated-user study binding across the actual MCP stdio transport

The v48 scientist01 natural turn rejected whole-study admission with the
stop-first deployment message despite the API/supervisor being configured.
The rendered `environment-execution.env` omitted the owner mode and stable
dedicated-user identity. LibreChat's stdio SDK inherits only its small default
environment, not the API process environment. This is a client configuration
defect, not a user-preflight failure, provider limit, or backend rejection.
The subsequent process-bound pipeline is retained separately; it is not durable
whole-study acceptance. No original operation was cancelled or resubmitted.

A second installed-path check found that the rendered `python3` resolved to
`/usr/bin/python3`, which lacks `jsonschema`. Earlier installed gates selected
`/opt/scientific-client/bin/python` directly and therefore did not qualify the
rendered MCP path. Those old results remain valid only for their stated direct
helper/worker scope.

## Narrow repair

The renderer now selects the existing scientific-client interpreter and forwards
existing, nonempty owner-mode/explicit-owner/seed-email bindings as `${VAR}`
references. The same applies to the three already-supported clinical provider
credential forms, because clinical preflight also runs in this filtered child.
No credential values are embedded in rendered configuration or study state.
No default owner/mode is invented, and the existing owner precedence, stop-first
gate, provider choice, timeouts, budgets, and admission behavior are unchanged.

## Evidence and remaining gate

Ten source renderer tests and all 21 existing configuration tests pass, with
Ruff and JavaScript syntax checks. The full run first exposed one stale test
assertion for the pre-v48 unqualified native/batch-only instruction; that
assertion now verifies the already-installed qualified whole-study instruction.
No seed or instruction behavior changed in this repair. The executable acceptance fixture is
`scripts/qualification/installed_stdio_gate.cjs`. It uses installed LibreChat
`processMCPEnv` and the actual installed SDK `StdioClientTransport`, not a
reimplemented environment or a direct Python admission shortcut.

The source-renderer gate on immutable v48 runtime
`sha256:d5a104dc2baaf44257bbd718b10bde093dfc6fe2108215511b5f18c9f0a7448a`
passes ten cases:

- Reproduces the old omission while the parent is fully configured.
- Admits and idempotently reuses CPU studies for email/first-instance and explicit
  owner/stopped-predecessor configurations; the latter also has a different email.
- Closes MCP, runs the independent supervisor to completion, confirms its owner
  namespace matches the API observer, reconnects and verifies all final hashes.
- Rejects absent/invalid owner mode and absent owner identity.
- Rejects clinical admission without provider configuration; accepts each of the
  three existing credential forms into a queued state without starting a worker
  or making a provider call.

All containers use `--network none`. This is an integration gate, not a natural
scientist result or a model-quality claim. The optional renderer argument marks
the source gate explicitly; it never replaces installed runtime helpers.
Protected receipt `U/workbench-v49-source/stdio-source-gate-r2.json` has SHA256
`54e2b719e16ee4a2e950003739bd0d9fbe0091198cb801c2531e64c7303055e6`.
The original v48 system-interpreter negative is retained alongside it.

Before release, rerun without the optional renderer argument against the exact
new immutable image. Mount this committed test fixture read-only and a private
receipt directory; do not overlay the installed renderer or runtime helpers.
Then qualify natural whole-study submission through the actual authenticated
LibreChat instance. Neither image nor natural-client acceptance is inherited
from this pre-build source gate.
