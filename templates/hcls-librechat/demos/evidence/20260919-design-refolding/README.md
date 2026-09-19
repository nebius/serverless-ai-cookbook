# Cross-model design/refolding: all frozen cases retained

All 196 originally prepared ESMFold2-Fast followups and the additional 24
RFdiffusion → ProteinMPNN → ESMFold2-Fast followups completed through ordinary
scientist keys. This is API/batch workflow and computational self-consistency
evidence, not a fresh natural LibreChat delivery or experimental validation.

| Source design group | Refolded sequences | Source requests / distinct backbones | C-alpha RMSD min / median / max (Å) | C-alpha lDDT min / median / max |
| --- | ---: | ---: | --- | --- |
| ProteinMPNN on experimental backbones | 192 | 48 / 16 | 0.342 / 1.133 / 16.051 | 0.437 / 0.929 / 0.989 |
| Mosaic designs | 4 | 4 / 4 | 1.305 / 5.382 / 7.781 | 0.509 / 0.578 / 0.844 |
| ProteinMPNN on generated RFdiffusion backbones | 24 | 6 / 6 | 0.423 / 1.219 / 18.032 | 0.593 / 0.952 / 0.989 |

The six RFdiffusion backbones span lengths 48, 76 and 256, with two backbones
per length. Each inverse-folding call requested four sequences; all six calls
and all 24 downstream refolds succeeded. Requests used the existing four
scientist lanes, one active request per key. Limits were not raised.

Every refold has the exact requested designed sequence, full positional
correspondence and finite coordinates. The fit includes redesigned residues,
not just residues whose amino-acid identity happens to match the source. RMSD
uses a proper least-squares C-alpha rotation; local distance comparison uses
15 Å reference pairs and 0.5/1/2/4 Å tolerances. These are not all-atom lDDT,
optimized TM-align, affinity, stability or activity measurements.

The substantial worst-case deviations are retained. There is no post-hoc
quality threshold or failed-case removal. Designs sharing a backbone are not
independent experimental replicates. A valid structure file is not evidence
that the design recovers its intended geometry or would work experimentally.

## Reproducibility and source binding

[Initial 196-case report](initial-196.json) and
[RFdiffusion-derived 24-case report](rfdiffusion-24.json) retain each case,
operation, reference/result/evaluation SHA256 and metric. They are generated
by `scripts/qualification/summarize_design_recovery.py`, with five tests for
missing/failed rows, duplicate receipts, changed references and nonfinite
metrics. Original results and evaluations are not rewritten.

Protected manifests:

- `/home/tux/secure-handoff/librechat-rene-20260918/qualification-design-followups-v1/cases.json`
  selects 196 refolding cases explicitly; its six additional inverse-folding
  preparation cases are counted separately, not treated as missing refolds.
- `/home/tux/secure-handoff/librechat-rene-20260918/qualification-rfdiffusion-refolds-v1/cases.json`
  binds all 24 new refolds to the six completed inverse-folding operations.

Original cohort receipts are under
`/home/tux/secure-handoff/scientific-qualification-20260918/cohorts/` in
`design-followups-r1`, `rfdiffusion-inverse-followups-r179` and
`rfdiffusion-refolds-r179`. Recorded release boundaries remain in their
campaign/operation files; the 196-case study is not relabeled as a new homogeneous
release179 run. No affinity, paper-reproduction or whole-platform readiness
claim follows from these results.
