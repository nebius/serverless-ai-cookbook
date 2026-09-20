---
name: clinical-asr-evaluation
description: Compare English or German speech transcripts against a real reference using reproducible WER, CER and strict keyword coverage, then review medications, doses, units, negation and speaker errors separately. Use for clinical speech quality evaluation, not medical approval.
license: Apache-2.0 AND CC-BY-4.0
---

# Clinical ASR comparison

Use `speech-workflows` for transcription, `clinical-documentation` for drafts.
Adapted from NVIDIA's clinical ASR evaluation workflow for our hosted APIs and
EN/DE recordings. It does not invoke NVCF or replace our existing scoring method.

1. Freeze original audio, reference transcript, hypothesis files, language,
   model/runtime IDs, options and operation IDs. Compare the same audio and
   reference across models; translations and different recordings are separate
   experiments. Identify whether the reference is human-checked or generated.
2. Use the existing `clinical-documentation/scripts/study_report.py wer` for
   historical WER comparability. Its versioned normalization preserves numbers;
   do not silently introduce another normalizer to improve scores.
3. For WER plus CER and keyword coverage, run the bundled offline helper:

```bash
python scripts/evaluate.py --reference reference.txt --hypothesis transcript.txt --language de --keywords keywords.json --output metrics.json
```

Run from this skill directory, or resolve its actual installed path. It is
stdlib-only, loads the sibling clinical skill, makes no inference calls and
refuses to overwrite an existing output. `keywords.json` is a reviewed array
of literal phrases from the reference, e.g. `["kein Fieber", "5 mg"]`.
It records source hashes and normalization; keyword misses are lexical misses,
not automatically medication errors. An empty reference is an error, not 0% WER.

4. Review medication names, dose/route/frequency, numeric units, dates, allergies,
   negation, uncertainty and speaker attribution against the reference/audio.
   Record exact source/hypothesis spans and the clinical interpretation **as
   a reviewer assessment**, separate from automatic scores. Detect contradictory
   additions too: exact phrase presence does not prove preserved meaning.
5. Report each recording and aggregate denominators, not an unweighted average
   disguised as corpus WER. Break down language/noise/speaker conditions when
   known. Keep failed, partial and timed-out runs visible, with coverage unknown
   if duration is unavailable. Do not exclude difficult clips to claim a pass.

The helper's `keyword_error_rate` counts missing distinct reviewed phrases;
it is not occurrence-level KER, semantic error rate, or a validated clinical
metric. CER uses the documented normalized character string including spaces.
Don't compare scores from different definitions as if identical. No universal
threshold here certifies a transcript or medical report for clinical use.
