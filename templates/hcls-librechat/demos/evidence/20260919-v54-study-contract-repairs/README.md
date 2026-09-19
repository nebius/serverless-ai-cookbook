# v54 natural 02/03: failed delivery, bounded source repairs

Both original r7 prompts were submitted once through the real dedicated-user
client, source `12fb896`, image index
`c5d01a265447b6d89c155c6266acdad18e158b78eba8888fa2586b41234d421a`,
backend190. Neither natural task delivered its requested final report. No
operator followup, scientific rerun, changed seed, model, budget or limit is
included in this evidence. The failed original records remain unchanged.

## Scientist02: four inferences, partial analysis, no final report

Study `ea5e2b2f-33b8-57fb-847f-2bc17010aa4d` was observed running immediately
before the actual browser closed at 18:24:32.827245 UTC. It continued unattended:
both Boltz2 and both Protenix calls succeeded, then the two Boltz comparisons
completed. The first Protenix comparison failed because the provenance reader
required a JSON object, although this model's uploaded complex input is an
array of records. The structure itself had already parsed. This is a local
analysis contract defect, not an inference failure or proof of a useful model.

The narrow repair accepts a nonempty array of objects as retained provenance,
keeps exact source bytes/hash and array-index JSON pointers, and explicitly
does **not** associate a coordinate index with a request index, seed or rank.
Malformed/scalar/mixed arrays remain rejected. No geometry or matching rule
changes. The submitted Protenix parameters retain `model_seeds:[7]`,
`sample_count:1`, `msa_mode:none`; filenames containing another seed are not
sampling evidence. The array alone contains no declared seed, so its reader
does not invent one.

All four retained outputs were replayed offline through the candidate helper
and independently checked with the separate Gemmi/Kabsch/contact evaluator.
These are operator repair measurements, **not** a completed customer report:

| Model / complex | Global Cα RMSD (Å) | Recovered / reference heavy-atom contacts |
|---|---:|---:|
| Boltz2 / 1ACB | 1.392246423129819 | 49 / 63 |
| Boltz2 / 2PTC | 0.6941059839459153 | 61 / 68 |
| Protenix-v2 / 1ACB | 17.10157054564747 | 0 / 63 |
| Protenix-v2 / 2PTC | 18.69059352368896 | 0 / 68 |

Protenix's poor reference agreement remains explicit. These descriptive
measurements are not affinity, biological efficacy or broad model qualification.
Recomputed completed Boltz metrics are unchanged. Reconnecting the actual
browser delivered five partial report/coordinate/diagnostic files whose hashes
match the archived originals. No final publication was fabricated.

## Scientist03: malformed whole-study call, then failed legacy fallback

Conversation `608b4a19-5e51-55cc-8deb-eafefd8b2103` ended normally with no
accepted Study and no successor-key platform operations. The exact first call
did select v2, but its `study` was JSON text rather than the then-required
object. Client validation returned a generic schema error. The 4,659-character
text also contains mismatched report-section delimiters at character3,494.
It must remain rejected, not automatically repaired. The subsequent shell
fallback wrote v1 and omitted mandatory `--output`; its recorded exit2 and
argparse diagnostic confirm no inference began. Terminal prose asking for a
later go-ahead did not satisfy unattended delivery.

The successor explicitly supports complete strict JSON text as an alternative
representation of the **same** v2 object. It rejects duplicate keys, nonfinite
numbers, double encoding and invalid schemas before admission, then uses the
identical submitter and immutable identity. The actual malformed call now gets
a bounded line/column error and composer guidance; no content is repaired and
no work is admitted. Valid object/text forms reuse one Study, verified through
the real stdio MCP SDK and CPU execution. File/composer-first guidance preserves
analysis/deliverables instead of downgrading a rejected whole study to v1.

Two original draft/method files downloaded through the actual Workspace UI
match retained bytes; these are not a report. Interim and final guidance also
requires measured sample IDs/counts/overlap before claiming two inputs are the
same samples. This preserves the separate v54/07 erroneous interim equivalence
claim rather than treating a correct later deterministic report as its erasure.

## Reproducible tests and protected evidence

Source tests:

- `test_study_text_transport.py`, `test_workflow_discovery.py`,
  `test_execution_guidance.py`, `test_execution.py`,
  `test_scientific_workflow.py`: real stdio representation/identity, no-admission
  negatives, legacy compatibility and unchanged launch/observation bounds.
- `test_structure_analysis.py`: array provenance, explicit unknown association,
  coordinate/output/hash regression and unchanged geometry definitions.

Protected evidence paths are relative to the unattended campaign root, not
public transcript copies:

| Evidence | SHA-256 |
|---|---|
| `v54-complex-helper-repair-r1/receipt.json` | `f4594091306569b720c014c668ab9adfbb2601c148d2adea53415e05799262f5` |
| `v54-study-text-repair-r1/receipt.json` | `9f8324c4cc78e728717f299844d4b5b32ba3ca05357b00f478c769e38c217b1d` |
| `natural-v54/scientist-02/terminal-browser-r1/receipt.json` | `6b8f02be717de3bb289fa43879d8028c393ea006742a4347a4192fcf25a05582` |
| `natural-v54/scientist-03/terminal-browser-r1/receipt.json` | `290ea878a01b7306d34d163ab087c591f262620c71854fdd32da0dd43ad0af23` |
| `v54-assigned-owner-handover/capture-r1/scientist-02/archive-sha256.json` | `3101100ecbfbe985a479487962cb5607382a95e6835c8e06e96c99589b990ce1` |
| `v54-assigned-owner-handover/capture-r1/scientist-03/archive-sha256.json` | `8f74e45b22eacdc76ed60fd77948857e738c37ba7f91ae1534cf1c8f69b928db` |

Both owner archives include full chats, provider/config identities, local
executions, exact owner registries, original failures and zero-active readbacks.
02 has eight history rows: four model operations and four upload operations,
not eight inferences. Full output archives contain250 and6 files respectively.
A preliminary observer GET without the normal browser request headers returned
HTTP200 with an SSE `Illegal request`; that harness response is preserved and
not treated as a valid status. The subsequent ordinary browser-compatible
readback and actual browser terminal evidence establish the states above.

This is a source candidate plus retained-output proof. An immutable installed
successor gate and new uncoached natural trials remain required. No cloud
lifecycle changes were performed by this lane.
