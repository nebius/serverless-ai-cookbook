# Dedicated-user migration: exact local v50 mechanics

This is a local retained-backup import/seed/login test, **not a cloud migration,
fresh cutover capture, planner qualification, or customer-ready claim**. Rene's
original endpoint was not changed or read by this test. Each user still has a
separate LibreChat instance; an intentionally shared tenant bucket does not
imply shared-instance multiuser support.

## Identity and results

- Frozen source: `6e1ef6858b899c58955b5927522b8eace12c8f30`.
- Image: `lc:r0919-v50-6e1ef68`, OCI index
  `sha256:c8c3e411599a42afe6d00dcc4be573f8d72322616f09a86c0e881fb2fb2ef3dd`.
- amd64 manifest:
  `sha256:4aab9f4dae34afc66d502f79e7c4ff91069bb180483a074826c44422212956f1`.
- Import used the retained strict-BSON original backup and protected environment,
  with network disabled, no published ports, and independent local data,
  uploads and workspace. The container is stopped; data and receipts remain.

The empty-candidate import and readback preserve 49 collections, 81 documents,
334 index definitions and two state files. Before local login, customer records,
password and private encryption/upload state compare exactly with the backup.
Actual local HTTP login returns200, the original conversation and two messages
are read back unchanged, and login leaves the customer user/password hash intact.
There were no original uploaded files or custom agents in this real backup;
do not claim those unexercised continuity cases passed.

All eight original agents are known bundled seeds. Their original IDs,
creation timestamps and version histories remain intact. Six workbench agents
receive the new composer allowance/guidance and retain the explicitly configured
DeepSeek-V4-Pro-0813,8192 output/131072 context/low reasoning. The two existing
demo agents use their unchanged bundle's Qwen235B/8192 settings. This records
configuration only: neither planner nor any scientific model was invoked.

## Preserved negative and limitations

The first extra seed-delta probe listed only the six workbench IDs and therefore
misclassified the known clinical demo seed as an unrelated customer agent. Its
failure and complete private diff are retained. The corrected probe enumerates
the exact additional two IDs from installed `demos/seed.cjs`, whose source is
unchanged from v49; it does not waive arbitrary agent mutations.

Startup uses the previously declared exact-URL GET `/v1/models` response replay
because the local container has network `none`. This qualification-only preload
does not replace runtime/seed code, mock inference, or establish current provider
availability. The separate installed-stdio gate had no such preload or overlays.
The stock startup, user-seed, renderer, study worker/engine and BSON migration
mechanisms are unchanged from v49; the seed/schema/module additions were checked
against the actual v50 installation and database.

Seven prepare-only binding tests pass. The new private migration helper binds
the exact source/digest, preserves the original endpoint/bucket/secret references
and hold/import procedure, and produces a **nonexecuted** candidate command.
Only candidate name/image differ from the earlier prepared argv. Cloud creation,
import, activation and predecessor stopping remain separately approved actions.
A fresh original-state/activity capture and actual cloud login/chat/bucket/client
gate are required before cutover. Final default planner selection remains with
the release owner and is not determined by these local checks.

## Protected evidence

Root: `U/rene-replacement/`, where U is the private unattended-study evidence root.

- Aggregate `v50-local-acceptance.json`, SHA256
  `6a5f03629a7422244418845187f54c4873c243c9f4dd466e9bf165e35f50727f`.
- Local receipts: `local-v50-20260919T160931354670Z/`.
- Unexecuted candidate plan: `prepared-20260919T161252831666Z/plan.json`.
- Original negative: local `seed-delta-v50.json`; corrected explicit-eight-ID
  check: `seed-delta-v50-r2.json`.

No password, archive, token, encrypted credential, conversation or private
command is committed here. Cloud mutations0; hosted model calls0.
