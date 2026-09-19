# Deterministic report stages

Implementation task: `fs2-unattended-report-contracts-r20260919`. These helpers
extend the existing dedicated-user workbench. They do not introduce a shared
LibreChat instance, change model requests or submit inference. Users in one
tenant may deliberately share a bucket; durable stage ownership remains the
workbench worker's responsibility.

## Clinical study assembly

Installed command:

```text
python /app/skill/clinical-documentation/scripts/study_report.py assemble --plan PLAN.json --output OUTPUT_DIR
```

`PLAN.json` must have `schema: clinical-study-plan/v1` and a nonempty `cases`
array. Each case has an `id` and actual `transcript` text file. Optional fields
are `document` (clinical-documentation/v11), `reference` (human text),
`source_spans` (exact literal probe list), and `provenance` with declared
`operation_id`, `model_id`, `clinical_job_id`, `language`, and boolean
`transcription_reused`. Relative inputs resolve beside the plan. Unsupported
fields and missing/contradictory source bytes fail before output publication.

The stage must validate all input paths against its existing workspace policy
before launching; this standalone scientific helper is not a second identity or
authorization layer. Run at most one writer for one stage output directory,
using the existing durable execution ownership. Do not point separate studies
at the same output directory.

Successful stdout is compact JSON:

```json
{
  "schema": "clinical-study-bundle/v1",
  "state": "complete",
  "output": "/workspace/study/measurements",
  "manifest": "/workspace/study/measurements/completion-manifest.json",
  "manifest_sha256": "<actual hash>",
  "case_count": 2,
  "reused_completed_output": false,
  "clinical_validation": false,
  "inference_submitted": false
}
```

The `clinical-study-artifacts/v1` completion manifest lists every artifact's
relative `path`, `sha256`, and `size_bytes`. The worker must verify this manifest
and its listed bytes before publishing its own stage success. The helper's
preparation identity binds the exact plan, helper and input hashes. Re-entry
verifies an existing complete output or resumes its matching partial output;
it never replaces a differing file or adopts an unrelated existing directory.

Files include the deterministic final `report.md`, aggregate `measurement.json`,
per-case measurements, exact input copies, plan and helper. Source selection
and WER are independent measurements. Missing reference/document inputs are
explicit `not_measured` states, not zero-valued results or failed model calls.
JSON WER values are ratios; the report's percent column is explicitly converted.
No cross-language/cross-source ranking, semantic-omission judgment, medical
correctness or completeness is inferred.

## Customer-path acceptance recipe

After root builds and deploys the integrated candidate, use an ordinary user's
dedicated instance and full retained teaching-consultation files. A natural
request should ask for the English/German transcription/report comparison and
downloadable sources/results, without naming helper methods or correcting the
agent's schema. If reusing old ASR, say so in the task and receipt; do not claim
a fresh audio-to-report run. A separate fresh-audio gate can run the existing
ASR/draft stages followed by this same measurement stage.

Verify in the actual browser that the agent's durable plan reaches measurement
and publication without a continuation or operator method correction. Download
the final report, measurement and manifest; independently verify all hashes,
canonical fact counts, source-selection denominators, and N/S/D/I/WER. A full
German draft without a human reference must still have source selection. A
genuine no-supported-facts result must remain a no-report outcome, not a blank
normal letter. Preserve original failed turns, missing measurements, low scores,
review excerpts and clinical limitations. The source tests alone do not qualify
this natural execution path.
