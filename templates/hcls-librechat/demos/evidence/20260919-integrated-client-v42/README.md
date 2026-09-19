# Integrated client v42 — immutable handoff

As of 19 September 2026, 04:45 UTC. Installed-image qualification is complete;
deployment and natural customer acceptance are **not** implied.

## Exact release

- Source: `7674a107eeeb2fce5782030c872adad91e966add`
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v42-7674a10`
- Index: `sha256:ffc003193e5e26886ad1c5f3278b2e6a07e6c1dd51234131c8da901b0256fc81`
- amd64: `sha256:c024118c6b9a8d5d1972d871dd011e34bb9e81c249408921f0e0f1f86b0e185b`

Built from the committed Git archive, not the shared dirty working tree. The
official skills input is pinned to `292c7e65a46d0c29994d2babfc19da129d16fa62`.
Registry digest and local pull were verified. This combines v41 exact-tool
discovery and streaming downloads with bounded operation-deadline handling,
clinical no-facts UX, deterministic clinical reports, and truthful Runs timing
labels. No model, provider, token, round, concurrency, or timeout limit changed.

## Installed-image gates

Fourteen installed runtime files match their exact committed bytes. Tests use
the actual installed runtime, not mounted replacements:

- 29 service/operation-deadline tests and four pinned ToolSearch tests pass.
- Three clinical no-facts behavior tests pass; installed worker outcome
  constants are checked separately at their real container location.
- Five retained clinical WER/source-selection reports regenerate both JSON
  and Markdown byte-for-byte using the installed reporting helper.
- Compiled client includes `Workflow active` and accepted-to-ready labels.
- Installed packages: MCP2.2.0, httpx2 2.12.0, NumPy2.2.6,
  RDKit2025.3.6, h5py3.13.0.

Prebuild gates additionally passed42 Node,82 Python and seven NumPy-export
tests. Initial commands using environments without TypeScript/NumPy are
retained as harness errors. The first installed test attempt incorrectly
assumed the source-tree worker path inside the image; three behavioral tests
already passed, but a static-path assertion failed. The second attempt checks
the actual installed path, without changing product source or the image.

Protected receipts (`Q` is the campaign secure-handoff directory):

- `Q/workbench-v42-build.json`
- `Q/browser-evidence/workbench-v42-installed/` (first harness-path failure)
- `Q/browser-evidence/workbench-v42-installed-r2/summary.json`
- `Q/browser-evidence/qualify-v42-installed.py`

These checks submitted no inference and changed no endpoints. A separate
fresh-image read-only recovery of an already completed real LeRobot bundle is
pending the backend180 rollout settling; it must be attributed separately.

## Controlled deployment handoff

The existing supported helper is
`templates/hcls-librechat/demos/deploy-scientist-workbenches.py`.
Parent/root owns any Create action. Use the protected campaign manifest and
`--source-deployments` pointing at `workbenches-v39-deepseek0813`; the helper
checks scientist, tenant, principal, project, email, bucket and existing secret
identity before reuse. It must not create replacement credentials.

Intended scientist10 settings are unchanged: DeepSeek-V4-Pro-0813,
131072 context,8192 output,low reasoning, original per-key concurrency. Use
the verified immutable tag because this Serverless version derives an invalid
label length from a full digest string. Record the tag-to-digest check.

Reconcile the exact proposed name
`science-qualification-v42-deepseek0813-scientist-10` before and after a single
Create. Never clear `creating_endpoint` state to retry. On timeout or error,
save provider request/trace IDs and inspect exact-name matches: one matching
image can resume readiness checks; zero means stop and retain the failure;
multiple/different-image matches need explicit resolution. A new release
attempt is not permission for a retry loop or quota increase.

Keep working v39 `aiendpoint-e00hq3500nvwc43nm7`, its chats and original bucket
unchanged. Rollback is to continue using that existing endpoint, not to mutate
its VM or overwrite its image. No extra deletion is authorized by this note.
Rene's production endpoint is outside this operation.

## Still-open customer gate

The original v39 third recovery produced valid native and LeRobot inference,
but only a partial report, a zero-byte provenance file, and incorrect
float32-accumulated numerical claims. Its two observation errors and manual
operator-only artifact verification remain distinct from a natural customer
pass. See the adjacent operation-wait-boundary and persona-experience reports.
The existing deterministic export helper works; the natural agent failed to
use it. Do not describe this image's unit/recovery gates as closing that
scientific delivery problem.
