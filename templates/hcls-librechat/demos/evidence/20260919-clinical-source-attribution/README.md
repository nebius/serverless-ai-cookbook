# Clinical source attribution: retained v60 gap and bounded successor fix

The unchanged private-EU v60 scientist08 study completed five phases, delivered
34 hash-verified UI downloads, and preserved both full source transcripts and
the requested no-report negative. Its clinical semantic acceptance remains
**partial**: patient self-reports appeared beneath Findings/Befunde without an
explicit reported-versus-observed classification. Exact quotations and adjacent
context did not resolve that presentation gap.

The retained examples include English fact F0034 and German facts F0004, F0030
and F0033. No original transcript, document, report, fact selection, draft or
study receipt was changed. The original final evidence receipt has SHA-256
`b0085095c76d068157ec994d5d7b5a6ee68c9c4cddf4f18c7c48b9ebbf8818a5`.

## Source change

The existing extraction and contextual-review calls now each declare
`source_attribution`. A source passage can be patient-reported,
clinician-recorded observation, clinician statement, teaching/narrative
context, or unclear. The renderer displays agreement explicitly; absent or
conflicting classifications remain unclear. Neutral section headings no longer
imply that every item is an objectively observed finding. Identical-quotation
deduplication preserves conflicting fact IDs and both pass classifications,
rather than silently retaining the first label.

These are automated classifications, not verified speaker identities or
clinical validity. The same model calls, budgets, literal quotation/offset
checks, medication constraints and bounded follow-up behavior remain. Historical
v11 documents without the new metadata stay unclassified; there is no inferred
retrofit, migration or live repair.

## Offline evidence

- Full clinical helper suite: **95 passed, zero skipped**, including20 new
  attribution cases. Coverage includes the retained short passages, observed
  versus reported/teaching/unclear labels, disagreement, legacy documents,
  uncertain text, exact quotes, unchanged call count and duplicate conflicts.
- Full retained EN/DE document replay:25/24 original facts rendered in memory
  with explicitly unknown attribution; every selected passage and full cited
  context preserved. Original document/transcript/report hashes were unchanged.
- Private replay receipt SHA-256:
  `d32b4094589b8dce12401ce1ab81cf2a2b8b1b7868caea273033c5308184d367`.

No inference, provider/lifecycle action, output-budget change or customer-output
publication was performed for this fix. Successor installed and natural-client
qualification are separate, still required gates. This does not repair the
original v60 outcome or establish clinical completeness.
