# German v39 transcript-only cohorts

Recorded 2026-09-19. These are public-client transport/source-fidelity tests,
**not medical accuracy, completeness or clinical-readiness qualification**.
The actionable no-facts error repair below is source-only: it was not deployed
or exercised by these retained v39 jobs. The pending v41 deployment does not
qualify this later source change.

## Frozen client and input

- Workbench source `5dc3e66`, image index
  `sha256:6d6564e60f252404a5975d35157cb601733802757aced5ebd3df81174300fd0b`.
- Scientist08's existing customer endpoint/key/workspace; no endpoint, resource,
  grant or budget changes. No administrator inference credential.
- Planner `deepseek-ai/DeepSeek-V4-Pro-0813`, reasoning low, existing limits.
- Clinical v11, `Qwen/Qwen3-235B-A22B-Instruct-2507` at the unchanged Nebius Token
  Factory provider. Existing per-call budgets and source checks were unchanged.
- Deployed `clinical_report.py` SHA256
  `6ad17908c923e2fe9ab17b89ce9461f543824dc5a4e8c7663b2d24383dfd6323`;
  `document.py`
  `53f0901369b3afdd6a84a4fa9b0e437b2198006af3ddccb895ef4a65badc01c7`.

Two distinct original transcripts were submitted once each using
`clinical_report_from_workspace`, explicit `language=de`, and distinct fixed
idempotency keys/output directories. There was **no new ASR**, source cleaning,
hand correction, provider fallback or second draft to repair an unfavorable
result. Neither cohort replaces the previous English clinical evidence.

| Cohort | Exact input | Original terminal result |
| --- | --- | --- |
| Short non-consultation negative | 162 UTF-8 bytes; SHA256 `ecf9a586ece9c373ba38d721cc9301ddc05e66e8d4b3aa28179dadc63f0c267f` | Job `c2df49d3700a43911a864026eb83a0ae`, 04:09:33–04:09:36 UTC: incomplete, no report; `review.json` records `non_patient`, no facts. |
| Full retained HHU Herzrasen ASR | 4,798 UTF-8 bytes; SHA256 `c0c0aeebaef6383955d8fb4e98d34820d0a90c675302ec6bbb522bab4bb729e8` | Job `9dd9f9606174f072d9aa8ac043fe2be2`, 04:14:30–04:15:13 UTC: completed in 43.66s; 22 literal selections, 8 withheld candidates/excerpts. |

The short source was a 12.5265-second public German MultiMed fragment, not a
patient consultation. It is an insufficient-source negative, not a meaningful
German medical-draft trial. Its three available files were browser-downloaded
and matched the API bytes. No clinical report/document was invented to score.

