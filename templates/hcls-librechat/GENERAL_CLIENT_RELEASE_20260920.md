# General Scientific AI client — release candidate

Status: **implemented, built, UI-tested and published; live upgrade pending**.
This is not an all-model or customer-readiness verdict.

## Source and artifact

- Base: canonical fork main `f1183f0` (v61 workbench, public skills, ClawBio).
- Runtime source: `8729de7`; subsequent commits change tests/evidence only.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:general-20260920-8729de7`.
- Registry digest: `sha256:dc044a464cd6c57112a6a6af4c81b9a9e753fde124fd18476079c24eebde7578`.
- Local image ID: `sha256:bb776c6d91667375f32d942bbd9d8cc23f85e0e9b8a33e750291e63b73e42173`.
- Platform: linux/amd64. Full existing Dockerfile; no runtime credentials baked in.

## Changes

Removed the retired LongevityHack dedicated models, provider, region endpoint and
deployment flag. Even an old environment value of `true` cannot reactivate them.
Removed event destination/date copy from the general MindEval UI and seeded
instructions. Conversation Evaluation retains its saved agent ID, tool/API paths,
existing conversations and reports; those compatibility identifiers are not
event-specific model deployments. Historical event evidence remains in Git.

Added a home-page workspace tour and a Getting started tab with six copyable
prompts, explicit inputs/deliverables, authorized catalog checks, bucket examples,
file-upload guidance, progress/recovery instructions and a link to portable skills.
The five inference examples use OpenFold2, GenMol, English speech, PhenoAge and
SAM 2; the tour submits no inference. The UI does not assert every key can access
those Apps. [GETTING_STARTED.md](GETTING_STARTED.md) is the user-facing guide.

## Verification

Exact candidate ran in isolated local container `fs2-general-client-20260920-r1`,
bound only to 127.0.0.1:13098. Synthetic login; no customer key, provider key,
tenant mount, production chat database or GPU model operation used.

- 35 Python configuration/onboarding/deployment tests passed.
- 77 installed-image Node tests passed; one retained-private-trace replay was
  skipped because the historical trace was not mounted. Includes Runs, file
  download links, scoped file handling, durable study observation, tool dispatch,
  strict workflow validation and result/completion presentation.
- Actual LibreChat skill loader: 79 skills, 65 supporting resources, 57 core file
  hashes verified. Includes the pinned ClawBio selection; this is loader evidence,
  not qualification of all ClawBio workflows.
- Two consecutive unchanged-image browser onboarding cohorts passed: six distinct
  prompt copies, model preservation, sample-prefix navigation, reload, desktop
  and 390-pixel mobile layout, and zero chat/inference submissions.
- Existing six research cards, provider selector and two missing-provider-key
  dialogs passed the actual browser UI-only suite. Missing keys disable sending;
  no external-provider inference is claimed. Zero browser console errors/warnings.
- Production browser build passed. Existing upstream vm-browserify eval and
  bundle-size build warnings remain; neither was relabeled as a clean build log.

Retained test corrections: the host lacked TypeScript, so Node integration ran
with the actual image dependencies. An old Runs mock omitted the real display
helper and was fixed to execute it. The browser CLI sandbox lacks a global URL
constructor, so URL parsing moved to the browser context. The older smoke suite
assumed a configured Token Factory key; it now explicitly tests the valid
missing-key state instead of waiting for a disabled Send button. Workflow factory
tests initially ran in the wrong source/installed modes; the final run uses
`SCIENTIFIC_VALIDATION_INSTALLED=1` and the shipped MCP/Python runtime.

## Deployment decision still required

Two separate live lanes were found: Rene's personal endpoint
`aiendpoint-e00nkx6mf6qwvwsfkp` and the actively developed recording client.
The user was asked which should receive this upgrade. Neither was modified.
No customer grant, bucket, quota, GPU pool, backend image or model placement was
changed. The stable deployment default remains the previous release until the
selected live target is qualified; an explicit `IMAGE` selects this candidate.

The installed Serverless endpoint CLI has no in-place image update. Do not
delete/recreate an endpoint to replace its image: preserve MongoDB, encryption
state, uploads and job records, retain the original bucket/key binding and stop
the predecessor study supervisor before enabling a same-user replacement.
Existing migration tooling and the user's live target decision must drive that
step. The personal predecessor observed here uses image tag `lc:r0918-cb13e8c`;
capture its current digest/configuration again immediately before rollout.

After deployment: verify login, real authorized Apps, bucket read/write, each
advertised getting-started model example to terminal semantic output and real
downloads, reconnect without duplicate submission, and the exact final client
identity. Test grants/limits must match the intended customer. Historical starter
pack or model acceptance does not replace those client tests. Only then update
`scripts/release-image.sh` and claim the corresponding customer-ready scope.

## Reproduce the UI checks

Run the existing `scripts/getting-started-browser.js` and `scripts/browser-smoke.js`
through `playwright-cli run-code --filename` in an authenticated candidate session.
They prepare/copy prompts but never send model requests. Screenshots are written
under `output/playwright/`; no real credentials belong in those artifacts.
