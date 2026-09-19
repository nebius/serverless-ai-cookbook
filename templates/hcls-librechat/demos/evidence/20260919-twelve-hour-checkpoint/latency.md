# Customer wait and latency — retained evidence

Evidence as of 2026-09-19T06:04:00Z. No new requests; no readiness verdict.

Only top-level requests appear in this table. Child operations are separate in JSON. Values are seconds.

| App | Requests | Completed timing n | End-to-end median / p95 / max | Queue-before-activation median (n) | Activation span median (n) | Execution median |
|---|---:|---:|---|---|---|---:|
| alphafold3 | 11 | 11 | 74.115 / 208.972 / 208.972 | unknown (0) | unknown (0) | 73.950 |
| altumage | 22 | 20 | 2.185 / 3.454 / 4.886 | 0.157 (20) | 0.733 (20) | 1.028 |
| bindcraft | 6 | 6 | 1794.091 / 8395.248 / 8395.248 | unknown (0) | unknown (0) | 1793.628 |
| boltz2 | 113 | 111 | 33.362 / 86.450 / 118.924 | 0.047 (111) | 0.411 (111) | 32.602 |
| boltzgen | 13 | 13 | 849.653 / 1198.009 / 1198.009 | unknown (0) | unknown (0) | 800.600 |
| cosmos3-lerobot-augmentation | 9 | 9 | 187.442 / 610.999 / 610.999 | unknown (0) | unknown (0) | 180.722 |
| cosmos3-nano | 32 | 32 | 62.805 / 312.102 / 462.763 | 0.084 (28) | 42.955 (28) | 17.621 |
| diar-streaming-sortformer-4spk-v2-1 | 4 | 4 | 34.217 / 61.995 / 61.995 | 0.050 (4) | 0.252 (4) | 33.743 |
| diffdock | 108 | 88 | 9.025 / 16.763 / 24.152 | 0.089 (88) | 0.751 (88) | 8.076 |
| esmfold2 | 45 | 45 | 92.902 / 391.954 / 1325.285 | unknown (0) | unknown (0) | 92.603 |
| esmfold2-fast | 223 | 223 | 93.957 / 115.276 / 409.125 | unknown (0) | unknown (0) | 93.459 |
| evo2-40b | 88 | 64 | 8.790 / 26.811 / 31.094 | 0.047 (64) | 0.562 (64) | 7.433 |
| genmol | 77 | 72 | 1.837 / 3.344 / 7.601 | 0.042 (72) | 0.557 (72) | 1.079 |
| magpie-tts-multilingual-357m | 7 | 7 | 11.873 / 29.287 / 29.287 | 0.069 (7) | 0.441 (7) | 11.587 |
| molmim | 97 | 96 | 3.551 / 9.474 / 13.238 | 0.059 (96) | 0.650 (96) | 1.774 |
| mosaic | 10 | 10 | 292.762 / 460.615 / 460.615 | unknown (0) | unknown (0) | 319.513 |
| msa-search-pdb70 | 40 | 40 | 3.792 / 5.866 / 6.835 | 0.055 (40) | 0.427 (40) | 3.062 |
| nemotron-speech-en-0-6b | 9 | 6 | 28.237 / 31.412 / 31.412 | 0.063 (6) | 0.500 (6) | 27.629 |
| nemotron-speech-multilingual-0-6b | 118 | 114 | 1.905 / 25.477 / 32.842 | 0.040 (114) | 0.418 (114) | 1.354 |
| nv-reason-cxr-3b | 100 | 100 | 1.728 / 4.895 / 25.380 | 0.050 (100) | 0.568 (100) | 0.993 |
| nv-segment-ct | 54 | 54 | 5.782 / 10.434 / 13.216 | 0.046 (54) | 0.583 (54) | 5.086 |
| openfold2 | 61 | 60 | 2.913 / 6.866 / 13.260 | 0.046 (60) | 0.414 (60) | 2.175 |
| openfold3 | 105 | 105 | 12.439 / 28.110 / 31.441 | 0.050 (105) | 0.533 (105) | 11.688 |
| openfold3-openbind | 14 | 14 | 84.565 / 3947.407 / 3947.407 | unknown (0) | unknown (0) | 84.465 |
| parakeet-realtime-eou-120m-v1 | 9 | 7 | 144.404 / 370.744 / 370.744 | 0.051 (6) | 0.510 (6) | 159.335 |
| phenoage | 21 | 19 | 1.144 / 7.229 / 7.229 | 0.052 (19) | 0.482 (19) | 0.517 |
| proteina-complexa | 15 | 15 | 258.036 / 619.702 / 619.702 | unknown (0) | unknown (0) | 257.564 |
| proteinmpnn | 414 | 414 | 1.826 / 5.600 / 13.915 | 0.055 (414) | 0.499 (414) | 1.079 |
| protenix-v2 | 12 | 12 | 141.380 / 308.581 / 308.581 | unknown (0) | unknown (0) | 140.990 |
| qwen3-8b | 180 | 180 | 1.904 / 69.562 / 291.259 | 0.050 (180) | 0.571 (180) | 1.194 |
| rfdiffusion | 9 | 9 | 113.211 / 228.918 / 228.918 | unknown (0) | unknown (0) | 112.891 |
| sdxl | 36 | 36 | 3.564 / 6.537 / 253.414 | 0.046 (36) | 0.397 (36) | 2.845 |

