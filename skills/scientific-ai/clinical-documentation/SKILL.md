---
name: clinical-documentation
license: Apache-2.0
description: Turn an uploaded consultation recording or transcript into an evidence-linked German Arztbrief or English medical report draft, with a separate list of unclear details and suggested follow-up questions. Use for clinical documentation, not diagnosis, prescribing, or hospital discharge summaries without the required records.
---

# Clinical documentation

Produce three deliverables: the unchanged transcript, a report draft with source
references, and separate uncertainties/suggested questions. Do not silently
rewrite the transcript, correct unclear medication names, infer normal findings,
or turn a doctor's unanswered question into a negative answer. Suggestions are
not facts to insert in the letter. These models and this workflow have not been
clinically validated; a clinician must review the draft before using it in a
record. Do not claim that a question was never asked just because it is absent
from the recording.

Keep source attribution separate from topic headings. Patient-reported symptoms,
self-measured pulse/weight and recalled results are not clinician-observed
findings. A clinician's recap or proposed examination does not establish that
an examination occurred. The existing extraction and contextual-review passes
record `source_attribution`; the report labels agreement as patient-reported,
clinician-recorded observation, clinician statement or teaching/narrative
context. Missing or conflicting labels remain explicitly unclear. These are
automated source classifications, not clinically verified speaker identities.
Preserve the exact source passages and surrounding dialogue, including doubt,
conditions and uncertain names. Do not reclassify an old report from its heading
or add attribution to a retained output; older documents without this metadata
remain unclassified when separately inspected.

## Uploaded audio or an existing transcript

Use the bundled executable workflow when the client provides a file-capable
execution environment. Resolve the actual current user's attachment to a local
file; an attachment label or remote path is not audio. Use the user's ordinary
platform credential through `FS2_API_KEY` or `FS2_API_KEY_FILE`, never in tool
arguments, source, chat, or output. `FS2_BASE_URL` selects the platform origin.
The platform key needs access to the appropriate Nemotron speech App, with
catalog, inference, operations/result and artifact-write scopes. Choose the
report model explicitly; the tested profile is Qwen-235B on Nebius Token Factory.
The executor operator configures its provider credential separately and does
not disclose that credential in chat or to MCP clients.

```bash
uv run /path/to/clinical-documentation/scripts/clinical_report.py \
  --audio /user-workspace/consultation.wav --language de \
  --report-provider https://api.tokenfactory.nebius.com/v1 \
  --report-model Qwen/Qwen3-235B-A22B-Instruct-2507 \
  --output /user-workspace/consultation-report
```

English uses `--language en`. The helper selects English Nemotron for English
and multilingual Nemotron for German; it verifies the Apps are visible to the
current key. To reuse a completed transcription, use `--transcript file.txt`
(or ASR JSON with `text`) instead of `--audio`. For finalized uploaded audio,
use `--artifact audio-reference.json`. It contains only the immutable artifact
reference, not a URL or file bytes. Do not submit the same audio again just to
change the report model.

The helper uploads real bytes outside model arguments, handles async operations
and long-result artifacts, extracts facts in overlapping numbered source
segments with schema-constrained generation, builds exact citations itself,
performs an automated contextual fact review, and renders those facts into the
report. It keeps excluded candidates for inspection.
Literal citations and a second model pass do not prove medical correctness.
Review important facts against the transcript and, where unclear, the recording.

Deliver `report.md`, `follow-up.md`, and `transcript.txt` as downloadable files;
`document.json` carries structured facts and exact source character offsets.
`review.md` makes withheld candidates readable; `review.json` retains their
structured evidence. Inspect these alongside the report: the automatic reviewer
can reject a correct fact. Empty report sections mean no entries were assigned,
not that the consultation lacked that information. `run.json` and `calls/`
retain provenance, model usage and operation IDs. These files contain sensitive
content: use the existing per-user workspace, not public repository storage.
Successful extraction is not proof of completeness. Deliver the review queue
alongside the report rather than hiding omitted candidates. Suggested questions
can repeat answered points or contain speculative rationales; review them before
using them with a patient. Do not present them as a validated clinical checklist.

## Reproducible study measurements and coverage language

In a durable whole-study plan, an explicitly requested unsupported-source test
may set `allow_no_report: true` on that individual `kind: "clinical"` stage.
The default remains false. This permits only the existing typed
`no_supported_clinical_facts` outcome, not provider, storage, malformed-output or
unknown-admission failures. It preserves the unchanged `transcript.txt`,
`review.json`, `coverage.json` and `run.json` and publishes
`clinical-outcome.json` plus `clinical-outcome.md`. Later declared analysis and
publication can then continue without another draft or user continuation.
Normal positive drafts also publish these two outcome files. Use the guaranteed
`clinical-outcome.md` for downstream reporting when either outcome is allowed;
do not promise `report.md`, `document.json` or questions from a no-report case.
No report is not evidence of no illness or no important source information.
Do not add this permission to positive cases merely to hide an unexpected failure.

