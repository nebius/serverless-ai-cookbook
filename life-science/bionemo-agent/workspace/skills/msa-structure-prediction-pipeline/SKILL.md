---
name: msa-structure-prediction-pipeline
description: Run the bounded MSA Search to OpenFold3 research workflow with bionemo_msa_to_structure.
license: Apache-2.0 AND CC-BY-4.0
---

# MSA-to-structure pipeline

Call `bionemo_msa_to_structure` with a public or synthetic protein sequence.
The tool obtains a bounded A3M alignment and passes it directly to OpenFold3.
Report alignment sequence count, structure confidence fields, and artifact
links. If the hosted OpenFold3 route is unavailable, report it without
substitution. MSA depth and model confidence are not experimental validation.
