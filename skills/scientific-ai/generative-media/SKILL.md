---
name: generative-media
description: Generate SDXL images, Wan2.2 text/image-conditioned video, or Cosmos video and LeRobot augmentation through hosted model contracts, preserving mode selection and verified artifacts.
license: Apache-2.0 AND CC-BY-4.0
---

# generative media (native)

Shared rules: `scientific-gateway`.

## Wan2.2 and separate Cosmos variants

`wan2-2-t2v-nim` and `wan2-2-i2v-nim` are independent Apps, not modes of
Cosmos. Inspect the exact App schema. Current adapter uses `prompt`, `seconds`,
`size`, `seed`, `steps` and `cfg_scale`; i2v additionally requires
`input_reference` in its published image format. Prepare any data URL from
actual image bytes in a local input JSON outside chat. Do not add a model field
or copy Cosmos `num_frames`/`num_inference_steps` into Wan. Preserve the source
image, verify returned MP4 dimensions, decoded frames/FPS and duration, and
report runtime versus total observed latency separately.

Only use `cosmos-transfer2-5-2b` or another Cosmos variant if this user's live
catalog exposes it. Its presence in source or a vendor catalog does not mean
public access. A different checkpoint/control interface is a distinct App; do
not silently replace `cosmos3-nano` or promise interchangeable controls.

## sdxl (typed tool `generate_image_native`)

Text-to-image: `prompt` (required), optional `negative_prompt`, `seed`,
`steps` (default 20), `guidance`/`guidance_scale`, `width`/`height`,
`response_format`. Call `get_model_schema` for live bounds. Result: image
artifact — download it per the shared manual; do not inline base64 into chat.

## cosmos3-nano (typed tool `cosmos3_nano_generate_media_native`)

Media generation: `mode` (required, e.g. `"text-to-video"`), `prompt`
(required), `size`, `num_frames`, `fps`, `num_inference_steps`, `seed`,
`negative_prompt`, `output_format` per the live schema.

```json
{
  "mode": "text-to-video",
  "prompt": "A red cube on a white table",
  "size": "448x256",
  "num_frames": 25,
  "fps": 24,
  "num_inference_steps": 30,
  "seed": 1
}
```

## Match the control mode to the scientific goal

For a new imagined clip, use a supported text/image generation mode. For
continuing a prefix or suffix, `video-to-video` is appropriate: it conditions
only selected latent frames, then generates the rest. A prompt asking it to
"preserve motion" does not condition the entire recorded trajectory.

For restyling an existing recording while retaining its motion/geometry,
inspect the live **transfer** contract and use whole-sequence controls derived
from the source, such as edge conditioning. Do not silently substitute prefix
continuation when full-clip preservation was requested. Explain a missing
control mode before spending the customer's inference request. Do not invent
depth/segmentation controls if those data were not supplied or validly derived.

The published specialized native transfer tool is `cosmos3_nano_transfer_video`.
Request `get_model_schema(model_id="cosmos3-nano", tool_name="cosmos3_nano_transfer_video")`
to inspect that exact contract without every sibling mode. Preserve that choice
as `tool_name: "cosmos3_nano_transfer_video"` in the native workflow phase, or
`--tool cosmos3_nano_transfer_video` in the file helper. Use exactly that tool's
input schema: its specialized contract already selects the mode. The separate
generic `cosmos3_nano_generate_media_native` contract requires an explicit mode.
Do not mix the generic and specialized inputs or depend on catalog ordering.
For a direct call, load only that exact tool with tool_search's existing
`max_results:1`, `fields:["name"]`, `mcp_server:"bionemo-models"` parameters.
A file-based workflow does not need the direct model tools loaded into chat.
Queued whole-study admission is not evidence that either model call has been
submitted. Describe the Study as queued/in progress until its actual phase
receipts contain operation IDs; never say both media calls were submitted merely
because the supervisor accepted the plan.
Count top-level augmentation requests separately from recorded child generations:
one LeRobot request can invoke multiple native generations. Say "two top-level
requests," not "exactly two model calls." Count or identify children only when
their retained manifest/operation history records them; otherwise state unknown.
Uploads and deterministic CPU analysis are not model inference.

For `cosmos3-lerobot-augmentation`, read its scientific schema and artifact
contract. The current recorded-video path is `augmentation.mode: transfer`
with supported `augmentation.conditioning.controls`, for example `edge`.
Select actual episodes/cameras, retain the original actions and state, and use
the existing file-based batch helper with the exact published artifact roles.
The native Cosmos transfer request has its own typed control-input fields;
do not copy the LeRobot parameter shape into the native request.

Use the existing typed `run_scientific_workflow` batch step with source_file
pointing to the actual archive and parameters_file containing the scientific
settings plus `"source":{"kind":"uploaded-bundle"}`. The client uploads the
source and injects its verified artifact reference; do not invent an ID or read
its implementation. For LeRobot, select the exact published
`submit_cosmos3_lerobot_augmentation` contract. Native media inputs needing an
artifact use the typed `upload_workspace_files` first, then the returned small
reference in the native input_file. These are separate interfaces; do not
pre-upload every scientific-batch source unnecessarily.

Measure frame count, dimensions, FPS, episode/timestamp integrity, selected
and unselected cameras, and exact non-video values. Inspect same-index frames
and temporal motion, retaining original and generated clips. Transfer can
still change materials, geometry, contacts or fine motion. Numeric action-array
equality does **not** establish that generated pixels remain aligned to those
actions, and neither a prompt nor a decoded MP4 establishes policy-training
suitability. Report those limits instead of calling augmentation fully verified.

For an unattended recorded-video + LeRobot study, use the published typed
`robotics-analysis` phase after the native and batch phases. Supply the exact
original `source_video` and `source_archive`, the earlier native `result.json`
as `native_result`, the batch `output-manifest.json` as `manifest_file`, and
explicit `selected_cameras`. It reads the verified native-file contract and
manifest-indexed archive bytes, checks every nonvideo value/type, episode
identity/timestamp and camera, and measures decoded RGB/temporal differences.
Do not replace these checks with a script globbing `*.mp4` beside result.json:
native bytes are declared by the result contract and batch media are inside
verified archives. Missing files or null comparisons are not successful checks.
The helper publishes `metrics.json`, `report.md`, `native-output.mp4`,
`augmented-dataset.tar.zst`, `completion-manifest.json` and
`visual-comparisons.json`. Available `comparison-native.png` and
`comparison-dataset-NNN.png` are automatically registered customer downloads.
They show at most four unedited decoded frames at matching zero-based indices:
source on top, generated output below, with exact source/output hashes in the
index. Missing alignment stays explicitly unavailable. Review these images and
the clips for actual appearance changes; never interpret their existence as a
geometry, lighting-only, contact, motion or physical/action-validity pass.
Declare the returned
video and dataset as deliverables, not just manifest links. Use the existing
`parquet-export` phase for NPZ/HDF5/ZIP/SQLite exports from the original recorded
Parquet. Keep whole-study operation receipts in the final provenance. Automated
measurements do not replace a visual review or prove action-label validity.

Mode selection and byte integrity are not a scientific acceptance result.
Require evidence from the exact deployed runtime and actual requested workflow.
