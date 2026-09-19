# Natural v52 chemistry, aging and retained-MindEval evidence

As of 19 September 2026, 17:17 UTC. This is a bounded three-persona cohort,
not a platform-wide qualification or two unchanged clean cohorts.

Exact client source `e4005cea9e8dd4429064104a53861e8a877016a9`, image index
`sha256:0c2a60ea79d3a2ff27c3927964ad5ddb95b02c7f21d94a86990b40200a29f182`;
Kimi-K3, low reasoning, 131072 context / 8192 output. Backend189 was unchanged
(`bbcec4d515d7d53cabc10d185d48adb4ddb6435e`, index
`sha256:2e72e6d90e76acdd051e6148a0bb562720cedb8e57744e60d88402a75df71a19`).
Each scientist had its own instance and original account/bucket binding. Each
received one original frozen prompt, with only the `unattended-20260919-r6`
output root changed. No corrective prompt, scientific rerun, key renewal or
limit increase occurred.

| Persona | Durable study | Actual result |
|---|---|---|
| 05 chemistry | `72699ae3-efc0-590d-983f-51b7c3e3f111` | **Failed** in generated GenMol-analysis script after all five hosted calls and four docking analyses succeeded. No final report. |
| 07 aging | `482ff35b-04e9-5f11-84f5-9ae082e1dc20` | Seven phases completed; four fresh calls, independent reference checks, report, and eight actual UI downloads verified. |
| 09 retained MindEval | `a34aa3f9-81ca-5d49-912e-1b7d76b5ab27` | Reuse-only analysis completed; six full records, 126 messages and 30 scores preserved; all 22 helper files downloaded through the actual UI and byte-verified. No fresh consultations or judge calls. |

## Browser closure and waiting

Browsers closed only after a fresh matching study-detail read still reported
`running`, with saved browser state and another detail read immediately before
closure. The selected observer has five offline cases covering response shape,
ID/path mismatch, terminal-before-close and terminal-during-state-save.

- 05 closed at 17:01:24.843 UTC; failed at 17:05:28.044. Accepted-to-terminal
  duration 247.931 seconds. Reopened Runs visibly reported `failed`,
  `an-genmol`, `9/11 phases` and the retained diagnostic.
- 07 closed at 17:01:27.184; completed at 17:04:11.599. Accepted-to-terminal
  duration 168.347 seconds; approximately164.4 seconds after closure.
- 09 closed at 17:04:06.856; completed at 17:04:06.989. Its total study duration
  was4.076 seconds and completion was only0.134 seconds after the closure
  receipt. This is a very narrow observed disconnect interval, not a long
  interruption, process-restart or infrastructure-recovery qualification.

One chemistry detail read returned503 at17:03:41 while its list read returned200
and showed progress. The later separate detail read returned200. Both remain in
evidence; the observation error is not relabelled as a failed docking call or
hidden by a successful retry.

## Independent scientific checks and limits

**Chemistry partial results:** exact four requests used the frozen receptors
and ligand inputs, seeds7/11, four poses each. All16 generated3D poses were
independently rechecked using stereochemistry-preserving atom maps and unfitted
receptor-frame RMSD. The0.237372–40.357847Å range, including poor poses, remains
visible. GenMol returned16 valid canonical-unique molecules; independent heavy
atom counts and QED agree with the retained result. These independent checks
do **not** replace the missing customer report. The four RDKit2D-header warnings
come from the two unchanged experimental reference SDFs read twice; generated
pose conformers were verified3D.

**Aging:** all32 NHANES rows/units and both16-row batches match the original
inputs. PhenoAge uses the declared rounded published coefficient version;
maximum absolute error is3.019806626980426e-14years. AltumAge independently
recomputed all17 predictions using20,318 mapped CpGs and the pinned public
Keras/scaler assets; maximum error is1.55301247417583e-5years. There is exactly
one genuinely matching sample between complete/reversed inputs, with
−5.364418029785156e-7years difference. Four negative predictions remain in the
results. This proves numerical/feature-mapping behavior, not clinical or
population validity. Eight Runs→Workspace→Download-selected-file downloads,
65,665bytes total, exactly match independent stored bytes and published hashes.

