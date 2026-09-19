# Dedicated-user state migration: local v47 qualification

This is **local Mongo/import/startup/login mechanics evidence**, not a deployed
Rene upgrade or a customer-readiness claim. The original endpoint, bucket, keys,
chats and user data were not modified. Cloud replacement remains held pending
the final client/planner release decision.

## Exact scope and result

- Image source: `92047e435c9484efba58be32755ccaddde73b150`.
- Unique tag: `lc:r0919-v47-92047e4` in the existing Nebius registry.
- OCI index: `sha256:950b924fd117f4bd64f4592d9ffd6d659f240968bad858c095259724336f630e`.
- Linux/amd64 manifest: `sha256:972f98c147e33ec65bb09f50fe5773c503abc9ab36a97ad5856bd200818864a5`.
- Read-only source capture and local tests: 19 September 2026, approximately
  14:25–14:36 UTC. Task containers had network `none`, no published ports and
  separate private local data/upload/workspace directories. Original archives
  were mounted read-only. Both containers are now stopped; data is retained.

| Gate | Observed result |
| --- | --- |
| Original Mongo import | 49 collections, 81 documents, 334 index definitions and two state files; exact strict-BSON, options, index-order, identity/content and file equality |
| Stock v47 seed | Original customer records, password hash, plugin ciphertext and encryption/upload bytes unchanged; bundled agent/system seed changes recorded separately |
| Existing login | Original password verifies against imported bcrypt hash; actual HTTP login and authenticated user/conversation endpoints succeed |
| Original chat readback | One original conversation and both original messages returned with exact text/content |
| Ordinary local restart | Customer-state equality passes; same password, unchanged user record and original chat readback pass again |
| Real-Mongo typed fixture | Int32, small/large Long, integral/fractional Double, Decimal128, Binary and Date preserved; collection validator, collation and compound partial unique index enforced |
| Private-helper tests | 19 Node and 10 Python tests pass |

The local restart includes legitimate new local authentication sessions; its
comparison uses the captured post-login state. The pre-login comparison is
against the original source archive. No customer differences were discarded to
make either assertion pass. There were no original uploaded files to exercise:
the original upload directory was empty, so real upload/browser-download
continuity is still a live acceptance gate.

## Declared isolation fixture and preserved failures

The first stock-image activation failed because network isolation prevents
authenticated Token Factory discovery of the selected, non-curated
`deepseek-ai/DeepSeek-V4-Pro-0813` planner. The successful local test used a
manager-approved replay of a freshly captured authenticated **GET /v1/models**
response for that exact URL only. The mounted Node preload does not modify the
image, mock inference or permit network access. This result cannot establish
live cloud discovery, MCP/model access, bucket mounting or browser continuity.

The real tests also caught and repaired three private migration-helper issues:

1. The initial activity check incorrectly treated a workshop's terminal
   `aborted` state as active. The exact workshop terminal set is now used;
   `paused`, `takeover` and `interrupted` still block cutover. The source had no
   active operations or unfinished chats; no customer state was reset/cancelled.
2. Default Mongo/EJSON numeric promotion can erase BSON type distinctions.
   Final capture disables value promotion, and import uses `relaxed:false`.
   The stronger fresh-source and real-Mongo results supersede, but do not erase,
   the initial weaker import comparison.
3. A synthetic harness compared a BSON Int32 error code directly to a JavaScript
   Number. Validator/index enforcement was correct; the assertion now converts
   the code explicitly. Its failed attempt is retained separately.

## State-preserving cloud procedure — not executed

1. Select the final qualified client image, then verify the unique short tag's
   remote digest immediately before creating a candidate. The provider has a
   known full-reference annotation-length issue; do not assume an OCI digest
   reference will create successfully.
2. Preserve the original provider config, secret references and bucket mount.
   Take a fresh read-only strict-BSON backup with indexes/options, private
   encryption state and local files; confirm no active source work.
3. Create a **separate held candidate**, with no seed, API or study supervisor
   before import. Verify actual Serverless command parsing/held behavior.
4. Import only into an empty database and empty data/upload directories. Never
   drop, merge or overwrite a populated candidate. Verify every original
   identity/content/type/index/options/file invariant before activation.
5. Require a new, unchanged predecessor capture before activation. If the source
   changed, retain the candidate and prepare a new empty one; do not overwrite it.
6. Start the stock app with the bootstrap password seed unset, preserving the
   imported password/profile. Verify post-seed customer state, actual login,
   original browser chats/files, bucket/key access and dedicated-owner behavior.
7. Only after final image/client acceptance and source reconciliation may the
   original endpoint be stopped recoverably. Never delete it as part of this
   procedure or run two new supervisors for the same user.

Each user retains a dedicated instance. A tenant may share its bucket; this is
not a multiuser/shared-LibreChat migration.

## Evidence

Protected root:
`/home/tux/secure-handoff/scientific-unattended-20260919/rene-replacement/`.
No archive, password, token, encrypted credential, original conversation or
private command is committed here.

- Aggregate receipt: `final-evidence-20260919T1435Z/receipt.json`,
  SHA256 `7845bf33fcfcc63081a18ffa9a825e604d796685ce75889c2a3b9fa1c365f6b3`.
- Strict source archive/receipt:
  `execution-capture-source-20260919T142956154358Z/`.
- Successful local candidate: `local-v47-20260919T143150461340Z/`.
- Original isolation failure: `local-v47-20260919T142715042873Z/`.
- Real-Mongo typed/options/index test: `mongo-types-20260919T143215412205Z/`.
- Updated nonexecuted provider plan: `prepared-20260919T143501779852Z/plan.json`.

The aggregate binds each private receipt and helper by hash. The next client
image still needs its own applicable qualification; v47 evidence does not
silently qualify a successor or resolve the planner/reporting gaps.
