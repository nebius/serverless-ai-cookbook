# Fenced workspace-file links: v44 candidate

As of 2026-09-19 05:45:57 UTC. This is a narrowly tested UI repair, not a new model or scientific qualification. Live authenticated-browser acceptance is a separate deployment gate owned by the workbench lane.

## Customer failure and change

The natural scientist-10 v43 conversation `521be947-6927-57c3-bc14-27111bd7c494` returned valid workspace download routes inside fenced code. Unlike the previously repaired inline-code case, those routes were not clickable. The first response contained six routes; its subsequent final response contained seven, including `source_reference.npz`, `comparison_results.final.json`, and `report.final.md`.

The repair keeps the original pinned LibreChat `CodeBlock`, its exact content, and its copy/execution controls. For blocks containing only complete recognized same-origin workspace-route lines, an adjacent **Workspace files** list provides links. Ordinary code, mixed code/URLs, external URLs, malformed paths and unrecognized parameters remain unchanged. Links use the existing authenticated workspace route; this does not add a new download API or broaden path access.

Both actual fenced-renderer branches are patched with exact-source guards. Existing math/Mermaid handling and both inline-code branches remain intact.

## Exact candidate

- Source: `6976499dd79c38fe91d8d73ec7d5e7e4a2d6c674` in the cookbook fork.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v44-6976499`.
- OCI index: `sha256:68a23fd0b48f18f7ca913f4225da21f8281a24e3eb2b71afb16a8e2aa58256bf`.
- Linux/amd64 manifest: `sha256:dc073b968d42408f93d6f347a6cf3e0d60af3ade95d436e8cd9222b1ba1eaa53`.
- Original pinned LibreChat base: `sha256:1eaa9a5e7dc7e7a141d6f452f46e5547646a7c6113e610348511f801e7b185d1`.

Built from a clean archive of that source, with the existing pinned official-skills preparation. No Dockerfile, backend, runtime helper, prompt, model, endpoint or capacity changes are part of this fix.

## Checks completed

1. Eleven focused Node tests pass against the exact base image: inline-code compatibility, six-file natural fixture, original-code preservation, ordinary/mixed-code rejection, CRLF and Unicode handling, plus existing workspace deep-link behavior.
2. The complete renderer patch applies to the actual base's `MarkdownComponents.tsx`; both fenced wrappers are present and TypeScript transpilation succeeds.
3. The full client Vite build succeeds (9,692 modules). The published image's OCI source label matches the committed source.
4. The published final image contains the new compiled renderer in `assets/hooks.nnr2b8ee.js`, SHA-256 `ccf9088327b167e44ac38f4e9397f1638ff2aaff7fca67d70e51029701d27d0b`.
5. Independent actual React rendering of the retained natural conversation finds both the historical six-line and final seven-line fences. They produce exactly six and seven links respectively; the original code renders byte-for-byte unchanged. No network/model call was made for this replay.

The first installed-image checker incorrectly expected the build revision as an environment variable. The unchanged Dockerfile exposes it as an OCI label; the checker was corrected to inspect that existing label. This was a checker assumption, not a modified image or a customer failure. An earlier six-only retained-render receipt remains preserved beside the expanded two-block check.

## Evidence and remaining gate

[receipt.json](receipt.json) binds the private receipts and hashes. Protected originals are under `/home/tux/secure-handoff/scientific-qualification-20260918/`; they contain no newly generated inference. The exact retained second-final messages hash is `503d1067dee12d4a4a1d7fc61697b7479a164c64e8c1aef91f39c628abab5896`.

The final gate is to load the retained response on the deployed candidate, click the adjacent links as the authenticated scientist, and verify downloaded bytes. Passing these source/build/offline checks alone is not a clean natural-workflow completion or evidence of scientific correctness. In particular, the v43 report's incorrect 5,504-versus-6,144 numeric-value narrative is unrelated and remains a recorded limitation.
