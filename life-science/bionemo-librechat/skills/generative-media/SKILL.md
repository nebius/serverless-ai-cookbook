---
name: generative-media
description: Generate research images (sdxl) and media (cosmos3-nano) through the scientific gateway native lane.
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

Live verification status: readiness report (not yet live-tested).