Durable clinical outcomes include deterministic source-selection measurements
from the existing v11 reader, not just a completed flag. Include that measured
outcome in the study report. Positive clinical stages register their unchanged
transcript, draft, structured document, review queue, questions, coverage and
run provenance for final Runs downloads under step-qualified names; permitted
negative stages register only the files actually produced. Provider-call and
checkpoint internals are not automatically published. These downloads and
literal-span counts do not establish speaker attribution, clinical meaning or
completeness; retain the reported source-selection gaps and review limitations.

For a complete multi-case study, prefer one deterministic assembly step after
the full transcripts and any clinical documents have been retrieved:

```bash
python /app/skill/clinical-documentation/scripts/study_report.py assemble \
  --plan /workspace/study/measurement-plan.json \
  --output /workspace/study/measurements/complete-study
```

The plan is `{"schema":"clinical-study-plan/v1","cases":[...]}`. Each case has
a unique filename-safe `id`, the actual full-text `transcript` file, and optional
`document` (v11 JSON), `reference` (human text) and `source_spans` (exact probes).
Relative input paths resolve beside the plan. Optional `provenance` can record
`operation_id`, `model_id`, `clinical_job_id`, `language` and boolean
`transcription_reused`; these are explicitly declared identities, not a new
service verification or an inferred fresh ASR call. Do not put keys or URLs in
the plan.

The helper counts accepted facts from the canonical `facts` and `source_phrases`
fields, preserves fact IDs for exact source probes, and produces the final
study table itself. Do not write a competing `source.text` walker or recalculate
its counts in another report. Source selection is measured whenever a document
is supplied, **even without a human WER reference**. No document means the fact
count is unknown, not zero. No WER reference means WER is unmeasured, not zero.
Case and declared edge punctuation are already ignored by the pinned scorer:
they cannot on their own explain a measured error. Literal probe absence is not
proof of semantic omission; do not turn equivalent wording into a missing fact.

Return the helper's `report.md`, `measurement.json` and
`completion-manifest.json`, which lists the verified hashes/sizes of all
retained input and measurement files. The manifest is written only after every
listed artifact has been read back. Reusing the same plan, helper and unchanged
input bytes resumes its own interrupted output or verifies a completed output;
changed historical files are rejected, never overwritten. A deterministic
measurement bundle is not a new clinical report or proof of completeness.

For a speech comparison, use the bundled offline helper rather than writing one
normalizer in a scratch command and saving a different scoring script:

```bash
python /app/skill/clinical-documentation/scripts/study_report.py wer \
  --reference /workspace/study/human-reference.txt \
  --hypothesis /workspace/study/actual-transcript.txt \
  --output /workspace/study/measurements/new-case
```

It emits `measurement.json` and `report.md` from the **same** calculated counts,
with exact normalization ID, helper SHA-256, input hashes and unchanged copies
of inputs and `helper.py`. Quote those recorded N/S/D/I/WER values; do not
recount them in prose. Keep the denominator and normalization alongside every
comparison. This method retains uncertain inner words, drops the specified
annotation markers, and strips a declared set of edge punctuation, including
standalone `--`. It does not expand contractions or map numbers. Other pinned
scorers and normalization choices are separate regimes: retain their original
outputs, name the difference, and never silently change an earlier denominator.
WER is lexical agreement, not medication/negation accuracy or clinical quality.
Inspect those issues separately against actual reference passages and audio.

After retrieving a v11 report's exact `document.json` and `transcript.txt`, run:

```bash
python /app/skill/clinical-documentation/scripts/study_report.py coverage \
  --document /workspace/study/clinical/document.json \
  --transcript /workspace/study/clinical/transcript.txt \
  --output /workspace/study/measurements/new-source-selection
```

The helper verifies literal source offsets and counts **accepted selections**,
cited context, and review excerpts separately. Optional `--source-spans` takes
a JSON list of exact transcript `{start, end, quote}` ranges for an explicitly
bounded check; it reports `selected_phrase`, `cited_context_only`,
`review_excerpt_only`, or `source_only`, not clinical entailment. A keyword in
the report's repeated full context or review queue is not an accepted fact.
One selected phrase does not cover every fact in its segment. Even all probe
hits or all segments selected do **not** establish completeness. Do not turn
"16 items located" into "no important omissions" or "all facts supported".

Report only the measured scope: e.g. "X/Y declared source segments contain at
least one accepted literal selection; completeness remains unassessed." For
each meaning-sensitive comparison, cite the actual human-reference passage,
the unchanged ASR passage and the accepted fact ID (or context/review-only
location). Retain disagreements, uncertain speakers, conditions and unanswered
questions. A source-anchored statement can still repeat an ASR error or omit a
qualifier; source equality does not prove clinical correctness. Keep the
automated review's claims separate from independent checks. Do not rewrite the
clinical draft or transcript to make the comparison pass.

