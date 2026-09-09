# Event and interactive-viewer follow-up — 2026-09-09

## Findings and scope

- The Token Factory model group had no icon. The official app favicon at
  https://static.nebius.com/app/ai-studio-ui/assets/favicon.ade3d1245f2fbcbf.svg
  supplies the navy/lime mark; it is now a local asset used consistently.
- The footer now pairs NVIDIA and Nebius. NVIDIA uses the retained green symbol
  with a black wordmark on a white backing; both logos have balanced sizing.
- The previous viewer code still existed but was disconnected from the current
  app. Its artifact relay depended on the retired clawbio contract. Re-enabling
  that relay would not restore current operation results.
- The event page https://luma.com/5b82vwsa lists five tracks. The six starters
  cover those tracks, with two entry points for longevity biology. They remain
  editable drafts and do not change the chat LLM or authorize compute.
- Infrastructure scope changed during review: preparation and skills/MCP setup
  handoff are included, but participant account connection and execution remain
  outside the hosted workspace.
- https://github.com/nebius/skills is private according to authenticated GitHub
  metadata. No private contents have been copied into this public source tree.
  Redistribution approval was requested separately. The public MCP guide is
  available at https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md.

## Implementation

`structure-mcp.py` adds one read-only `visualize_structure` tool. It validates
an operation UUID and fetches `/v1/operations/{id}/result` with the existing
gateway key over verified HTTPS. Redirects, arbitrary URLs and filesystem paths
are not accepted. It extracts bounded real PDB/mmCIF/SDF structures; missing,
oversized, expired, inaccessible or reference-only results fail explicitly.
Credentials and full result bytes are not returned as LLM text.

The original 3Dmol implementation is reused and extended with molecule poses,
structure selection, errors, reliable reset and responsive fullscreen sizing.
LibreChat's HTML-only sandbox is retained; the client explicitly delegates only
fullscreen and keeps iframe width inside the message column. Stored UI resources
remain available after reload, independently of subsequent result retention.

All model specs and legacy tutorial agents receive the viewer. In per-user
gateway mode, users must configure their key for the viewer server as well;
the shared demo mode uses the existing server-managed gateway key.

The infrastructure card supplies an exact copyable setup prompt and public links.
The new preparation skill distinguishes a installed skill, an MCP configuration,
and an authenticated participant-owned cloud connection. It does not install a
cloud-management MCP server or copy operator credentials into the application.

## Acceptance and limits

- 35 offline tests pass across template, viewer and scientific-skill suites.
- Pinned client TypeScript check and production build pass.
- Six starter drafts, model preservation, provider-key dialogs, and 390 px mobile
  send controls pass browser checks without compute submissions.
- Existing OpenFold2 operation `d77ed2a3-3626-4c9b-8e1d-9722a2e68dc9` produces
  an in-chat viewer with 133 parsed atoms. Browser checks verify real camera
  changes for spin/drag, fullscreen, representation controls and reload.
- Existing DiffDock operation `91c4bef9-9dcf-4dfb-a1f8-44eabd0d646e` supplies
  both its actual receptor PDB and ligand SDF to the read-only bridge.
- No scientific models were submitted for these viewer checks. Successful
  visualization is not validation of a model's scientific accuracy.
- Batch artifact downloading, attachment upload, participant cloud accounts,
  clinical/EHR integration, and multi-tenant gateway isolation are not delivered
  by this UI update. Each participant should use their own LibreChat account;
  a shared scientific gateway key does not provide per-participant isolation.
