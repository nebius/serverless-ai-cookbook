---
name: imaging-models
description: Research biomedical imaging on the gateway — chest X-ray reasoning (nv-reason-cxr-3b, OpenAI-chat) and CT segmentation (nv-segment-ct, native).
license: Apache-2.0 AND CC-BY-4.0
---

# imaging models

Shared rules: `scientific-gateway`. Research use only; outputs are not
diagnoses.

## nv-reason-cxr-3b (protocol `openai-chat`)

Chest X-ray reasoning model speaking the OpenAI chat protocol. Send standard
chat payloads with the image per the deployed runtime's expected encoding
(base64 data URL or artifact reference — confirm via a minimal call and the
400/422 detail; do not guess). MCP `analyze_image_openai_chat` or
`invoke_model` with `protocol: "openai-chat"`. Being OpenAI-compatible does
not mean arbitrary chat text works — the model is domain-bound to CXR imagery.

## nv-segment-ct (native)

CT segmentation. Payload requires either `label_prompt` (non-empty list of
integer labels) or `points` with matching `point_labels`; image input is a
NIfTI volume (`nibabel`-loadable) supplied per the runtime's input convention.
Exact field names were being pinned from the deployed adapter at adaptation
time — probe minimally and read error details. MCP `segment_ct_native`.

Live verification status: readiness report (explicitly not yet live-tested).
