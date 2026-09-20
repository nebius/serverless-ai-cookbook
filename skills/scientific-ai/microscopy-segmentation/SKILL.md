---
name: microscopy-segmentation
description: Segment bounded 2D microscopy images using Cellpose CPSAM v2, preserving channels, instance masks, object counts and overlays. Use for microscopy and cell segmentation rather than generic SAM2 or CT organ segmentation.
license: Apache-2.0
---

# Cellpose microscopy

Use `scientific-gateway`, App `cellpose-cpsam-v2`, and its live schema. Follow
the App's research-only/noncommercial restrictions; a working key is not a
commercial license. Method reference: https://cellpose.readthedocs.io/en/latest/

1. Inspect actual image dimensions, pixel type, channel order and microscopy
   provenance. Current adapter supports bounded 2D grayscale/RGB PNG/JPEG/TIFF,
   up to three channels, not an arbitrary z-stack/time series. Do not flatten
   a 3D stack or discard channels without an explicit analysis choice.
2. Preserve the original. If the user selects a slice/channel or a conversion,
   save it as a new image and record that transformation and pixel spacing.
   Diameter is in pixels; do not copy a micron value into `diameter` without a
   measured pixel scale. Use the published research acknowledgement.
3. Use the advertised artifact input when present. For a base64-only contract,
   construct a local input JSON from the image bytes and invoke the native file
   client outside chat. Never paste an image's base64 through the language model.
4. Retain and decode the actual instance-mask PNG and overlay. Preserve integer
   instance IDs (not an 8-bit display conversion). Compare shape to the input,
   count nonzero IDs and check areas against `object_areas_px` / `object_count`.
   Inspect merged/split objects and edges visually; don't infer accuracy from
   the returned object count or an attractive overlay.

For labeled data, evaluate overlap with an explicit matching rule and report
unmatched objects. Without ground truth report measured segmentation statistics,
not precision/recall. Keep output paths, hashes and operation/runtime identity.
Use `sam2-segmentation` for prompted objects/tracking; `imaging-models` for CT.
