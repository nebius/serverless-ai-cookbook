# Attribution and adaptation

This is the Nebius Scientific AI customer adaptation, maintained in
`rene-tech/serverless-ai-cookbook`. It is not the unmodified, signed or
NVIDIA-verified upstream skill package. Logos/names do not imply endorsement.

Sources reviewed on 2026-09-20:

- [NVIDIA/skills](https://github.com/NVIDIA/skills/tree/fd9f1466ff8a39178e488981e8b5118709392949),
  revision `fd9f1466ff8a39178e488981e8b5118709392949`: `nemotron-speech`,
  `digital-health-clinical-asr-eval`, `digital-health-clinical-asr-build`,
  `paidf-augmentation`, `physical-ai-video-data-augmentation`, `i4h-lerobot-viz`,
  `dicom-series-preflight`, `dicom-series-to-volume`, `nv-segment-ct` and
  `medtech-model-evidence-export`. NVIDIA and its contributors retain copyright.
  Upstream documentation is CC-BY-4.0; code is Apache-2.0, subject to per-file
  notices. Full license texts accompany this bundle.
- [NVIDIA-BioNeMo/bionemo-agent-toolkit](https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit/tree/0e67a612e4045f007e38fa77adc8f3ebfc5616b6),
  revision `0e67a612e4045f007e38fa77adc8f3ebfc5616b6`: BioNeMo model and
  Complexa target/design/sweep/evaluation guidance. Existing adapted skills
  retain their Apache-2.0 / CC-BY-4.0 declarations.

Changes: replaced upstream NVCF/gRPC/local deployment assumptions with caller-
scoped hosted MCP contracts; added durable operations, file transport, current
adapter limits, evidence handling, EN/DE evaluation, and conditional client
capabilities. No NVIDIA signature is asserted for modified instructions.
NVIDIA's complete runners/containers are not bundled. The new lexical evaluator
is our stdlib implementation; it explicitly identifies differences from upstream
KER/semantic scoring and reuses our existing historical WER method unchanged.

Independent method references (not NVIDIA-branded):
[scvi-tools](https://docs.scvi-tools.org/en/stable/tutorials/index.html),
[Cellpose](https://cellpose.readthedocs.io/en/latest/),
[SAM2](https://github.com/facebookresearch/sam2),
[MindEval](https://github.com/SWORDHealth/mind-eval).
These projects and their models retain their own licenses. Skill installation
does not grant rights to model weights, private datasets or academic software.

Unless a file declares otherwise, new bundle tooling is Apache-2.0. Existing
clinical helper files retain their source notices. The private Nebius/skills
source used in some operator images is intentionally excluded from publication.
