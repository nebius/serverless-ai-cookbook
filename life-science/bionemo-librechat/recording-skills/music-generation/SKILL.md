---
name: music-generation
description: Generate instrumental music, sound beds, or short sonic identities with a hosted music App such as ACE-Step, preserving the exact live schema and downloadable audio artifact.
license: Apache-2.0
---

# Music generation

Read `scientific-gateway` first. Discover the current caller-visible music App;
prefer `ace-step` only when it is present and ready. Read its exact live schema
before preparing a request because prompt, duration, lyrics, seed, format, and
conditioning controls can differ between deployed variants.

For marketing-video music, ask for or infer the intended duration, energy,
instrumentation, pacing, and whether speech will sit above the track. Prefer an
instrumental result unless vocals or lyrics were requested. Keep the prompt free
of artist imitation and request a clean ending when the clip has a fixed length.

Submit once with a stable idempotency key. Preserve the operation ID, model ID,
input JSON, and exact returned audio artifact. Download and hash-verify the full
artifact before presenting it. A preview or text-only completion is not a
finished audio deliverable. Do not claim license terms from model output; report
the deployed model and the platform's applicable usage terms separately.