These commands are local analysis, not new inference. Use a **new** measurement
directory; completed outputs are immutable. Re-run its retained `helper.py`
with retained inputs into another new directory for exact reproduction. Keep
source text and review output in the user's protected workspace. If the exact
helper is absent from an older image, state that limitation instead of claiming
it ran or silently substituting an unpinned scorer.

For the clinical draft workflow (not offline measurement commands), rerun the
**same command and output directory** to resume a pending operation without
retranscribing. A new input, language, prompt or model needs a new output
directory. A completed directory is immutable. Empty audio/transcripts, terminal
model errors and truncated JSON are explicit incomplete runs, not blank letters.
Report the saved operation ID when blocked. Do not repeatedly create new runs
or change deployment settings. There is no new access policy in this skill.

`no_supported_clinical_facts` is an explicit **incomplete/no-report** outcome,
not a provider outage or a statement that the patient has no findings. The
workflow found no supported facts or retained review excerpts from which to
render a draft. Inspect the unchanged transcript and `review.json`; check for
non-consultation/insufficient material and obtain fuller source if appropriate.
Resuming the same source does not add evidence. Do not fabricate a blank or
normal report, correct the source, or automatically create a new draft. Older
jobs may show only generic `ValueError`/incomplete; their original receipts are
not retrospectively rewritten by this change.

## MCP-only client

In the Scientific AI LibreChat deployment, prefer the `scientific-demos`
bridge when present. For an existing full transcript, use
`clinical_report_from_workspace` with the exact workspace-relative `.txt` path
or original ASR `.json` file. The server reads the bytes and records their size
and SHA-256 in `input_provenance`; verify these against the saved input before
claiming full-recording coverage. Do not shorten, reconstruct or hand-copy a
long transcript into tool arguments. `clinical_report_from_transcript` remains
for actual user-supplied short text, not model-generated summaries of ASR.
Both start the same helper with a per-user platform key held by the server. Save its job ID and use
`clinical_get_job`/`clinical_read_output` to retrieve the draft, transcript,
review queue and questions. Each `clinical_read_output` retains the original
bytes as a hash-verified `workspace_file`; read or copy that exact path instead
of guessing private job directories or reconstructing files from chat excerpts.
Keep even empty review/question outputs and check completeness independently.
An earlier report made from substituted or shortened input fails full-source
coverage; preserve it and label any explicitly authorized corrected replay.
For audio or large files use the authenticated
`/demos?tab=clinical` upload panel; an attachment label alone is not transferred
to this tool. After an interrupted job use `clinical_resume_job`, not a new
submission. Missing clinical tools require reconnecting the scientific-demos
MCP server, not exposing credentials or switching to a shared root executor.

If the client only has MCP tools, discover `list_models` and `get_model_schema`.
Use the advertised typed Nemotron transcription tool with a finalized audio
artifact, exact `options.model` and explicit language. Save the operation ID,
poll `get_operation`, then retrieve `get_operation_result`; externalized results
need the normal file/artifact bridge. Never paste audio/base64 into tool calls.

Once the transcript is available as a file, run the bundled helper with
`--transcript` through the client's file executor. A `SKILL.md` does not install
that executor or transfer the MCP user's key to it. If absent, explain this
specific integration requirement; do not claim that the executable report
workflow ran. An agent may prepare a clearly labeled manual draft from an
accessible transcript at the user's request, but must not fabricate helper
validation, source offsets, files or measured results.

## Report models and limits

There is deliberately no small-model default: live tests found important
omissions and wrong citations with `qwen3-8b` and the tested NVIDIA Nemotron Nano.
The current recommended profile is
`Qwen/Qwen3-235B-A22B-Instruct-2507` at
`https://api.tokenfactory.nebius.com/v1`. Configure its credential with
`CLINICAL_REPORT_API_KEY_FILE` (protected secret mount) or
`CLINICAL_REPORT_API_KEY`; `CLINICAL_REPORT_MODEL` and
`CLINICAL_REPORT_BASE_URL` can hold the non-secret defaults above.

Without `--report-provider`/`CLINICAL_REPORT_BASE_URL`, an explicit
`--report-model` selects an authorized platform OpenAI-chat App using only the
platform key. This mode exists, but the tested small cluster model is not a
qualified report profile. The host agent can instead help review a draft; that
does not change which model actually generated the saved report.
Never silently send clinical content to another provider or use its key as the
platform key. Changing models requires quality testing, not just catalog
discovery. The provider comparison results and negative runs are documented in
the solution's `acceptance/clinical-documentation-20260917/README.md`.

The report is a consultation-note/Arztbrief draft, not a discharge summary,
clinical decision, or signed document. Speaker identity is not established by
the default ASR. Do not infer patient/clinician identity from voice alone.
Recorded audio is supported; live microphone capture requires a separate client.
Long transcripts are chunked without truncation. Questions are omitted with an
explicit notice if the complete fact set exceeds the question context budget;
no completeness claim is made for long or multi-encounter recordings. Separate
different encounters before submission.
