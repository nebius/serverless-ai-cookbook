---
name: sam2-segmentation
description: Use the hosted SAM2.1 Hiera Large App for prompted images, automatic image masks and prompted video tracking, with explicit coordinates, frame indices, object IDs and artifact verification.
license: Apache-2.0
---

# SAM2 image and video masks

Read `scientific-gateway`; select `sam2-1-hiera-large` and its exact live tool.
Primary source: https://github.com/facebookresearch/sam2

Choose the mode explicitly:

- `prompted-image`: positive/negative points or a bounding box on one image.
- `automatic-image`: propose masks without points/boxes.
- `prompted-video`: track objects from prompts at the chosen zero-based frame.

Inspect dimensions/frame count/FPS before selecting prompts. Points use pixel
`x`,`y`, label 1/0 and object IDs; a box is `[x0,y0,x1,y1]` with increasing
coordinates. Coordinates must refer to the **submitted** image size, not a
thumbnail. Current worker supports at most eight prompted objects and 320 video
frames. Get current gateway limits; don't silently truncate a customer's video.

Upload or encode actual media with the file client according to the public
schema, never by pasting base64 in chat. Preserve the source and conversion
record. Retain the durable operation and verify its returned mask/overlay ZIP
and manifest. Decode masks, check frame coverage, shapes and IDs, and inspect
occlusions and object re-entry. Missing frames remain a failed coverage check.
Masks with plausible shapes do not prove the object stayed correctly tracked.

For long videos, propose explicit segments with timestamps and an object-ID
mapping strategy; cross-segment tracking identity is not automatic. Do not
invent unsupported semantic class labels or claim a mask is a medical diagnosis.
If measuring accuracy, use labeled frames and an explicit IoU/matching protocol.
Report transport success separately from segmentation/tracking quality.
