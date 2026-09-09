---
name: molmim-nim
description: Optimize or sample research molecules through the bounded bionemo_molmim NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# MolMIM NIM (hosted, bounded)

Use `bionemo_molmim` with a SMILES seed. Choose `CMA-ES` for bounded property
optimization or `none` for sampling. Event limits cap candidates, iterations,
and particles at 100. Treat QED/plogP as proxy properties only. Return SMI and
JSON artifact links and state that chemistry, toxicity, and assays are not
validated.
