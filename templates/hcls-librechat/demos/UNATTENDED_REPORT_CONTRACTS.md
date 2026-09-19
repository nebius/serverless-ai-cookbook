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

## Final assembly and cross-domain measurements

The existing `report-assembly.py --manifest PLAN.json --output-dir OUTPUT_DIR`
keeps its `{title, sections:[{title,file,format}]}` contract and existing limits.
Relative files resolve beside the plan. Empty sections and malformed tables
fail before publication. Markdown and CSV still retain original content/order;
they do **not** confer scientific validation on arbitrary narrative.

Four additive deterministic section formats render source-schema measurements:

| Format | Retained input | What is fixed |
| --- | --- | --- |
| `operation-timing` | Native result/operation JSON, optionally `structuredContent` | `elapsed_ms` stays ms and has an explicitly divided-by-1000 seconds field; timestamp intervals and reported GPU reservations remain separate. Missing fields are unavailable. Admission/activation delay is not labelled cold start. |
| `recorded-export` | `scientific-recorded-export/v1` comparison.json | Validates every field's dtype/shape/scalar count and total; reports all, floating, integer and boolean values separately. Metadata arithmetic is separate from the exporter's raw readback. |
| `rgb-statistics` | Producer results with unique roles and `mean_rgb_float64` RGB24 channel triples | Renders each retained channel mean, unweighted RGB mean and optional explicitly supplied weighted proxy. None is called physical luminance or proof of action-label validity. This does not decode the video again. |
| `mindeval-runs` | Saved `{data:[run...]}` records | Counts unique consultations, observed criterion keys, profiles, clinicians and observed profile×criterion cells separately. Missing judgments remain unavailable; duplicate IDs and invalid scores fail. No clinical winner is inferred. |

The assembled report bundle contains exact source copies, original plan, helper,
report, source-bound provenance (including typed measured rows), and a
`scientific-ai/report-artifacts/v1` completion manifest written last. Every
artifact is published through the existing closed-file/readback mechanism.
Identical completed/partial publication is resumable; differing prior bytes are
preserved and cause failure, not overwrite. The durable worker independently
verifies and publishes the whole study after its local stages succeed. Each
user still has their own instance; no new multiuser storage service is added.

For retained evidence, these adapters distinguish 2,951.319835 ms from
2.951319835 s; 6,144 total values from 5,504 floats, 512 integers and128 booleans;
and five observed MindEval criteria from ten profile×criterion cells across
two profiles and three clinicians. These are replay findings, **not defaults or
hardcoded campaign expectations**. Tests cover different counts and missing
data. A natural customer must obtain the measured report and complete manifest
without being told these answers or receiving an operator's method correction.

## Customer-path acceptance recipe

### Structure comparisons

The existing `structure-analysis.py` CLI now also accepts `--request-file` with
the actual retained request JSON. The durable stage must preflight/hash this
optional file like its existing reference, prediction and residue-map inputs.
It records declared seed/sample settings and exact JSON pointers, never a seed
inferred from a filename or returned sample index. Missing request settings
remain unknown; even present settings do not prove the runtime honored them.

The helper writes `report.md` alongside `metrics.json`, `residue-mapping.json`,
`prediction.pdb`/`.cif` and `methods.md`. Every report uses actual computed
counts and explicit units. Globally fitted complex RMSD, independently fitted
chain RMSD, mapped interface contacts, observed residue coverage and model
confidence stay distinct. Poor predictions and unmapped/excluded chains remain
visible. Sequence redesign still requires the existing hash-bound explicit
residue correspondence; no positional or chain guessing is introduced.
Comment-prefixed CIFs and nested OpenFold structure results are supported;
identical extracted samples are not silently deduplicated. Extracted selection
order is not asserted to be the model's native rank or a distinct model call.

For natural acceptance, ask for an actual reference-complex comparison and a
designed-backbone/refold comparison using the retained correspondence. Download
the report and mapping, then independently compare the counts and units with
metrics. A low independent-chain RMSD must not hide a poor complex arrangement;
an index such as `seed7` in a filename must not become a declared request seed.

### Full clinical study

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
