---
name: generative-media
description: Generate research images or augment recorded videos and LeRobot data through the live scientific model contracts.
license: Apache-2.0 AND CC-BY-4.0
---

# generative media (native)

Shared rules: `scientific-gateway`.

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

For `cosmos3-lerobot-augmentation`, read its scientific schema and artifact
contract. The current recorded-video path is `augmentation.mode: transfer`
with supported `augmentation.conditioning.controls`, for example `edge`.
Select actual episodes/cameras, retain the original actions and state, and use
the existing file-based batch helper with the exact published artifact roles.
The native Cosmos transfer request has its own typed control-input fields;
do not copy the LeRobot parameter shape into the native request.

Measure frame count, dimensions, FPS, episode/timestamp integrity, selected
and unselected cameras, and exact non-video values. Inspect same-index frames
and temporal motion, retaining original and generated clips. Transfer can
still change materials, geometry, contacts or fine motion. Numeric action-array
equality does **not** establish that generated pixels remain aligned to those
actions, and neither a prompt nor a decoded MP4 establishes policy-training
suitability. Report those limits instead of calling augmentation fully verified.

Mode selection and byte integrity are not a scientific acceptance result.
Require evidence from the exact deployed runtime and actual requested workflow.
