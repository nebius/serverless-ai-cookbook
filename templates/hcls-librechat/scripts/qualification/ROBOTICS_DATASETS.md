# Recorded ALOHA qualification inputs

These are real recorded robot observations and controls, not model-generated
imagery or fabricated action arrays. They are bounded derived clips for checking
the platform's generative-augmentation workflow, not reproduction of a robot
policy's success rate.

## Primary sources and immutable identity

- Dataset: [official LeRobot ALOHA coffee](https://huggingface.co/datasets/lerobot/aloha_static_coffee),
  revision `b144896feb1f37398a862927b22cd3abdf005a6b`, MIT.
- Paper: [Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware](https://arxiv.org/abs/2304.13705),
  Zhao et al., RSS 2023; [authors' project](https://tonyzhaozh.github.io/aloha/).
- The pinned `meta/info.json` is v3.0. The repository README contains an older
  v2.0 layout example; actual versioned metadata is the preparation authority.
- Tavily primary-source discovery request IDs:
  `94e814fd-6a17-4cc9-b287-283d9313b7e9` and
  `d16cab42-1569-465e-bb5a-12191e9effe7`.

The source contains 50 episodes, 55,000 rows and four 640×480 RGB videos at
50 FPS. The preparation script downloads only the required metadata, numeric
data and two camera shards. It checks each source size and published LFS SHA-256
where provided, recording the computed SHA-256 for every source file.

## Deliberate derivation

The hosted augmentation runtime is currently qualified only through 30 FPS and
16–400 selected frames per episode. The derived fixture therefore takes every
second original frame at 25 FPS, without interpolation:

| Derived episode | Original episode | Original frame indices | Original relative time |
|---|---|---|---|
| 0 | 0 | 200, 202, …, 326 | 4.00–6.52 s |
| 1 | 1 | 250, 252, …, 376 | 5.00–7.52 s |

Both retain `observation.images.cam_high` and
`observation.images.cam_right_wrist`, so each segment has 64 frames and two views.
Actions, 14-dimensional joint states, efforts and `next.done` values are selected
from exactly those original rows and retained at their declared dtype. Canonical
indexes and timestamps are rebased to the derived clip; all original indexes and
timestamps remain in `qualification-source-provenance.json`. The original task
description is retained, but the short segment is not labeled as completing it.
Video decoding and AV1/H.264 re-encoding may introduce compression differences;
numeric control values are not recomputed.

## Actual offline acceptance

Prepared with the already installed pinned `lerobot==0.6.1` CPU environment and
the production `fs2_lerobot_augmentation.dataset` reader/writer/helpers:

- Two episodes, 128 numeric rows, two cameras, 25 FPS, 640×480.
- All 256 camera frames fully decoded by the pinned reader.
- All 5,504 selected numeric values match the source exactly, including dtypes.
- Dataset bundle: 1,986,457 bytes, SHA-256
  `1721d4018c0e38390695059a8cab79d23f679d70b3bdc878d509c9f68bef7be7`.
- Four standalone recorded-reference MP4s exported, one per episode/camera.
- No model requests or GPU allocation during preparation.

Protected artifacts are under
`/home/tux/secure-handoff/librechat-rene-20260918/qualification-robotics-aloha-v2/`.
`preparation-receipt.json` lists all files, hashes and validation counts. Source
download cache and the first interrupted preparation are retained separately in
`qualification-robotics-aloha-v1/`. The interruption was a harness comparison of
scalar Boolean versus declared one-element shape, not changed data or a
platform/model failure; the corrected check compares identical values in their
declared shape. An initial local `datasets.py`/Hugging Face `datasets` import
name collision was corrected in the preparation script, not in the platform.

Rebuild into a new output version using `robotics_cases.py --output ... --runtime
.../lerobot-augmentation/runtime/src` with the pinned environment. Use
`--source-cache` to reuse the hash-verified source shards. The script never
overwrites an existing derived dataset.

## What the live study must assess

Check normal scoped upload, model calls, durable polling, complete result
download, pinned-reader reopen, unchanged nonvideo values, preserved frame/timing
counts and individual camera/episode selection. Compare all generated frames
with the recorded originals for requested lighting/background changes, robot
geometry and motion, grasp/contact consistency, temporal artifacts and
multi-view consistency. Preserving action arrays alone cannot establish that
the generated imagery remains physically consistent with them. No policy
retraining or robot execution is included, and no training-quality claim follows
from API success or metadata integrity.

The official UMI cup dataset was considered but its current pinned feature
schema lacks an `action` field required by the hosted runtime. Actions were not
invented to make it pass. ALOHA supplies real recorded actions instead.
