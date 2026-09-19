# Highlight-aware fenced links: v45 successor

As of 2026-09-19 05:54:11 UTC. This is source/build evidence; authenticated live-browser acceptance remains separate.

## Preserved failure and actual cause

The [v44 live gate](../20260919-workspace-fenced-links-v44-live/README.md) failed despite its isolated string-render tests passing: both retained fenced blocks produced zero workspace links. Live React fiber inspection proved that the installed wrapper received an array of strings interleaved with `span.hljs-number` elements (auto-detected Perl highlighting), not a string/string-only array. The installed bundle was present; the recognizer rejected the highlighted children.

The new regression uses the actual pinned `react-markdown` and `rehype-highlight` packages, with the application's actual `langSubset` and `{detect: true, ignoreMissing: true}` configuration. It first reproduced the v44 `0 !== 6` failure. It now exercises both the original six-file and final seven-file responses, including the same auto-detected Perl/span path.

The repair reads strings and passive `span` children only to recognize complete same-origin workspace-route lines. It does not evaluate arbitrary React components, accept event/HTML properties, change the URL/path policy, or rewrite the original highlighted code. Mixed code remains code. The original highlighted DOM remains unchanged; links are adjacent.

## Frozen successor

- Source: `f25b35fe5a91f8ed9b1a775b2cb97054a4ebedba`.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v45-f25b35f`.
- OCI index: `sha256:135139167e96ec05ec483307b578cbfacad1180f85db44d22b16d9a7314c6fb5`.
- Linux/amd64: `sha256:53eba1993daac5b36542d63032e8006e255d63aef09ff5de4ebc0dff0a8b176f`.
- Thirteen tests pass, including the actual highlighted pipeline and rejection cases. The full Vite build passes. The published OCI label binds the same source.
- Installed asset `hooks.Dw4JKXhg.js`: SHA-256 `c900552776de469a85b58542e48f9f96881b01f5233ab502480d2abb4e33626b`.

No model calls, backend changes, prompt edits, limit increases or endpoint mutations were made in this repair lane. The deployment owner and workbench lane perform the live retained-conversation click/download gate. Do not replace the preserved v44 failure with these offline passes or infer scientific/report correctness from clickable links.

## Protected evidence hashes

All paths below are relative to `/home/tux/secure-handoff/scientific-qualification-20260918/`.

| Evidence | SHA-256 |
|---|---|
| `browser-evidence/scientist-10-v44-renderer-regression/highlighted-fiber-shape.txt` | `c56916efd14e19c97025d475fd7165d9b54e13bbdd245bf9076ae4d87db5481b` |
| `workbench-v44-highlight-regression.log` — expected failure before repair | `32f55fa8d0dc0c0cd7bd4b68baf7757660d60c27e9b3b96e5679ae768eb9a618` |
| `workbench-v45-source-tests.log` | `141bf56636c618e89779dabaa855e6aef7ed74b2d1f8c2c29d63a88ee9da0fac` |
| `workbench-v45-build.json` | `007ccae1dfd4a4260da5211a20cf16290b8a185069350448adeb84271dac8b23` |
| `workbench-v45-installed.json` | `54a4f9efee1d1e742b624d2156cb85b92947d9d08d8f534aa8e2584880ed41cc` |