The full acted [HHU WWSZ/Herzrasen recording](https://media.hhu.de/video/good-practice-wwsz-technik/5b4e0fb9a15939a76a025c06d3fd505f)
is by Heinrich-Heine-Universität Düsseldorf; Olaf Reddemann, Christian Cujovic,
Marlon Jarek; CC BY 3.0 DE. Full audio was extracted/downmixed to 16kHz mono,
without cuts. Its 421.86-second prepared WAV SHA256 is
`573a2c92bf726012808ca1188b4d105c343ef1998297b3d8fc5abbe177182357`.
The retained prior multilingual-Nemotron run binds that audio and the exact
full ASR text reused here. No verified German human transcript/reference
Arztbrief exists: **no German WER or clinical accuracy score is claimed**.

## Full-draft observations, including limits

All seven clinical files downloaded through the actual browser matched the
public API and the requested workspace copies. The complete unchanged source
was bound by the returned input size/hash and run manifest. One ordinary
continuation retrieved the existing completed job after the planner stopped at
an interim running status; it did not submit another draft.

Independent offline checks, using the separately pinned `study_report.py`
from `de1c804`, reproduced JSON and Markdown byte-for-byte. This helper was
**not present in/adopted by live v39**. It verified 22 literal source selections
with adjacent cited context, 13/14 declared segments containing a selection,
and 8 withheld/review excerpts. Segment presence is not factual completeness.

- No phrase from the explicit opening narrator setup (characters 0–225) was
  selected as a patient fact. That setup remains visible inside quoted context.
  This is textual separation, not audio-verified speaker diarization.
- The tentative assessment remained tentative; conditional treatment wording
  remained source context, not an invented prescription.
- Planned examination and blood draw were absent from the **selected plan
  facts**, but retained in context/review. Uncertain onset, rest occurrence,
  previous episode resolution and sleep duration likewise remained
  context-only at their checked source locations. A keyword hit in repeated
  context must not be counted as an accepted or complete clinical statement.
- ASR artifacts remained uncorrected. The 25,679-byte output is an extractive
  evidence/review document, not a polished or complete Arztbrief.
- Generic **Befunde** contains the reported pulse and weight change. Adjacent
  source supports self-report, not a clinician-performed measurement. This is
  a real provenance/category ambiguity for later clinician-reviewed template
  improvement: distinguish reported, observed/measured and proposed findings
  using evidence, never infer that distinction from a heading alone. No live
  artifact or current categorization was silently rewritten for this note.

## Bounded no-facts UX repair (source-only)

In the retained negative, Python raised a descriptive `ValueError`, but
`run.json` retained only the type; the detached worker replaced the reason
with generic incomplete/resume guidance. No report was produced, as intended.

The repair emits the recognized `no_supported_clinical_facts` code with a
fixed public explanation: no facts were extracted, no report was produced,
source/review are retained, and fuller consultation material may be needed.
The worker maps only that code; arbitrary exception text/unknown codes keep
their existing generic projection. Status stays incomplete; no-report/source
fidelity rules, extraction prompts, report provider and budgets are unchanged.
Historical completed/failed artifacts are not migrated. Unchanged-input
idempotency replay does not create a new draft. Automatic retry behavior is
unchanged.

Focused offline tests cover the exact retained 162-byte input with non-patient,
insufficient and zero-fact consultation classifications; real workflow-to-CLI
receipt propagation; retained transcript/review with absent report; no new ASR;
recognized worker-to-public-status handling; replay; and generic/sensitive-text
fallback. Existing clinical and worker lifecycle tests remain required before
source handoff. These tests are not new live/model evidence.

Source verification: **59 Python tests passed**, **19 Node service/router tests
passed**, Ruff passed, JavaScript syntax checks and `git diff --check` passed.

```bash
python -m pytest -q templates/hcls-librechat/skills/clinical-documentation/scripts/test_*.py
node --test templates/hcls-librechat/demos/service.test.cjs templates/hcls-librechat/demos/router.test.cjs
```

## Protected originals and portable hashes

Raw source, tool traces and report text remain in the protected campaign
evidence store, not this note. Paths below are relative to its `browser-evidence/`:

| Receipt | SHA256 |
| --- | --- |
| `scientist-08-herzrasen-v39-final/cohort-completion-receipt.json` | `43fc5b4cc3bc7a774bc15f339f4662dc12780b798e33c6861f0586b7f266d912` |
| `scientist-08-herzrasen-v39-independent/receipt.json` | `a57d9df445e4e75888c3cf7cac1563e60d41867358595072529401653a1d7ac6` |
| `scientist-08-herzrasen-v39-independent/coverage/measurement.json` | `d18e594957ec54b9d3e964d779ad2edad077228e650c91da613e7e8b50a0f119` |
| `scientist-08-german-v39-final/independent-receipt.json` | `2b3e32224ced40c7589ea1a565af35c3aa966d1579f58e6aad2d3ffed54d338a` |

Full report SHA256:
`c71356f2d341ab619bdb39e1428459ecb7b5f5d9bc00977acf4278eeb7d4c26a`.
Original full-cohort prompt SHA256:
`ee604cf70bf78a54599852a778e415e50916df36e18063f43f4b9e6c7af86769`.
Source-only reporting helper SHA256:
`db4eac1c94f689aa93e2540969e5d0cf3443bc8ab028016ab46e056bc9f4d08a`.

Scientist08 was released after completion. Latest-50 caller operation IDs and
the exact tool traces showed no additional native inference; this is not a
full lifetime billing/occupancy audit.
