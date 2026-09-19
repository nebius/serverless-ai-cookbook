# v44 real-browser renderer regression — failed, retained

At05:48–05:51 UTC, exact v44 source6976499/index
`68a23fd0b48f18f7ca913f4225da21f8281a24e3eb2b71afb16a8e2aa58256bf`
was tested on endpoint `aiendpoint-e00zkv8bx00c82xkrj`. The normal authenticated
`POST /api/convos/import` route returned201 for a clearly labelled retained-text
regression conversation. No model inference, runtime injection, original chat
mutation or provider/budget change occurred. Imported conversation:
`cd4f8e4f-4f46-4074-843d-9b66b7e89674`.

Both original v43 assistant texts remain byte-identical, including inaccurate
counts and original versus corrected comparison narratives. Text SHA256:
`aab8f2772ea28eb7f6aa06bb3c8efa4861aa1bc33d8285c47f67351cbc56177e`
and `0fb3a053bc9458de3313a6673af2c1da4dab18d76aa163e1c808b29c65422dca`.

Actual browser DOM rendered both six-line and seven-line fenced URL blocks but
**zero workspace anchors and zero Workspace files navigation regions**. The
original highlighted code text is preserved. The renderer gate therefore fails
despite the earlier direct-string component tests and full Vite build passing.

Read-only React fiber inspection proves the integration cause: the real pinned
Markdown highlighting pipeline supplies `codeChildren` as a25-item array of
strings interleaved with passive `span.hljs-number` elements. Both CodeBlock
and its new wrapper receive that shape. The v44 recognizer accepts only strings
or arrays entirely composed of strings; it therefore returns no links. This is
not an absent bundle or stale frontend. A successor must test the actual
Markdown/highlighting pipeline as well as the real browser.

The authenticated workspace remains available by manually navigating the exact
URLs; this does not pass clickable-chat navigation. A501 queued-turns request
also appears in the imported agents conversation's console and is retained,
not interpreted as model inference or this renderer's causal failure.

Private evidence under
`/home/tux/secure-handoff/scientific-qualification-20260918/browser-evidence/scientist-10-v44-renderer-regression/`:

- `receipt.json` SHA256 `b98f312c9504e6abc15262d520c2a85815b7dc920e3700090f12725ff21fe16f`;
- `browser-observation.txt` SHA256 `1552a388df329d53a55a1bd0b707e27248209bb91f020365be797d066538d70c`;
- `browser.png` SHA256 `60a640d8d675e4285e54909b34e38592d37071aaca412c9bf4dec8c6dada9463`;
- `highlighted-fiber-shape.txt`, normal import payload/response and captured messages.

Original v43 natural export delivery is documented separately in
`../20260919-natural-seekable-export-v43/README.md`. This imported renderer test
is not natural customer completion and does not retroactively alter that result.
