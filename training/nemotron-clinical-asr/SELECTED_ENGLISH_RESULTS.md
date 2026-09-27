# Selected existing English model: engineering demonstration

The September 27, 2026 demonstration selected the existing balanced English
checkpoint, not a later corrective model and not the older Nemotron 3.5 pilot.
This is an engineering selection with explicitly retained clinical failures.
No model weights, private bucket locators, patient data or credentials are
distributed by this recipe. Train and evaluate your own approved-data model.

| Identity | Value |
| --- | --- |
| Foundation | `nvidia/nemotron-speech-streaming-en-0.6b` |
| Foundation revision | `ebe59e5a817142986528bbbee5dba8db7b38ed50` |
| Foundation SHA-256 | `283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd` |
| Selected checkpoint SHA-256 | `2a2b1cae8e96d62e83a82351f7d483df01fc28d1d64793ce45a5de514a6c3b5f` |
| Selected checkpoint size | 2,473,031,680 bytes |
| Selected/completed step | 3000 / 3000 |
| Historical training source | `800d4a525ab98016dbca1a1c8cabbb60779ee2ae` |
| Model family | English RNNT; not the 3.5 prompt architecture |
| Native decoding | FP32, greedy-batch, en-US, 560 ms, context `[70,6]` |
| License | NVIDIA Open Model License; review upstream and data obligations |

The public [balanced recipe](BALANCED_TRAINING.md) exposes the reusable training
path. Reproducing its commands on different approved data does not reproduce
these historical scores, source manifests or checkpoint bytes.

| Known evaluation cohort | Clips / groups | Base WER | Selected WER |
| --- | --- | ---: | ---: |
| Clinical development | 239 / 27 conversations | 13.9241% | 10.6804% |
| External role-play | 141 / 2 conversations | 13.1939% | 9.5169% |
| Expanded role-play | 828 / 10 conversations | 12.0952% | 7.0067% |
| General English | 242 / 40 speakers | 2.7618% | 2.6028% |

Expanded role-play relative WER reduction is 42.07%. Medication lexical errors
fell from 12/37 to 9/37 **reference occurrences**, not 37 different medications.
Those are spelling/alignment measures, not clinical factual correctness. Do not
pool the cohorts or imply every utterance improved. These sets were repeatedly
examined during development; they are not fresh final-test evidence, and absence
from upstream pretraining is not proven. The final holdouts remained closed.

The all-828 reference-based AI text review retained two medication errors, one
dose/frequency error and eight negation/meaning errors, with 16 changed and seven
inherited meaningful uncertainties. For example, “Sertraline” became “sexually”
and “three puffs” became “two puffs”; both examples also failed in the foundation.
No clinician adjudication or human listening was performed for this review.
The frozen critical-gate verdict remains **REJECTED**. Later training did not
produce a better qualified replacement; this selection does not rewrite those
results or establish medical safety.

The same selected artifact backs both “fine-tuned” and “fine-tuned + Sortformer.”
Sortformer adds anonymous speaker attribution after recording, not corrected
ASR or verified clinician/patient roles. Deployment qualification and measured
multi-customer capacity are separate from all scores above.
