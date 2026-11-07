# Policy-quality evaluation for PR 33

Measured November 5–7, 2026. The original full-data training/reload validation remains separate from these results. The [SO-101 README](README.md) and [ALOHA README](../bfl-flux-action-new-embodiment-full-finetune/README.md) summarize the outcomes. No physical robot was operated.

## SO-101 paired simulator evaluation

The original full-data run `pr33-so101-e258-full-1104`, final checkpoint `060000`, supplied the raw and EMA adapters. These policies trained on all 60 recorded episodes and were not used for held-out scoring on those episodes.

| Frozen contract | Value |
| --- | --- |
| Base policy revision | `e2584b2698e3b88368854976e354af87ec9893c6` |
| Raw adapter SHA-256 | `0eb2a428143dd59f7f13600a02fc4a0b6393bf0f201dd29343befac73c369e64` |
| EMA adapter SHA-256 | `8d58e800b01da215295db93c8779aa785bdc058029964120245cc42f9479c04f` |
| State normalizer SHA-256 | `86b5d152c9df39a640248215469c97a3facf240d481ee0e3e29fd185b423e458` |
| Calibration | `leisaac-24d3bcd-to-flux-so101-e2584b2-sim-d7da38e` |
| LeIsaac revision | `24d3bcd3f1e4585740fc79921782c41617237812` |
| IsaacLab revision | `3c6e67bb5c7ada942a6d1884ab69338f57596f77` |
| Simulator/task | Isaac Sim 5.1.0 / `LeIsaac-SO101-PickOrange-v0` |
| Initial-state seeds | 42000–42024, identical physical fingerprints across all three variants |

Each seed ran in a fresh simulator process, seeded before construction. The camera signals, six-channel conversion round trip, original kitchen/robot asset checksums and reset determinism were qualified before policy scoring. Repeated physical states matched exactly; rendered images retained small pixel differences (mean absolute difference about 0.314 front / 0.240 wrist on a 0–255 scale).

The task retained 60 Hz physics with decimation one, up to 7,200 applied actions / 120 simulated seconds. Successful episodes could stop early. The evaluator's wall-pacing cap was 30 Hz; actual wall throughput was slower. Reported wall seconds, simulated seconds and video playback seconds are distinct. At 30 video frames/s, a 7,200-frame timeout video lasts 240 playback seconds.

An orange placement means its plate predicate was **ever met before termination**. Full-task success additionally requires all three placements and the rest pose. This predicate does not require simultaneous or final plate containment. Some inspected final frames showed an orange outside the plate after its placement had been counted. Outcomes and thresholds were preserved without score-based retries or tuning.

| Policy | Ever-met placements | Placement rate, 95% interval | Full-task successes | Task rate, 95% interval |
| --- | ---: | --- | ---: | --- |
| Base | 0/75 | 0% [0, 0] | 0/25 | 0% [0, 0] |
| Raw | 52/75 | 69.33% [56.00, 81.33] | 10/25 | 40% [20, 60] |
| EMA | 39/75 | 52.00% [36.00, 68.00] | 9/25 | 36% [16, 56] |

Intervals use 10,000 percentile bootstrap resamples of the 25 paired seeds, RNG seed 41997. Paired deltas versus base are +69.33 placement percentage points [56.00, 81.33] and +40 task percentage points [20, 60] for raw; +52.00 [36.00, 68.00] and +36 [16, 56] for EMA. Raw and EMA are reported separately; neither was selected as a winner using this test. The all-zero base bootstrap interval is degenerate and is not a population upper bound. This small seed set and simulator-specific calibration do not establish real-robot performance.

All 75 raw initial-state payloads were independently hashed; each seed matched across variants. Child/root outcomes, termination, timing, completion receipts and policy pins were checked. Videos for the predefined seeds 42000–42002 in every variant were hashed, fully decoded, probed for frame count/resolution/rate, and visually inspected, including failed episodes. [Machine-readable results](assets/paired-simulator-quality.json) include every seed outcome, physical fingerprint, policy pin and paired interval.

## Held-out adaptation experiments

New full-budget policies were trained from the pinned base with split manifests frozen before training. SO-101 trained on episodes 0–47 (60,000 microsteps / 15,000 updates); ALOHA trained on 0–39 (3,000 FP32 updates). Only final-budget exports were scored; held-out episodes were excluded from optimization, fitted statistics, checkpoint selection and tuning. SO-101 retained the original base normalizers. ALOHA fitted statistics only on its 40 training episodes; the actual saved index/statistics and sampler episode IDs were checked. Exact numeric whole-trajectory duplicates crossing the split were rejected by the audit. Near-duplicate demonstrations and exposure during base-model pretraining remain unknown, so these are adaptation holdouts, not proof of wholly unseen pretraining data.

Both evaluations used four evenly spaced valid windows per held-out episode, without episode crossing or padded future targets. SO-101 used full observed history, with future commands only as scoring labels, and matched sampling seed 42000 across base/raw/EMA. ALOHA used the pinned upstream `472653eb48419a0f981da2a6605c7be318d6f4f7` evaluator with seed 42000, Cosmos UniPC, four steps, shift 5, guidance 4 and absolute actions. Uncertainty resamples whole episodes (10,000 draws, seed 41998), rather than treating overlapping windows as independent observations.

