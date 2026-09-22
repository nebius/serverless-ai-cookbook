# Conversational model default

The product-owner-approved default conversational model is
`zai-org/GLM-5.3-Flash` on Nebius Token Factory.

Do not change this default, add an automatic fallback, or change the model set
on a live customer workbench without explicit product-owner approval. A user or
deployment may still select another available model explicitly.

This policy applies to the LibreChat planning/conversation model. Models pinned
inside a specific scientific workflow—such as a qualified clinical report,
patient, clinician, or judge model—are separate explicit choices and must not be
silently rewritten when the conversational default changes.
