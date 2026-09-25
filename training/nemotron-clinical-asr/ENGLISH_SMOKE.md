# English recipe GPU smoke — September 25, 2026

The public `cloud-run --model-family english_specialist` path completed on a
new preemptible H200 Serverless Job in eu-north2. This validates the documented
training pipeline, **not a clinically useful model or a serving release**.

## Exact tested identity

| Item | Value |
| --- | --- |
| Source commit | `710e5cb3d93abaa88e6934e970a7d0fbe0744da6` |
| Tested image digest | `sha256:aa48ec382005e62b50353db3f94a6bee554e463499100a4c4fae247db59c6637` |
| Run ID | `public-english-recipe-smoke-20260925-r1` |
| Foundation | `nvidia/nemotron-speech-streaming-en-0.6b@ebe59e5a817142986528bbbee5dba8db7b38ed50` |
| Export SHA-256 | `b15dd1994e8e430193b21c3946afa53a66a98bd6aba344a314a28d3e5025c58c` |

The digest identifies the tested private-registry build; it is not a public
download promise. Build and push the pinned source to your own registry using
the README. Later documentation-only commits do not change this tested identity.

The admitted Job specification matched the immutable image and arguments.
Actual installed-image code matched the source, and 105 offline tests passed
against that image. This is not independent attestation of the cloud host.

## What ran

The fixture used six public simulated examinations from the CC0 source listed
in [data/SOURCES.md](data/SOURCES.md): four training conversations (`GAS0007`,
`RES0029`, `RES0091`, `RES0142`) and two development conversations (`CAR0004`,
`RES0203`). Alignment produced 285 training and 167 development clips. An
independent audit checked all 452 clips against original PCM and reference text.
No final-test data was opened. This small smoke used no general-speech replay.

The Job ran 20 optimizer steps, learning rate `0.00003`, batch duration 120s,
accumulation 1, seed `20260926`, validation at step 20 and checkpoint snapshots
disabled. Full development validation selected step 20. The real 2,473,031,680-byte
`.nemo` export was reloaded for the wrapper's first 12 development clips and
compared with the original English foundation using native streaming inference.
Native text fragments were concatenated without inserting artificial spaces.
The baseline's one blank hypothesis was retained rather than dropped.

Publication completed at 15:58 UTC. Independent full downloads verified all
497 published objects (2,537,541,871 bytes). The exact temporary GPU VM and
scratch disk were confirmed absent at 16:00 UTC; durable output remained saved.

## Limits

This is a functional smoke, not evidence of medical accuracy improvement,
general-speech preservation, speaker accuracy, latency or cost at production
load. The 12 inference clips cover only one conversation; their uncertainty
estimates are not useful generalization evidence. No human listening or clinical
review was performed. No HTTP endpoint, MCP client, browser microphone or
Sortformer integration was qualified by this Job.

The image is configured as user `10001:10001`, and its local default-user
process was checked. Actual cloud-process UID was not observed; a read-only SSH
probe was unavailable. Do not describe this as cloud UID attestation.

Retained audit SHA-256:
`2fa672722e8a9ee02fd68138a3e9c97ee6275e03f21802d0e7de49fdbb0c0ce7`.
Cleanup-binding receipt SHA-256:
`a6854e7ab700e9647884eebdf5f10f8179051e048c1d55eb00b030a46506d601`.
These identify retained operator evidence, not publicly hosted audit downloads.
