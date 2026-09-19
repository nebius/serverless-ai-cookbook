# Recorded LeRobot public API acceptance — release 179

Status: **data/media integrity passes; natural client completion and physical
augmentation suitability are not qualified.** One explicitly scripted API/MCP
cohort, not an emulated scientist or a successful v41 browser workflow.

The Serverless creation failure still blocks the frozen v41 natural prompt.
This separate test uses the same scientist10 principal/key, unchanged max1
concurrency, the immutable v41 helper image, and the actual recorded ALOHA
coffee source. No model/provider/limits were changed and no failed historical
journey was erased.

## Exact request and results

- Parent operation: `3e529cf5-f399-497e-8ec1-2c50f89d2c87`.
- Original source archive: 1,986,457 bytes,
  SHA256 `1721d4018c0e38390695059a8cab79d23f679d70b3bdc878d509c9f68bef7be7`.
- Source: two recorded 64-frame episodes, 25 FPS, 640×480, two cameras,
  recorded actions/state/effort and timestamps. No synthetic demonstration.
- Whole-sequence edge transfer on the high camera only; wrist unchanged.
  One variant, seed20260919,35steps, guidance6; prior frozen supported transfer
  controls reused. This is **not** prefix-conditioned video continuation.
- Result archive: 2,552,670 bytes,
  SHA256 `c34885d8e4e31c797ce5d13c808fe5f062133cd3894f0593e8c5c128caa390f5`.
- Publicly admitted children:
  `1af8e6c4-686f-4958-a677-a9b28ce1f1f4` and
  `fc6991ca-7e38-48d1-ba76-db5f64c57df7`.
- Published helper image index:
  `ae862cd01b16462961f7a5b1baab5eeaf5d211d561a43578ede2cc4a796bed12`,
  source1b15d5d. The helper ran in a local container against the public API;
  this does not establish deployed Object Storage mount behavior.

## Independent checks

The returned archive was size/hash checked, safely extracted and reopened with
the actual LeRobot0.6.1 reader. All128 rows and6144 non-video values match
exactly, including dtype: action, state, effort, timestamp, episode/frame/index,
task_index and next.done. Both episode timestamp intervals match.

The untouched wrist MP4 is **byte-identical**, SHA256
`51bae67eb87e3ee61f631720de6970406ecb9ce485cdfd31402cc1f6ec99ac24`.
All128 decoded wrist frames match pixel for pixel, with zero maximum error.
Ten per-episode wrist-stat fields match exactly. The aggregated stats match
except a measured3.4877e-9 standard-deviation rounding difference; this is
reported, not called bit-identical aggregate metadata.

Both selected episodes return64 frames at640×480 and25 FPS. The two native
child MP4s were separately downloaded through the existing authenticated
streaming/hash-verifying helper and fully decoded with FFmpeg: each64frames,
2.56seconds, H.264. Packaging produces128-frame/5.12second AV1 shards with
correct per-episode offsets; no hidden geometry/FPS change was found.

The first verifier mislabeled uint8 RGB differences as normalized values.
Its original receipt remains; corrected `independent-validation-v2.json`
asserts dtype uint8/range0–255, preserves the same numbers, and also records
all-pixel RGB moments and their difference from writer statistics. Reader
values are not called luminance. Corrected receipt SHA256:
`e2444f75ee55a4f5fed9f2b55e864131026605f3b03c02280a30bdc8d4079718`.

## Timing and runtime attribution

| Measurement | Seconds |
| --- | ---: |
| Helper start through both verified downloads | 226.852 |
| Parent accepted to terminal publication | 187.442 |
| Episode0 accepted to ready, including admission/activation | 58.598 |
| Episode0 started to completed service interval | 36.359 |
| Episode1 accepted to ready | 1.177 |
| Episode1 started to completed service interval | 35.086 |

Do not sum the parent and child intervals as independent GPU use, and do not
call the generic parent running interval GPU compute. Both child operations
attribute to the same1GPU preemptible Pod
`7a744583-f8b8-47b8-9f17-5cd03c3afbce`; this cohort is not a multi-Pod witness.
Independent operator-side witnesses confirm the actual same GPU Pod's native
image `5e2680aa1f8332413638ec1bc962c3796a79a314c1c84f5456d32aa916839e32`,
zero container restarts, and04:05:04.707392 log event
`serving_snapshot_runtime` with mechanism`cuda-criu-restored`. The active
owner cache policy is`Require`, with CUDA checkpoint bundle
`573bf6acacb90461ca0cc06f850f550dc48e34579d79f866da2b1691097ff120`.
The legacy fastStart.level=Off field is not substituted for actual cache policy.

Coordinator Pod`dfacf2ee-cd87-4165-a0d8-bed50e01643b` is observed during the
run with actual imageID
`69fe161d370fac4cc9517d24ecfee7b025bb569a935ffadab8eb31e49c783a11`,
zero restarts, and the179 collector. Public terminal result binds that exact
image, attempt and Pod. Minute observations at04:03:59/04:04:59/04:05:59 and
`Q/robotics-api-r179/cosmos-runtime-logs.json` preserve the witnesses. The GPU
Pod subsequently scaled to zero normally; absence from the after-capture is
not an execution failure. Timing alone is not used to infer snapshot restore.

## Scientific limits remain

All selected frames changed; RGB mean absolute differences are32.029/34.911
on0–255 values. These are image-change measures, not geometric fidelity scores.
Direct inspection at episode0/frame32 shows broadly similar arm placement,
but changed surface textures, edge details and white table markers rendered
green. Consequently **lighting-only changes, unchanged physical geometry,
correct visual-action alignment and policy-training validity are not proven**.
Whole-sequence conditioning is operational, not a guarantee of the requested
scientific invariance. Source/output RGB averages do not establish successful
cooler-lighting compliance either.

Protected complete evidence:
`Q/browser-evidence/scientist-10-scripted-lerobot-r179/` (Q is the campaign
secure-handoff directory). Includes original request, finalized input and
output manifests, public events/status, child IDs/results, raw MP4s, original
and corrected independent checks, frame inspection, and all source hashes.
Verifier source SHA256:
`4af8156dcb9c06dbfccc86eee01d6c3400a916822ac7b0ae9b0cc0120e472f21`.
The natural LibreChat/v41 acceptance remains separately blocked/unperformed.
