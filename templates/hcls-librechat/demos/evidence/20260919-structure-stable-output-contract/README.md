# Stable, byte-preserving structure output reference

The original private-IP v60 scientist-01 study failed final publication; it is
not a completed customer study. Its OpenFold2 operation succeeded, and all three
prediction/comparison/report phases completed, but the saved plan required
`compare/prediction.cif`. The measured prediction was actually PDB. The helper
correctly retained `prediction.pdb`; no CIF file existed. This was an invalid
future output promise, not a failed model call or scientific conversion need.

Exact retained identities:

- Source `3f138ea02c809758f285fa59cda5b8cc0dcaf838`; OCI index
  `6d764aca3237cec1ccd234690a191ad89247e08d3f60b7b1f4f1722a6a414dca`.
- Study `4accfc33-6ce3-5aba-9ad2-a2e0edf338ab`; successful operation
  `8f17f012-0c76-462e-8095-e013fcd677be`.
- Protected evidence root `U = scientific-unattended-20260919`:
  `natural-v60-private/scientist-01/terminal-detail.json`, SHA256
  `1a74376ea931c9df6024e78a6f5581a10743f1fb1cc8e6c04fc98f739e4fad54`.
- Complete retained source tree:
  `independent-v60-private/scientist-01-s3-20260919T233643975552Z`,
  44 files / 452,297 bytes; receipt SHA256
  `5e72c1d720f8775b790763f71f381f7a5ab98ec2446a8e04888d77e649761d6e`.
  Original 49,167-byte prediction SHA256
  `e83411ea63f46ed591d2f2d0f88c7d46070ae5e659179ca74959f0727998cafa`.

## Scoped source repair

Structure discovery now guarantees the logical file key `prediction.structure`.
The Study file map resolves it to the verified original `prediction.pdb` or
`prediction.cif` path. It does not create, rename, convert or duplicate a
coordinate file. Downstream consumers and download URLs retain that actual
extension. Helper provenance records `prediction_format`; publication verifies
both that format and the measured coordinate hash before exposing the alias.

Preflight rejects required future format-specific structure references with an
actionable stable-key alternative. Existing materialized files and unrelated
native/batch conditional output contracts remain supported. Original failed
plans, model results, reports and receipts are unchanged.

## Verification and remaining qualification

`test_structure_output_alias.py` adds eight cases: real PDB/mmCIF
submit→advance→downstream comparison→report→publication, four pre-admission
format-guess failures, unrelated-contract compatibility, and rejection of the
unchanged retained failing plan with model execution forbidden. The raw-byte
fixtures include CRLF PDB and a leading-comment mmCIF.

Local results: 71 scientific/helper/output-contract cases passed; the exact
retained-plan case separately passed in the SDK environment; 52 broader
Study/model-output cases passed. Split environments avoid incompatible local
Python scientific/SDK dependencies; they are not one installed-image gate.
Protected JUnit receipts under `U` are:

- `v61-structure-output-alias-local-r4.xml` (71 pass), SHA256
  `59d8830cc3c5a3c522f72aeba48a69c079237ffdc8b51b55848f68c1a231bf23`.
- `v61-structure-output-alias-retained-r4.xml` (1 pass), SHA256
  `42aa0e4093ae62f3bc9cd21b93d4f81df0a04993f2f035f98bafb8d3809e6cc2`.
- `v61-study-output-backcompat-r1.xml` (52 pass), SHA256
  `67a0aaa128f26838e17a3b25a1bd68f8774fd13ab245eca4ccf2c20b5f409725`.

For the successor installed gate, run all eight new cases against installed
modules with `SCIENTIFIC_RETAINED_V60_01_SNAPSHOT` pointing to the exact read-only
snapshot above, alongside the existing helper/Study suites. A fresh natural
client run and actual UI downloads remain required after the successor image
is frozen and deployed. Source tests do not retroactively complete v60 or
establish scientific/experimental correctness.
