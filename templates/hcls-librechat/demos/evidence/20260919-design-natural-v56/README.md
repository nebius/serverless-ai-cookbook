# Scientist03 v56: completed engine, incomplete scientific report

The one unchanged natural prompt produced Study
`57c37e0e-479e-5224-a049-9f1115931dd7`. Its browser closed while ongoing at
19:22:29 UTC; all five phases completed without a followup or operator repair,
observed terminal at19:47:02 UTC. Both original calls succeeded. This is
unattended engine completion, not blanket scientific acceptance.

Independent manifest/hash verification and a second coordinate parser confirm:

- Proteina:18 artifacts,16 coordinate outputs,8 provenance-linked raw/refolded
  pairs. All8 raw and8 refolded structures pass the existing coarse geometry
  screen. Eight distinct linked design sequences are present. The request was
  seed7/num_samples4/diffusion_steps400; output pairs are not equated to requested
  samples or experimental replicates.
- BoltzGen:2 artifacts,1 exposed coordinate output, with actual chains A
  (60 residues) and B (127 residues). The target reference sequence uniquely
  matches B. The planner's analysis selected binder C from the input convention;
  no C exists in the returned coordinates. The retained measurements correctly
  say `constraint_pass=false`, but the original short report/CSV omitted that
  verdict. No remapping or changed scientific request was performed.

The original report also omitted the measured diversity/score summary despite
retaining native metadata in measurements.json. Published final output count
does not reveal all rejected search candidates or rejection reasons. Missing
upstream rows must remain unavailable, not interpreted as zero rejected.

The full requested output tree was archived (617 files/3,750,765 bytes). All13
declared final files plus four request/status files were downloaded through the
real browser (17 files/231,078 bytes), byte/hash-equal to the retained archive.
The final9,963-byte report is real and downloadable, but its scientific
reporting limitations remain a failed acceptance criterion.

## Source-only rendering correction

The existing manifest-aware helper now always renders recorded constraint
verdicts/reasons, actual observed chains, unavailable/failed selections, measured
sequence-hash diversity and exact published score/filter values. Inventory CSV
includes the same constraint verdict and selected-chain context. No evaluator
threshold, request, chain selection, measurement, ranking or model call changes.
Missing C stays missing; native filter flags remain distinct from the analysis
constraint failure. Confidence/affinity/biological success is not invented.

18 focused helper/typed-integration/rendering tests pass, including the retained
C-versus-A/B shape, null/unknown results, exact score strings, and raw/refold
deduplication. Ruff passes. A separately retained replay of the actual v56
measurements produces corrected report/CSV only; measurements.json stays
byte-identical. Original customer artifacts remain untouched. Installed-image
and fresh-client acceptance of the successor are not asserted here.

Protected root `scientific-unattended-20260919/natural-v56/scientist-03`:

| Receipt | SHA-256 |
| --- | --- |
| independent-artifacts-r1.json | `6641e217b9567b8c073e4e5460b000603360d56a9869cb9bd6f3af624112480a` |
| terminal-files-r1/receipt.json | `786fc6e8d5d3b8d942145277b3344b5f8f953e5d2b6d30fcce6987b6e9c1581b` |
| terminal-browser-r1/receipt.json | `faf2903267376d3bc50239b767c4122c1e243a5b19e8272e31cbddee0895d863` |
| successor-report-reassessment-r1/receipt.json | `a2e7997925e956fa5a701c57497ef60938a1115c27ee61ab87d7b1c543e9a689` |
