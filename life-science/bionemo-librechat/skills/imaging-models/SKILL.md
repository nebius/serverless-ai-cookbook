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

CT segmentation: `input_nifti_base64` (required) plus either `label_prompt`
(non-empty integer label list) or `points` with matching `point_labels`. There
is deliberately no tiny fake example — supply the real NIfTI volume. Call
`get_model_schema` for bounds.

Live verification status: readiness report (not yet live-tested).
