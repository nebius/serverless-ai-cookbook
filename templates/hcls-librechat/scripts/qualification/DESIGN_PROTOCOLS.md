# Bounded design-protocol coverage

These are computational service/constraint tests, not evidence of binding,
catalysis, therapeutic efficacy, or experimentally usable designs. Preserve
failed requests and original outputs. A completed pipeline and finite
coordinates alone do not establish acceptable backbone geometry.

## Binding uploaded inputs

A scientific case may declare a direct parameter-to-manifest-entry binding:

```json
{
  "arguments": {"parameters": {"operation": "scaffold-motif"}},
  "preparation": {
    "artifact_id_parameters": {"input_pdb_artifact_id": "target_structure"},
    "inputs": [{"name": "target_structure", "local_path": "inputs/1UBQ.pdb"}]
  }
}
```

The abbreviated input above must also carry the ordinary frozen SHA-256, byte
count, media type, compression and semantic type. `prepare_arguments` uploads
the exact file, validates the returned artifact UUID, then fills the named
`parameters` field. The original case is not mutated. A resumed case reuses its
recorded finalized reference. Unknown input names, invalid declarations and
missing/invalid UUIDs fail before model admission; friendly artifact names are
not sent as invented platform IDs. This is explicit binding, not arbitrary
recursive interpolation.

## Planned source-driven gaps

Pinned BoltzGen source: `HannesStark/boltzgen` revision
`31d9d9b9c72245b4ed6fe8742d6fbf4e1a3552a0` (v0.3.2).
Pinned RFdiffusion source: `RosettaCommons/RFdiffusion` revision
`9273ef67335acaf91df0150473a274759229cdf6` (v1.1.0).

- Peptide: short peptide against the retained human PD-L1 structure; exact
  target identity, requested peptide length and geometry measured separately.
- Small molecule: upstream chorismite example, CCD TSA; ligand presence and
  chemical identity, requested protein length and available affinity metrics.
  Predicted affinity is not ground truth.
- Nanobody/Fab: pinned upstream antibody scaffolds adapted to retained PD-L1;
  exact fixed framework/order, variable CDR bounds, target identity and both
  antibody chains where applicable. Adaptation must be recorded.
- Protein redesign: benign ubiquitin loop redesign; exact fixed residues and
  measured coordinate preservation. A separate target chain is not an inherent
  requirement of this upstream protocol.
- RFdiffusion motif: ubiquitin A23–34 with explicit flanks; preserve motif
  sequence and residue mapping, calculate proper rigid-aligned motif C-alpha
  RMSD. Raw coordinate differences are invalid because global orientation is
  arbitrary.

Retain existing server filters and requested limits. No winner is an honest
finite-search outcome. A suspected protocol-specific output-validator mismatch
requires an exact legitimate upstream-output reproduction before changing the
validator; do not weaken thresholds to manufacture a pass.