The table includes terminal failures as experienced by customers; JSON additionally separates outcomes, exact latest-runtime evidence, different/historical identities and unknown identities. Use those strata before comparing runtimes. Queue/activation phase counts and missing values are in JSON.

Worker-state evidence: `{"ready_worker_before_acceptance": 605, "unknown": 1457}`.

## Runtime-stratified terminal requests

Compared only with the supplied dated baseline. Image-only is not full release identity. Inputs differ; failure timing is not evidence of faster inference. Unknown identities remain in JSON.

| App | Identity evidence | Service outcome | Requests | End-to-end n / median / p95 |
|---|---|---|---:|---|
| alphafold3 | exact_latest_execution_identity | succeeded | 11 | 11 / 74.115 / 208.972 |
| altumage | exact_latest_image_only | succeeded | 16 | 16 / 1.896 / 4.886 |
| bindcraft | exact_latest_execution_identity | succeeded | 6 | 6 / 1794.091 / 8395.248 |
| boltz2 | exact_latest_image_only | succeeded | 40 | 40 / 31.731 / 33.814 |
| boltzgen | different_execution_identity | failed | 3 | 3 / 75.370 / 611.401 |
| boltzgen | different_execution_identity | succeeded | 7 | 7 / 952.701 / 1198.009 |
| boltzgen | exact_latest_execution_identity | succeeded | 2 | 2 / 740.547 / 851.632 |
| cosmos3-lerobot-augmentation | different_execution_identity | succeeded | 4 | 4 / 287.494 / 610.999 |
| cosmos3-nano | exact_latest_image_only | succeeded | 12 | 12 / 43.157 / 462.763 |
| diffdock | exact_latest_image_only | succeeded | 24 | 24 / 8.638 / 18.086 |
| diffdock | historical_or_different_image | succeeded | 16 | 16 / 8.532 / 21.177 |
| esmfold2 | exact_latest_execution_identity | succeeded | 44 | 44 / 92.487 / 194.334 |
| esmfold2-fast | exact_latest_execution_identity | succeeded | 223 | 223 / 93.957 / 115.276 |
| evo2-40b | exact_latest_image_only | succeeded | 32 | 32 / 13.364 / 28.929 |
| evo2-40b | historical_or_different_image | failed | 8 | 8 / 8.283 / 10.664 |
| evo2-40b | historical_or_different_image | succeeded | 24 | 24 / 8.254 / 17.445 |
| genmol | exact_latest_image_only | succeeded | 27 | 27 / 1.741 / 2.657 |
| genmol | historical_or_different_image | succeeded | 10 | 10 / 3.073 / 7.601 |
| molmim | exact_latest_image_only | failed | 6 | 6 / 1.997 / 3.382 |
| molmim | exact_latest_image_only | succeeded | 6 | 6 / 2.107 / 2.816 |
| molmim | historical_or_different_image | succeeded | 5 | 5 / 4.915 / 7.643 |
| mosaic | exact_latest_execution_identity | succeeded | 9 | 9 / 320.003 / 460.615 |
| nv-reason-cxr-3b | exact_latest_image_only | succeeded | 59 | 59 / 2.292 / 15.244 |
| nv-segment-ct | exact_latest_image_only | succeeded | 4 | 4 / 5.417 / 5.789 |
| nv-segment-ct | historical_or_different_image | failed | 1 | 1 / 3.954 / 3.954 |
| nv-segment-ct | historical_or_different_image | succeeded | 1 | 1 / 5.775 / 5.775 |
| openfold2 | exact_latest_image_only | succeeded | 7 | 7 / 5.334 / 13.260 |
| openfold3 | exact_latest_image_only | succeeded | 56 | 56 / 12.352 / 23.277 |
| openfold3-openbind | different_execution_identity | succeeded | 10 | 10 / 84.565 / 401.506 |
| openfold3-openbind | exact_latest_execution_identity | succeeded | 3 | 3 / 73.814 / 238.222 |
| proteina-complexa | different_execution_identity | succeeded | 1 | 1 / 619.702 / 619.702 |
| proteina-complexa | exact_latest_execution_identity | succeeded | 9 | 9 / 347.505 / 492.378 |
| proteinmpnn | exact_latest_image_only | succeeded | 33 | 33 / 2.087 / 4.606 |
| proteinmpnn | historical_or_different_image | succeeded | 18 | 18 / 2.411 / 5.076 |
| protenix-v2 | exact_latest_execution_identity | succeeded | 10 | 10 / 135.324 / 308.581 |
| qwen3-8b | exact_latest_image_only | failed | 13 | 13 / 1.061 / 70.407 |
| qwen3-8b | exact_latest_image_only | succeeded | 123 | 123 / 2.023 / 72.415 |
| rfdiffusion | exact_latest_execution_identity | succeeded | 9 | 9 / 113.211 / 228.918 |
| sdxl | exact_latest_image_only | succeeded | 35 | 35 / 3.554 / 5.464 |

