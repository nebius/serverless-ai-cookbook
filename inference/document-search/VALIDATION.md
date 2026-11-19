# Validation

## November 19, 2026 · official recipe

One preemptible Serverless Job fetched the worker from [commit `3eda510`](https://github.com/nebius/serverless-ai-cookbook/tree/3eda510635994954e84a0cd72f0a3b077d3bf8d8/inference/document-search). It used a fresh bucket prefix, the bundled input and model, and the default uncapped document count. The cookbook’s L40S preset had no reported capacity, so this run used one H100 with a $2.50/GPU-hour price ceiling, an 80 GiB temporary disk and a one-hour timeout.

The Job reached **Completed** in 6 min 16 s from creation. Nebius recorded 4 min 44 s from creation to start. The worker measured 90.50 s from bootstrap through uploading the search report. [Job settings and service timestamps](docs/job-results/default-flow/job.json) · [Completion log](docs/job-results/default-flow/completion-logs.txt)

```text
Finished: 1,000 new, 0 reused, 0 remaining.
```

The index contained 1,970 chunks. A separate listing counted 1,000 document objects in Object Storage. The index manifest, indexing report and query result carried the same run fingerprint. For “What is stalemate in chess?”, the first result scored 0.8237 and explained why the game is a draw when the player to move has no legal move and is not in check. All five HTML links matched the viewer rows in the downloaded JSON. [Index report](docs/job-results/default-flow/main.json) · [Search JSON](docs/job-results/default-flow/search.json) · [HTML report](docs/job-results/default-flow/search.html) · [First passage in Dolly](https://huggingface.co/datasets/databricks/databricks-dolly-15k/viewer/default/train?row=5)

| Worker phase | Seconds |
| --- | ---: |
| Source and dependencies | 12.02 |
| Prepare pinned input | 0.80 |
| Load indexing model | 36.54 |
| Embed documents | 23.75 |
| Save document results | 11.64 |
| Scan saved progress on the empty prefix | 0.05 |

Indexing, including model startup and progress storage, took 72.30 s. The 90.50 s worker total also includes preparing the input, loading and running the query, and uploading the reports. The private index and reports were retained. This run used the full batch. The controlled recovery results below come from the earlier L40S runs.

## November 13, 2026 · earlier L40S runs

On November 13, 2026, three preemptible Serverless Jobs ran an earlier version of this recipe (`f1d8ca0`). The main Job and the final resume used the default `MAX_NEW_DOCUMENTS=0`. Only the first recovery attempt set a limit of 600. [Effective launch settings](docs/job-results/2026-11-13/launch-settings.json).

| Attempt | New documents | Reused documents | Remaining | Saved chunks |
| --- | ---: | ---: | ---: | ---: |
| Main flow with default settings | 1,000 | 0 | 0 | 1,970 |
| Optional first attempt | 600 | 0 | 400 | 1,206 |
| Optional fresh Job | 400 | 600 | 0 | 1,970 |

The main Job printed `Finished: 1,000 new, 0 reused, 0 remaining.` and generated the search JSON and HTML in the same attempt. The optional test used a separate fresh prefix: one Job saved 600 documents, then a new default Job printed `600 documents already saved, 400 to go.` and finished the remaining 400. All reports match the same input/model fingerprint. This controlled application stop was not a provider preemption. [Main report](docs/job-results/2026-11-13/main.json), [first 600](docs/job-results/2026-11-13/limited-600.json), [remaining 400](docs/job-results/2026-11-13/resumed-400.json).

### Runtime and input

Each Job used one NVIDIA L40S, `pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime`, PyTorch 2.7.1+cu126 and Transformers 4.51.3. The model was `Qwen/Qwen3-Embedding-0.6B` at revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, with normalized 1,024-dimensional float16 vectors, last-token pooling, a maximum batch size of 16 within each document, and paragraph-aware 160-word chunks.

The pinned input contains 1,000 distinct Dolly reference passages and produces 1,970 chunks. Its text volume and provenance are recorded in the [current corpus record](docs/job-results/corpus.json); the worker validates the pinned data before indexing.

### Measured phases

Seconds measured inside the November 13 containers, rounded to two decimal places:

| Phase | Main 1,000 | Optional 600 | Resume 400 |
| --- | ---: | ---: | ---: |
| Source and dependency setup | 11.40 | 10.24 | 10.11 |
| Pinned data preparation | 0.86 | 1.75 | 0.80 |
| Model startup | 38.20 | 36.58 | 37.55 |
| Embedding | 21.16 | 12.46 | 8.38 |
| Saving results | 10.12 | 6.01 | 3.92 |
| State scan | 0.04 | 0.04 | 4.87 |
| Index application total | 69.92 | 55.37 | 55.00 |

The index application total includes model startup, embedding, saving, scanning and small application overheads. It excludes dependency setup, input preparation, later search and report uploads. Provisioning/image-pull time is recorded separately as coarse status observations, which include polling delay and can include work already performed. [Lifecycle observations](docs/job-results/2026-11-13/lifecycle.json). These measurements are not runtime promises.

### Search

The main Job used the default query, “What is stalemate in chess?” The relevant stalemate passage ranked first, similarity 0.8240; the next result scored 0.5424. Results link to the pinned source dataset records. [Search JSON](docs/job-results/2026-11-13/search.json), [HTML report](docs/job-results/2026-11-13/search.html). This is an executed example, not a retrieval benchmark.

### Cleanup

All three test Jobs completed and their managed compute was removed. The temporary SecretStash copy was deleted; the pre-existing S3 access key and bucket were preserved. New index and search artifacts remain in Object Storage. [Cleanup record](docs/job-results/2026-11-13/cleanup.json).

## Offline checks

All 38 tests passed on macOS Python 3.9.6 and Python 3.14.4, including the full-corpus recovery fixture. To repeat both data preparation and testing from this directory:

```bash
python3 scripts/prepare_job_data.py
python3 -m unittest discover -s tests
```
