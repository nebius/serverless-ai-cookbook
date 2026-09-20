---
name: imaging-models
description: Research biomedical imaging on the gateway — chest X-ray reasoning (nv-reason-cxr-3b, OpenAI-chat) and CT segmentation (nv-segment-ct, native).
license: Apache-2.0 AND CC-BY-4.0
---

# imaging models

Shared rules: `scientific-gateway`. Research use only; outputs are not
diagnoses.

## nv-reason-cxr-3b (typed tool `analyze_image_openai_chat`)

Chest X-ray reasoning model speaking the OpenAI chat protocol: pass standard
`messages` (with the image per the schema's content format), plus optional
OpenAI sampling fields; do **not** send a `model` field — the App selects it.
Being OpenAI-compatible does not mean arbitrary chat text works — the model is
domain-bound to CXR imagery. Call `get_model_schema` for the live schema.

## nv-segment-ct (typed tool `segment_ct_native`)

CT segmentation: inspect the public schema for the supported file/artifact
input, plus either `label_prompt` or `points` with matching `point_labels`.
The backend consumes `input_nifti_base64`, but this is not a request to put a
volume into chat. Where the public contract advertises an artifact input,
upload the real NIfTI and pass its finalized reference. If it only advertises
base64, encode the file directly into a local JSON file and submit with the
native file client outside chat. Never invent a new artifact field.

Before submitting, inspect volume dimensions, affine/orientation, spacing,
finite intensities and compression. Preserve the original, conversion command
and input hash. DICOM series need an installed, verified converter and geometry
preflight; a directory of DICOM files is not a NIfTI volume. Do not silently
merge series, rescale intensities or guess label IDs. Use the current runtime's
label map. Verify output dimensions/affine and review the actual overlay. Label
counts alone are not segmentation accuracy. See `microscopy-segmentation` for
Cellpose and `sam2-segmentation` for non-clinical image/video masks.

This skill documents the contract, not clinical validation or runtime readiness.