| SO-101 policy | Mean normalized action MSE | Episode median | 95% episode-bootstrap interval | Paired MSE delta vs base, 95% interval |
| --- | ---: | ---: | --- | --- |
| Base | 0.34148 | 0.33008 | [0.29739, 0.38806] | Reference |
| Held-out raw | 0.22230 | 0.22187 | [0.17957, 0.26710] | −0.11918 [−0.15525, −0.08021] |
| Held-out EMA | 0.21364 | 0.21959 | [0.17715, 0.25128] | −0.12784 [−0.15752, −0.10112] |

SO-101 has 48 windows per variant from held-out episodes 48–59. Its [complete score receipt](assets/heldout-quality.json) includes exact windows, episode distributions, ordered per-channel normalized MSE, absolute-command MSE/MAE and per-channel episode-bootstrap intervals. Angular absolute errors use degrees (MSE in degrees squared); gripper errors use percentage points (MSE in squared percentage points). Normalized target MSE is dimensionless. Do not pool these physical units into a task-success score.

ALOHA has 40 windows from held-out episodes 40–49, with mean normalized MSE **0.0172033**, episode median and per-channel results in its [complete score receipt](../bfl-flux-action-new-embodiment-full-finetune/assets/heldout-quality.json), and 95% episode-bootstrap mean interval **[0.0134984, 0.0214539]**. The 14 ordered raw channels use recorded dataset coordinates; physical units are undeclared. There is no matched zero-shot 14-channel or early-checkpoint baseline, so final error alone does not establish an improvement. Offline error does not measure cup opening.

The first ALOHA scorer failed before scoring because default inference compilation required an absent C compiler. The corrected scorer used `prepare_inference(compile=False)`, consistent with the export's `compile_model=False`; it preserved the model, preprocessing, windows and sampling settings. The original failure was retained as a harness failure. No compiler installation, model selection or test-driven parameter tuning was used.

## Provenance and retained evidence

All training and successful simulator/scorer jobs reached exact `COMPLETED` states. Final model files were independently streamed and hashed before scoring. Evaluation reports were read back from Object Storage and independently recomputed. Policy services were stopped after their clients finished, and owned compute removal was checked separately from terminal job state. Artifacts and images were retained.

| Work | Exact job ID | Object Storage prefix |
| --- | --- | --- |
| SO-101 held-out training | `aijob-e00d5wactmv706fz17` | `runs/pr33-quality-so101-holdout-1105/` |
| ALOHA held-out training | `aijob-e00dyavany59502jh9` | `runs/pr33-quality-aloha-holdout-1105/` |
| SO-101 held-out scoring | `aijob-e00d120g64dgdkce22` | `validation/pr33-quality-so101-score-1106-v1/` |
| ALOHA corrected held-out scoring | `aijob-e00qjc3q8pqzcvcmn9` | `validation/pr33-quality-aloha-score-1106-v2/` |
| Base simulator | `aijob-e00djqhy3rjwn9xz9h` | `validation/pr33-quality-so101-paired-base-1105-v6/` |
| Raw simulator | `aijob-e00gc11w8e63qkmazc` | `validation/pr33-quality-so101-paired-raw-1105-v6/` |
| EMA simulator | `aijob-e00f8900yqv1cpjymj` | `validation/pr33-quality-so101-paired-ema-1105-v6/` |

The audit bucket is `flux-action-serverless-20260925` at `https://storage.eu-north1.nebius.cloud`; access requires the owner's Object Storage permissions. Separate simulator/service source bytes were uploaded with checksum binding and read back before execution; they are outside the training helper's default flow.

| Artifact/source | SHA-256 |
| --- | --- |
| Held-out SO-101 final raw adapter | `91b9be11b860b28450cd82db6700f34c2dfddfb61bfbfbdf6dcff9c905ede6b6` |
| Held-out SO-101 final EMA adapter | `ef4ababfa914a100f5084d027dde51b0407c2cecb738dc7fba7f234bf0b4321c` |
| Held-out ALOHA final BF16 export | `416aa6ed8026ac27ca6c3b3e359e6c332eb55f58da23446eb3feb2fc95e452fe` |
| SO-101 score receipt | `05bcb5d8b5b798e39969af878c94af2359b1916edbff32091255d541c6cb6e76` |
| ALOHA corrected score receipt | `6a2b71b72ad9d000f489df16d7feeeffafc48b2f04c58b80d95f03e8ab488893` |
| Training split overlay | `bf7c93804f7ea595499920af6d8b40df43b24ba486b464e2702d68ee90969f16` |
| SO-101 scorer | `9d6661361145a8157895f40632bd54518850011cef93658932b4a5fbabb7be20` |
| Corrected ALOHA scorer | `039a77a604c9f311e84bdb2dd60912231aa4b181d8aeb252f35a41f42494e244` |
| Simulator evaluator | `9e2e1c714aced3a6884bff683a55664fecbf719ff75882b47c3f0606d3be6975` |
| Policy service | `68a7c93356ad0368b028ad4951eff0a018cebd078b33a9c494473cd79228bcfe` |

**Remaining dependency:** ALOHA cup-opening task success needs an identified matching simulator or robot/operator setup, including camera/joint units, control timing, cup assets and a success predicate. No other task or physical hardware was substituted. Both held-out scorers and all feasible SO-101 simulator comparisons are complete.
