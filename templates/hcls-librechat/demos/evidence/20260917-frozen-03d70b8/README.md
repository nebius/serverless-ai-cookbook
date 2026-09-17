# Frozen LibreChat candidate — 17 September 2026

Source: `03d70b8`, branch `agent/librechat-scientific-branding` in
`rene-tech/serverless-ai-cookbook`. Local image
`hcls-librechat-scientific:clinical-mindeval-03d70b8`, image ID
`sha256:fb52a5c2ca63154a626072cc7461d11559d696c41d38d4a4cc61324f1e429780`.
This is a local image ID, **not** a registry manifest digest or deployed release.
Candidate container `scientific-demos-frozen-03d70b8`, localhost:13120.

## Completed checks

- Actual Scientific AI Nemotron speech Apps and global Token Factory report
  generation, not mocks. Full 421.86-second German recording completed in
  61.196 seconds; full 457.92-second English recording completed in 123.259
  seconds, including per-key queue time. These are warm-platform workflow
  measurements, not cold starts. Six primary artifacts were downloaded and
  persisted per case; the API also lists the structured `review.json` artifact.
- The original synthetic transcript job survived the upgrade. Its 0.02-second
  replay did not run inference. The original 598.09-second receipt includes a
  failed provider attempt and operator delay before Resume; it is not a model
  performance measurement. All unchanged request IDs reused their jobs.
- Native browser file upload produced completed job
  `2e326fa861cffa8f12d94efe4b6b1505` and displayed Draft ready.
- Saved **Clinical Report Draft** agent successfully called `clinical_list_jobs`
  and `clinical_read_output` to retrieve that job's `follow-up.md`, without
  creating another report. Conversation
  `e7616135-6a32-53fa-8a6c-9d584262b73e` remains in the isolated test instance.
- Frozen browser create-run selection survived refresh, then abort succeeded:
  `9f05439a-1e9a-451f-87db-ddc7ec2362d1`. Earlier direct intervention and recorded
  CSV checks are recorded in the parent evidence README. No test run is left
  paused waiting for a human turn.

## Local migration rehearsal

The r3 candidate's Mongo process was shut down cleanly (exit 0, 08:41:38 UTC),
then the container was stopped. Its `/data`, `/app/uploads` and `/workspace`
were copied into a protected local test directory and mounted into the frozen
candidate. This was an offline, same-Mongo-version copy, **not copying live
database files** and not a backup of production.

Before/after database counts matched: 2 users, 1 conversation, 2 messages and
1 encrypted plugin credential. The same user ID and password worked. The demo
reported a configured key before any new credential write; an authenticated
workshop catalog call succeeded, verifying decryption. The old completed
clinical report remained readable. Subsequent tests added new chat/messages
and jobs after this comparison.

Operator-only recovery directory:
`/home/tux/secure-handoff/librechat-migration-test-d5xext` (not in Git).
Browser authentication state is also outside Git. The stopped r3 container
and the live production endpoint have not been deleted.

## Not yet qualified / release gates

- Production LibreChat still runs its previous image and URL. The owner must
  choose a replacement URL with rollback or a coordinated same-URL cutover.
  Existing Serverless CLI has no in-place image update; ordinary endpoint SSH
  has no authorized key. Obtain legitimate backup access before production
  migration; do not discard accounts, encryption keys, chats or files.
- Gateway's eight-clinician candidate is not deployed. The 40/40 direct
  qualification run is separate from final public API and multi-team client
  acceptance. Do not infer full-workshop readiness from this evidence.
- Reports remain clinician-reviewed drafts. The verifier can reject valid
  facts or accept incorrect ones. Negative prompt experiments were reverted;
  this evidence does not establish medical accuracy or clinical safety.
- Ordinary chat audio attachments do not automatically enter the workflow;
  use the native panel's upload. Latest-200-run history and the old shared
  root workbench limitations remain documented in the implementation README.
- Private Sword event artifact is still missing; Sword production was not used.
