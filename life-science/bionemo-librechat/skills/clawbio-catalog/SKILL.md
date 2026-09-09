---
name: clawbio-catalog
description: Discover the pinned ClawBio bioinformatics skill catalog, read a skill contract, or run one of the image-qualified demo-only workflows without local patient-file access.
---

# ClawBio catalog

Use the local `clawbio` MCP server when a user asks what ClawBio can do or wants
to inspect a ClawBio workflow contract.

1. Call `clawbio__list_skills` to search the catalog.
2. Call `clawbio__describe_skill` before recommending or invoking a skill.
3. Treat `demo_runnable_in_image` as authoritative. Do not infer executability
   from a catalog entry's upstream `runnable` field.
4. Call `clawbio__run_skill` only after the user explicitly asks to run a demo.
   Set `demo=true`. This image intentionally provides no local input/output path
   parameters and cannot use it to inspect patient or customer files.

The catalog is for research and education. Do not present its output as a
clinical diagnosis, treatment recommendation, or validated medical decision.