## Interpretation

- Latest means the explicitly supplied captured baseline, never the newest successful request or inferred image.
- Queue-before-activation is the operation-worker dispatch boundary; activation spans occur for hot requests too.
- Legacy cold_start_seconds is accepted-to-ready and includes queue/capacity; it is not model cold-start time.
- Worker state requires matching immutable Pod UID and timestamp-bracketing observations with the same container ID, image ID, restart count and readiness timestamps. Low traffic proves nothing.
- A new worker during a request is not an empty-node or uncached-weight benchmark. Warm worker is not a cache-tier claim.
- Started-to-completed includes the server execution/result path, not measured GPU-active time.
- For scientific batch, started-to-completed spans the orchestration plus all stages, Kueue waits, pulls and artifacts. Its short pre-execution wait is not the total GPU queue delay.
- Missing phases stay unknown. Negative durations are invalid, never clipped to zero; overlapping composites are not summed.
- Success and failure latencies are separated; distributions span varied input sizes and are not controlled speedup estimates.
- Generic upstream errors remain unknown causes; preemptible GPU placement alone does not establish preemption delay.
- Client elapsed includes receipt/poll/transport time. Scientific stage overlap is not added to parent wall-clock time.
- Operation/stage files changed since the aggregate hash are excluded, not silently reinterpreted. Rerun the aggregate to include later completions. Pod captures enrich exact-UID evidence independently. Observation-directory time and retained file mtime bound capture time; undated captures are not used.