**MindEval:** all original JSON bytes and untruncated transcript text match the
six pinned records. Counts derive from the records: two profiles, three
clinicians, five distinct criteria, ten profile×criterion cells,126 messages
and30 supplied scores. Five declared Runs links plus17 additional Workspace
downloads preserve all22 helper files,1,770,897bytes total. Scores remain
descriptive and uncalibrated; no clinical, ranking-significance or fresh-workshop
qualification is claimed.

## Chemistry failure and source-only class repair

The frozen generated script called
`json.loads(sys.argv[sys.argv.index('--inputs') + 1])`. The worker correctly
supplies a **file path**, not inline JSON, so the script raised JSONDecodeError
before molecule analysis. The failed study and script are unchanged.

The existing `molecule-analysis.py` handled docking only. Its additive GenMol
mode now consumes the original request and exact saved result contract:

```text
python molecule-analysis.py --genmol-result RESULT.json --request REQUEST.json --output OUT/metrics.json
```

It emits `metrics.json`, `rows.csv`, `report.md`, then a verified
`completion-manifest.json`. It measures validity, canonical uniqueness, heavy
atoms, QED and Crippen LogP; preserves every invalid/duplicate/underfilled row;
keeps supplied scores separate; records input hashes/runtime metadata; and
does not equate mask tokens with heavy atoms or descriptors with efficacy.
Existing docking behavior remains tested. The worker's separate typed `genmol`
integration removes the need for a new LLM-written parser for this routine.

41 focused helper tests, plus two typed integration tests, pass; Ruff passes.
The source helper was replayed locally against the **unchanged failed study's
retained16-molecule result**. Every canonical SMILES, atom count and QED value
matches the prior independent calculation. Two supplied model scores differ
from recomputation by1.1102230246251565e-16; those differences are reported,
not rounded to zero. An initial private verifier's incorrect exact-zero
assertion was corrected to check the actual subtraction and is disclosed in
the replay receipt. No model call or public study rerun qualified this repair
yet. A successor image still needs installed and unchanged natural acceptance.

## Protected evidence index

`U` is `/home/tux/secure-handoff/scientific-unattended-20260919`; raw payloads,
cookies and credentials remain outside Git. Paths below are relative to `U`.

| Evidence | SHA-256 |
|---|---|
| `natural-v52/scientist-05/capture-r4/study.json` | `ad0c1d3f95a26e2f24ddbe6bbe9d7588bc4fca469ae354abb80a6a53cea2aeef` |
| `independent-v52/scientist-05-partial-numerical-r1.json` | `f656c49d1c8f7f81ea1cb9f24aa3dd9bbb0583c59af05aec46b39a2d419e49fc` |
| `natural-v52/scientist-07/capture-r3/study.json` | `1a9f8dc2f3cf41adde989cf8115633353654aa5a56518d39696e4fe369bf42c0` |
| `independent-v52/scientist-07-numerical-r1.json` | `64b483cf25acfcb85104967ec38c26333e8bb257ec51f53fb20fe2c5850ab5cc` |
| `independent-v52/scientist-07-browser-r1/download-receipt.json` | `ec1f539750743e8693d919730bd6c8267fa4c8e4522d055ee70e75a8a4842f83` |
| `natural-v52/scientist-09/capture-r2/study.json` | `c3bba44f1f1d334e4f9df094685ddf441552c01c306a15060a90e38eaea035ac` |
| `independent-v52/scientist-09-numerical-r1.json` | `c9e6bc299c59a66b0267041bb60ad7036fb5f7834cac796ff9f9dca687ecf62b` |
| `independent-v52/scientist-09-browser-r1/download-receipt.json` | `06dcd6c9b2fcbac641dedab5fec6e770a9550d5ccde5f84380dd849b431037ce` |
| `independent-v52/scientist-09-browser-r1/source-downloads/hash-receipt.json` | `3be75b475c814368c8580dc446dfebeb817da1d337a01203fa21915592202a06` |
| `genmol-analysis-class-repair-r1/independent-replay-receipt.json` | `bc0c4ad4a06f4fd9afc5a693c6f3884555aecc56f51cf5bb4df980af1ab3961a` |

Per-persona `natural-v52/*/binding.json`, `submission-intent.json`,
`submission.json`, `disconnect-r1/` and capture directories retain exact release,
prompt, endpoint, timing and original failures. The reusable private checkers
are `verify_v52_mindeval.py`, `verify_v52_aging.py`,
`verify_v52_partial_chemistry.py`, `check_v52_assigned_browser.py` and
`download_v52_mindeval_sources.py`. No earlier cohort was overwritten.
