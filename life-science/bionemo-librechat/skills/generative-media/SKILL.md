---
name: generative-media
description: Generate research images (sdxl) and media (cosmos3-nano) through the scientific gateway native lane.
license: Apache-2.0 AND CC-BY-4.0
---

# generative media (native)

Shared rules: `scientific-gateway`.

## sdxl

Text-to-image. Payload fields observed in the deployed adapter: `prompt`
(required, non-empty), optional `negative_prompt`, `seed`, `steps` (1–50,
default 20), `guidance` (default 5.0; `guidance_scale` also accepted),
`width`/`height` (default 512; confirm allowed size bounds with a minimal
call). MCP `generate_image_native`. Result: image artifact — download it per
the shared manual; do not inline base64 into chat.

## cosmos3-nano

World/media generation (`cosmos3_nano_generate_media_native`). The deployed
payload contract was being pinned at adaptation time — run discovery and a
minimal probe, reading the 400/422 detail, before constructing full requests.
Do not assume NVIDIA Cosmos documentation fields for this portable runtime.

Live verification status: readiness report (sdxl partially verified against
adapter source; cosmos3-nano explicitly not yet live-tested).
