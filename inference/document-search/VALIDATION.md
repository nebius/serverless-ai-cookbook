# Validation

## Recorded GPU runs

On November 13, 2026, three preemptible Serverless Jobs ran an earlier version of this recipe (`f1d8ca0`). The main Job and the final resume used the default `MAX_NEW_DOCUMENTS=0`. Only the first recovery attempt set a limit of 600. [Effective launch settings](docs/job-results/default-flow/launch-settings.json).

| Attempt | New documents | Reused documents | Remaining | Saved chunks |
| --- | ---: | ---: | ---: | ---: |
| Main flow with default settings | 1,000 | 0 | 0 | 1,970 |
| Optional first attempt | 600 | 0 | 400 | 1,206 |
| Optional fresh Job | 400 | 600 | 0 | 1,970 |

The main Job printed `Finished: 1,000 new, 0 reused, 0 remaining.` and generated the search JSON and HTML in the same attempt. The optional test used a separate fresh prefix: one Job saved 600 documents, then a new default Job printed `600 documents already saved, 400 to go.` and finished the remaining 400. All reports match the same input/model fingerprint. This controlled application stop was not a provider preemption. [Main report](docs/job-results/default-flow/main.json), [first 600](docs/job-results/default-flow/limited-600.json), [remaining 400](docs/job-results/default-flow/resumed-400.json).

## Runtime and input

Each Job used one NVIDIA L40S, `pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime`, PyTorch 2.7.1+cu126 and Transformers 4.51.3. The model was `Qwen/Qwen3-Embedding-0.6B` at revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, with normalized 1,024-dimensional float16 vectors, last-token pooling, a maximum batch size of 16 within each document, and paragraph-aware 160-word chunks.

The pinned input contains 1,000 distinct Dolly reference passages and produces 1,970 chunks. Its text volume and provenance are recorded in the unchanged [corpus manifest record](docs/job-results/corpus.json); the worker validates the pinned data before indexing.

## Measured phases

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

The index application total includes model startup, embedding, saving, scanning and small application overheads. It excludes dependency setup, input preparation, later search and report uploads. Provisioning/image-pull time is recorded separately as coarse status observations, which include polling delay and can include work already performed. [Lifecycle observations](docs/job-results/default-flow/lifecycle.json). These measurements are not runtime promises.

## Search

The main Job used the default query, “What is stalemate in chess?” The relevant stalemate passage ranked first, similarity 0.8240; the next result scored 0.5424. Results link to the pinned source dataset records. [Search JSON](docs/job-results/default-flow/search.json), [HTML report](docs/job-results/default-flow/search.html). This is an executed example, not a retrieval benchmark.

## Local checks and execution scope

These archived cloud results predate the move to this repository. The current Job fetches its worker from this repository and links each search result to its dataset viewer row and pinned source. The updated worker has been tested offline. A fresh GPU run of this revision is pending. Run its offline suite from this directory with `python3 -m unittest discover -s tests`. To include the full-corpus fixture recovery test, prepare the pinned input first with `python3 scripts/prepare_job_data.py`.

## Cleanup

All three test Jobs completed and their managed compute was removed. The temporary SecretStash copy was deleted; the pre-existing S3 access key and bucket were preserved. New index and search artifacts remain in Object Storage. [Cleanup record](docs/job-results/default-flow/cleanup.json).
