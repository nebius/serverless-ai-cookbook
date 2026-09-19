# v45 real-browser retained-text link regression — narrow pass

At05:58–05:59 UTC the actual browser exercised source
`f25b35fe5a91f8ed9b1a775b2cb97054a4ebedba`, image
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v45-f25b35f`, index
`sha256:135139167e96ec05ec483307b578cbfacad1180f85db44d22b16d9a7314c6fb5`.
Endpoint `aiendpoint-e00xhmyjzgndgdzgnk` uses the same scientist10 bucket/key.
Deployment/configuration, source/build tests and installed checks are separately
recorded in `../20260919-workspace-fenced-links-v45/README.md`.

The supported authenticated LibreChat conversation import returned201. New
conversation `35b2bd47-e57d-4618-9391-0b68c5e97b72` is explicitly labelled
**v45 renderer regression only — retained v43 six/seven workspace URLs (no
inference)**. Both retained assistant responses and original code blocks are
byte-identical. No model call, prompt coaching, runtime overlay, changed budget
or mutation of the original v43/v44 conversations occurred. This is a UI
regression replay, not new natural scientist completion.

## Actual browser result

- The real syntax-highlighted Markdown pipeline renders two adjacent Workspace
  files navigation groups containing6 and7 visible anchors (13 total).
- Original highlighted code text is exact, including trailing newlines.
- **Seven final-group links were actually clicked, opening the normal workspace
  route; all seven selected files were downloaded through its real button.**
  The first six-link group was rendered/URL-verified but not clicked separately.
  This is7 downloads, not13.
- These seven files total153,693 bytes and match the independent S3 receipts:
  NPZ, HDF5, ZIP, closed SQLite, source-reference NPZ, final comparison JSON and
  final report. The natural v43 numerical verification remains separate.
- An unauthenticated request for the final report on the existing workspace
  file route returns401. No new authorization or arbitrary URL behavior was
  introduced.

## Failure history and scope

v44's actual browser rendered zero links because the highlighter supplies
strings interleaved with passive span elements; its direct-string component
tests did not cover that shape. The negative actual-browser receipt remains
in `../20260919-workspace-fenced-links-v44-live/README.md`. v45's source tests
first reproduced this failure through the pinned Markdown/highlighting pipeline
and then passed with bounded passive text extraction. v44 was not silently
updated or relabelled successful.

The underlying v43 natural task still required one ordinary continuation after
five preparation execution failures and a wrong ZIP boolean comparator. Its
wrong5,120 vector count was not explicitly corrected; final5,504 counts only
floats, while the independently preserved total is6,144 scalar values. A better
link renderer does not correct those scientific/narrative claims. No broad
workbench, medical or platform readiness verdict follows from this narrow pass.

## Protected receipts

Root `/home/tux/secure-handoff/scientific-qualification-20260918/browser-evidence/scientist-10-v45-renderer-regression/`.

| Receipt | SHA256 |
|---|---|
| acceptance-receipt.json | `da5b3ac4326b96cc4cd366edd5411b1916f2a3cc2fff3c376ed9d31c02bf8e93` |
| receipt.json (normal import/auth) | `eeb07751b2d2b44f8f3de999cc43d8ae884bc4c1b1677c2c7cc707a113f909e1` |
| browser-dom.json | `7a3475284830299222b6a1c807763c52038835442a69f767a41a901d8ed47281` |
| browser-clicks.json | `cff45e906bbdd8bec147513209700d4a2b5b9e4df34759d6ec6240e6bf0e3d91` |
| download-verification.json | `4f836ac5276f912a4f16c7f4325f000d2720c921fdab20c9c5f2e0ac01a19db1` |

Retained messages, import payload/response, screenshot and all seven actual
browser files accompany the receipts. Task-owned previews and bucket data are
retained for review; no Rene production endpoint was changed. No further
scientist/model calls were initiated after this gate.
