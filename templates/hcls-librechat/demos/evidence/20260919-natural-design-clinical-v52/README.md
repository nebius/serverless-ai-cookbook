# Natural design and clinical v52: preserved failures

These are two separate dedicated-user LibreChat instances, each receiving one
unchanged frozen r6 research prompt without technical coaching or follow-up.
Planner: explicitly selected Kimi-K3, low reasoning, 131072 context and 8192
output tokens; no changed budgets. Client source
`e4005cea9e8dd4429064104a53861e8a877016a9`, image index
`sha256:0c2a60ea79d3a2ff27c3927964ad5ddb95b02c7f21d94a86990b40200a29f182`.
The original cohort used the release-bound backend189. Later source repairs and
backend fault-recovery tests do not retroactively qualify these journeys.

## Scientist04: durable admission and disconnect, interrupted worker failed

Prompt SHA-256 `3df41ccaeaf59c54427d16b3810b39d10add96ef7c0fde09c9ad11b3d1b5efc5`;
submitted 2026-09-19 16:56:37.547097 UTC. Conversation
`b850ccdb-748d-5207-9b0e-523acf976cd2`; Study
`64212953-27a8-566c-843e-1750e6431267`.

The requested RFdiffusion48-residue design → four ProteinMPNN sequences → first
selected ESMFold2-Fast refold was represented by eight persisted phases,
including typed preparation, exact design/refold correspondence, measured
comparison and final report. The plan declared 11 final files. The observer
verified the Study was running at 16:58:32.827 and closed the actual browser at
16:58:33.674; this is genuine pre-completion disconnect evidence, not completion.

RF operation `c767ebaa-e39f-4874-a833-60a1b910238d` was admitted at
16:58:43.674937. The release owner then performed one explicitly authorized
eviction of the owned inference Pod
`582c9230-25db-47b3-a505-ddbc4e4597a6` at 17:01:34.921. The operation failed at
17:01:40.260226 with `BackoffLimitExceeded`, classified as application failure.
The observed first attempt did not recover. The authoritative accounting policy
allowed **two attempts per stage**; the public status's `max_attempts:1` was not
that policy and must not be used to claim the configured retry budget was one.

The Study failed at 0/8 phases with a generic TaskGroup ExceptionGroup. Reopening
the actual Runs UI showed this failure and the original RF operation, not a
resubmitted copy. Its two other new operations were uploads, not inference.
No final requested report or downloadable study artifacts were delivered. The
natural response had honestly reported pending work rather than completion.
No operator repaired or resumed this Study. A later separately-labelled backend
test is outside this immutable natural cohort.

Private retained evidence (`U` is the protected scientific-unattended handoff):

- `natural-v52/scientist-04/post-eviction-01/study.json`, SHA-256
  `e1402a4a1fa37a6da0f51092e390c95d33043cd8fe1abf113fa75ac980b86a4a`.
- Original operation `status.json`, SHA-256
  `b883aa257472f5374c6e262632c7bcbf2247f2d9884c4f891f20f783b03b620f`.
- `v52-owned-worker-recovery/readback-01/accounting.json`, SHA-256
  `e8c56c2fb061df0e0451584f253e5ae90ad50d0dc81f69ba12ad54d0d8f4a37e`.
- Actual reopened browser Runs snapshot, SHA-256
  `9475cea67177e14ea775f1a2c4461cb60b15b9a49a1143dd8e56c35debe285f3`.

## Scientist08: preparation only, no durable clinical Study

Prompt SHA-256 `0d3a3173d9af900ac50c67d7d3d1388108c16add6b1d2c3034a0ae6f44b3b0ac`;
submitted 17:00:41.472164 UTC. Conversation
`7ffada3a-11fb-5317-8b53-4cbd66a16efc`.

The task requested report drafts from retained full English and German
transcripts plus a short negative case, without new ASR, and exact retained WER
and source-coverage reporting. The assistant used nine preparation/discovery
tools, then ended mid-sentence. Persisted `unfinished:false` and `error:false`
do not establish that the user's task finished. Raw provider finish reason and
usage were not retained; no token-budget or hard-limit cause is asserted.

There were zero Studies, zero new clinical/model operations and no generated
clinical drafts, WER table, report or final study artifacts. The only new files
were a 3756-byte preparation script and five retained source/provenance copies.
Actual Runs reconnection showed no saved whole studies. No second user prompt
or manual technical repair was made. No final artifact downloads were possible.

Private persisted messages SHA-256:
`4d23733e5539d69e2e5837326e1e3018b0906be7684267e87a9c68dce81e793d`.
Actual Runs browser snapshot SHA-256:
`773c124245ef5f836dfcaad420aaad5da8079abfb9d3721276b35e5e6eb39881`.
The observed auth-cookie rotation and an earlier generic capture's invalid
request are retained harness defects, not new clinical provider failures.

## Read-only owner archives

Completed at approximately 17:26 UTC, with no stops, deletes, key/bucket changes
or new inference. The full r6 trees contain 96 files / 100520 bytes for04 and
6 files / 24987 bytes for08. Provider specifications, exact image/agent settings,
all chats/messages, full public operation histories, eight terminal execution
jobs per owner and durable owner registry files are retained. This is a
configuration/transcript archive, not a restorable Mongo database snapshot.
The first non-PTY SSH capture failed in the harness; the original error is
preserved and the existing tested PTY read-only helper completed the supplement.

Joined inventories under `U/v52-owner-archives/terminal-local-r2/`:

| Owner | Summary SHA-256 | Archive inventory SHA-256 |
| --- | --- | --- |
|04|`9bd0a199653dab4ef353de65875faf1ba9ef43793b98ab4ff77714b94c9a64bd`|`a48f9bf475070968a23cd32acfd1ce5a71d39b7e8532fce0313f0eb675f5c8fa`|
|08|`12435745757155f678d655d20d415d3a488aa39475f425c39072b182bcd2e716`|`2735163b75bd2fc8502eacda35dd26375897749502222eaf5907cccb15b9d623`|

The zero-active check is time-bound. Root's subsequently authorized scientist04
backend test invalidates it for retirement until that separate test is terminal.
Neither natural journey qualifies as unattended scientific delivery or clinical
readiness. The source/installed helper gates remain separately-scoped evidence.
