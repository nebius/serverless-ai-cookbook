# Natural clinical v57: delivered files, contradictory final chat

Exact runtime source `d7cf50364f80e98efa974200d33dbde7f193e6b8`, image index
`09406d09cbbb38937648e71708c3ecf2655d032abe933e0b18d560bdece11aa8`, backend190.
One uncoached frozen r9 prompt; no followup, live repair, new ASR or model swap.
The planner was Kimi-K3; the explicitly selected clinical draft model remained
Qwen3-235B-Instruct. One dedicated user instance and its original bindings were
preserved.

The five-phase saved Study completed in **124.591 seconds**. Its browser was
closed while running, before completion. It generated two new drafts from
unchanged full English and German transcripts, retained the explicit short
German no-supported-facts outcome, computed WER and published the combined
report. The negative produced no report/document/followup and did not prevent
downstream publication.

All **30 actual final Runs downloads, 349,273 bytes**, matched the final manifest
and independent Object Storage bytes. They include the drafts, unchanged
transcripts, structured documents, review queues, questions, coverage, run
provenance and measured outcomes—not merely operator navigation to private phase
files. All47 phase files were also independently verified.

Literal evidence checks reproduced English32 selected facts/33 cited span
occurrences,19/20 segment presence and14 withheld candidates; German21 facts/21
spans,13/14 segment presence and11 withheld candidates. Every checked citation
matched its source offsets and adjacent context. Segment presence and literal
citations do **not** establish clinical completeness, correctness or speaker
attribution. Self-reported pulse/weight remain categorized as findings; selected
German background includes doctor-question fragments. These limitations remain
visible rather than being relabelled as validated affirmative patient facts.

The planner wrote a WER script. Its saved output independently matched the
frozen deterministic reader under `casefold-annotation-edge-punctuation/v1`:

| Retained hypothesis | Reference tokens | Edit distance | WER |
| --- | ---: | ---: | ---: |
| English Nemotron | 1412 | 262 | 0.18555240793201133 |
| English multilingual | 1412 | 315 | 0.22308781869688385 |
| English Parakeet | 1412 | 341 | 0.2415014164305949 |
| Short German | 25 | 3 | 0.12 |

Full German Herzrasen has no verified reference and correctly has no WER. These
numbers do not measure medical adequacy; the original source/results were not
rewritten to match a helper.

## Preserved customer-facing failure

The final chat said the launch returned `Errno 11 Resource temporarily
unavailable`, asserted that nothing was submitted, and advised resubmission.
That contradicts the persisted completed Study and delivered files. Root's
separate diagnosis found an accepted first call followed by an identical replay
colliding with the phase lock; that repair is a successor source change, not a
retrospective v57 pass.

Verdict: durable execution, source-linked clinical outcome and real30-file
delivery passed; final admission narrative failed. Not clean end-to-end
acceptance, clinical validation or a clinically ready document.

Protected evidence under `U` (private scientific-unattended-20260919 root):

- `independent-v57/scientist-08-final-receipt.json` SHA256
  `3338fe75863b2c8ab7a3568734c05e98c4c33cc9e9af788a1ea9f5f298570dfd`.
- `independent-v57/scientist-08-s3-20260919T202613145154Z/independent-verification.json`
  SHA256 `6e738f38550844a44f51b3aacd8c22f4f30ed74256ab93be73a04b51af4d78e5`.
- `independent-v57/scientist-08-browser-r1/download-receipt.json` SHA256
  `98963341915b8b2bced468bbe89df9e233e8528e0c1f1efae2e62a15066ebec4`.
- Original full messages SHA256
  `8605b42bc6c6d56dc022e8264ca669b4f61c8471ae94441dfa64f8aa55f71851`.

No patient transcript, recording, credential or generated clinical content is
published in this portable note.
