---
name: genmol-nim
description: Generate research molecules from SAFE notation through the bounded bionemo_genmol NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# GenMol NIM (hosted, bounded)

Use `bionemo_genmol`. The upstream request field is named `smiles` but must
contain SAFE notation. Temperature and noise are strings. Generate at most 100
molecules; use a much smaller set for an event. QED and LogP are computational
scores, not efficacy or safety. Return SMI and JSON artifact links.
