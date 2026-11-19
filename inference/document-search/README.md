---
title: Build a Document Search Index with a Serverless Job
category: inference
type: cookbook
runtime: Nebius Serverless Job
frameworks: [Transformers, PyTorch, S3]
keywords: [documents, embeddings, search, serverless, preemptible]
difficulty: intermediate
---

# Build a Document Search Index with a Serverless Job

Build a searchable index of 1,000 Wikipedia reference passages from the Databricks Dolly dataset with Qwen3-Embedding-0.6B, save the embeddings to Object Storage, and search the collection by meaning. A single Serverless Job prepares the input, indexes all 1,970 chunks and writes a readable search report. It runs on a lower-cost preemptible GPU. If Nebius reclaims it, the next Job reuses the documents already in your bucket.

## 1. Set up

Start in a terminal on your computer. You need Git, the [Nebius CLI](https://docs.nebius.com/cli/install) 0.12.305 or newer, and a billing-enabled eu-north1 project with L40S GPU quota and an internet-enabled subnet.

```bash
git clone https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/inference/document-search
nebius profile create
```

Complete sign-in and select your project. In the [console](https://console.nebius.com), prepare:

- A private Object Storage bucket and an [S3 access key](https://docs.nebius.com/iam/service-accounts/access-keys) for a service account with `storage.object-editor` access to it.
- A SecretStash secret: open Cryptography → SecretStash → Create secret. Add text entries named `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` with the key values; use Add pair for the second entry. Copy the secret's `mbsec-…` ID. [SecretStash setup](https://docs.nebius.com/mysterybox/secrets/create).
- Your project ID from the project selector’s ⋯ menu → Copy project ID, and a subnet ID from Networking → Virtual Networks → Subnets.

Your account needs permission to create Jobs and read the secret payload (`mysterybox.payload-viewer`, included in `admin`). Replace all `YOUR_…` values below and use a fresh bucket prefix. The file contains a secret reference, not the S3 credentials.

```bash
cat > .env <<'ENV'
export NEBIUS_PROJECT_ID="YOUR_PROJECT_ID"
export NEBIUS_SUBNET_ID="YOUR_SUBNET_ID"
export S3_SECRET_ID="YOUR_SECRET_ID"
export RUN_ROOT="s3://YOUR_BUCKET/document-index-demo-01"
export RECIPE_REF="$(git rev-parse HEAD)"
ENV
source .env
```

Jobs download worker files from `nebius/serverless-ai-cookbook` at `RECIPE_REF`, matching this checkout. Local worker edits aren't uploaded; publish changes and select their commit to test them. For a fork, update the repository URL in `scripts/run_job.py`.

The launcher uses one preemptible NVIDIA L40S GPU, an 80 GiB temporary disk and a one-hour timeout. Review [current prices](https://nebius.com/prices); image and model setup use billable compute too.

Each Job prepares the same pinned passage data automatically. These are reference passages, not full articles; their [provenance and CC BY-SA 3.0 license](worker/data/SOURCE.md) are included.

## 2. Index all 1,000 documents

Submit the Job. The first command checks your settings; the second starts the run.

```bash
JOB_NAME=document-index bash scripts/submit.sh --dry-run &&
JOB_NAME=document-index bash scripts/submit.sh --async
```

Open Serverless AI → Jobs → document-index → Logs. In the original recipe’s November 13, 2026 run, the Job took about five minutes to reach Running and about six minutes from submission to completion. Account and storage setup take additional time. Wait for Completed and check:

```text
Finished: 1,000 new, 0 reused, 0 remaining.
```

The completed index contains **1,000 documents / 1,970 chunks**. The Job also runs the search below and saves its report.

## 3. Search the index

The Job automatically asks:

> What is stalemate in chess?

Open Logs to see the ranked passages and links to the dataset viewer. The [first passage](https://huggingface.co/datasets/databricks/databricks-dolly-15k/viewer/default/train?row=5) explains that stalemate occurs when a player has no legal move and isn’t in check, so the game is a draw.

In Object Storage → your bucket → document-index-demo-01 → outputs, download `search.html` and open it in your browser. `search.json` holds the same passages; the other JSON files record counts and timings. The bucket stays private.

To ask your own question, start a second billed Job on the same `RUN_ROOT` after the first one finishes. It reuses all 1,000 saved documents and embeds only your question. Download the current report first if you want to keep it. The new results replace `outputs/search.html` and `outputs/search.json`.

```bash
JOB_NAME=document-search-question bash scripts/submit.sh --async \
  --env 'SEARCH_QUERY=How does a game of chess end in a draw?'
```

Use a new Job name for each question. Check its logs for **0 new, 1,000 reused, 0 remaining** and the ranked passages.

If you’re finished, skip to [step 4 to clean up](#4-clean-up). Keep the index prefix, `.env` and SecretStash secret if you want to ask more questions or [try recovering a Job](#what-if-the-job-is-interrupted).

## What if the Job is interrupted?

**Each finished document is saved to Object Storage as its own object.** Its complete chunk embeddings survive the container. Submit the workload again with the same input, settings and prefix; it skips saved documents and finishes the rest. The run manifest refuses incompatible data or model settings.

Nebius has an `on-failure` restart policy, which restarts a container that fails inside a running Job. It doesn’t cover preemption, missing capacity at startup, unexpected VM stops, or failures and timeouts during startup. We use `--restart-policy never` here so you can inspect what happened and decide when to resubmit. [Automatic job restarts](https://docs.nebius.com/serverless/jobs/auto-restarts#when-jobs-arent-restarted).

- Wait for the previous attempt to show Completed, Failed, Cancelled or Error.
- Submit a new Job with a new name and the same input, model settings and `RUN_ROOT`.
- Check the log's reused and remaining counts. An unfinished document is recomputed.
- Use one active Job per prefix. Changed input or model settings require a fresh prefix.

### Try it yourself

Use a new test prefix and limit the first Job to 600 documents:

```bash
JOB_NAME=document-index-600 RUN_ROOT="$RUN_ROOT/optional-resume" \
  MAX_NEW_DOCUMENTS=600 bash scripts/submit.sh --async
```

Wait for Completed, then check the log for **600 new, 0 reused, 400 remaining**. Now submit an uncapped Job against that same test prefix:

```bash
JOB_NAME=document-index-resume RUN_ROOT="$RUN_ROOT/optional-resume" \
  bash scripts/submit.sh --async
```

Expect **“600 documents already saved, 400 to go.”** The Job should finish with **400 new, 600 reused, 0 remaining** and **1,000 documents / 1,970 chunks**. Here the Job stops on purpose; this is not a real preemption. Once both test Jobs show Completed, you can [clean up](#4-clean-up) or try the crash test.

## Go further

To test a crash during an unfinished document, use another fresh prefix. This attempt deliberately exits with code 75 during the seventeenth computed chunk:

```bash
JOB_NAME=document-index-crash RUN_ROOT="$RUN_ROOT/crash-test" \
  CRASH_AFTER_CHUNKS=17 bash scripts/submit.sh --async
```

Wait for Failed, then submit without the crash flag:

```bash
JOB_NAME=document-index-crash-resume RUN_ROOT="$RUN_ROOT/crash-test" \
  bash scripts/submit.sh --async
```

Only fully saved documents are reused. Check the recovery Job for Completed and **1,000 documents / 1,970 chunks**. See [worker/durable.py](worker/durable.py) for the pattern and [VALIDATION.md](VALIDATION.md) for actual execution results.

## 4. Clean up

Once a Job shows Completed, its compute has been released. The index and reports stay in Object Storage. To stop an unfinished attempt, use Serverless AI → Jobs → ⋯ → Cancel.

Before deleting resources, check that every Job using them shows Completed, Failed, Cancelled or Error. When you’re finished, delete the prefixes and SecretStash secret you created for this recipe. If you created a dedicated S3 key, delete it under the service account’s Access keys. Keep any keys and buckets you share with other workloads.

## Run with an agent

With the [Nebius skills installed](https://github.com/nebius/skills#install), share this cookbook and ask:

```text
Run the document-search recipe at my checked-out RECIPE_REF with
nebius-cloud-basics and nebius-serverless-jobs in my selected project
and approved GPU budget. Keep credentials in SecretStash. Use the
default Job to index all 1,000 documents, inspect the search result,
and confirm the Job finishes as Completed. Check the first passage
opens in the Dolly dataset viewer. Preserve the index and my other resources.
```
