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

Build a searchable index of 1,000 Wikipedia reference passages from the Databricks Dolly dataset with Qwen3-Embedding-0.6B, save the embeddings to Object Storage, and search the collection by meaning. A single Serverless Job prepares the input, indexes all 1,970 chunks and writes a readable search report. It runs on a lower-cost preemptible GPU and can pick up where it left off if interrupted.

## 1. Set up

Run the commands on your computer, from the cookbook folder. You need Git, the [Nebius CLI](https://docs.nebius.com/cli/install) 0.12.305 or newer, and a billing-enabled eu-north1 project with L40S GPU quota and an internet-enabled subnet.

```bash
git clone https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/inference/document-search
nebius profile create
```

Complete sign-in and select your project. In the [console](https://console.nebius.com), prepare:

- A private Object Storage bucket and an [S3 access key](https://docs.nebius.com/iam/service-accounts/access-keys) for a service account with `storage.object-editor` access to it.
- A SecretStash secret: open Cryptography → SecretStash → Create secret. Add text entries named `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` with the key values; use Add pair for the second entry. Copy the secret's `mbsec-…` ID. [SecretStash setup](https://docs.nebius.com/mysterybox/secrets/create).
- Your project ID and the ID of an internet-enabled subnet, available on their console pages.

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

The launcher uses one preemptible L40S AMD GPU, an 80 GiB temporary disk and a one-hour timeout. Review [current prices](https://nebius.com/prices); image and model setup use billable compute too.

Each Job prepares the same pinned passage data automatically. These are reference passages, not full articles; their [provenance and CC BY-SA 3.0 license](worker/data/SOURCE.md) are included.

## 2. Index all 1,000 documents

Submit the Job. The first command checks your settings; the second starts the run.

```bash
JOB_NAME=document-index bash scripts/submit.sh --dry-run &&
JOB_NAME=document-index bash scripts/submit.sh --async
```

Open Serverless AI → Jobs → document-index → Logs. Expect roughly five minutes for provisioning and the image pull before Running, based on our tests; logs can be empty during that wait. Wait for Completed and check:

```text
Finished: 1,000 new, 0 reused, 0 remaining.
```

The completed index contains **1,000 documents / 1,970 chunks**. The Job also runs the search below and saves its report.

## 3. Search the index

The Job automatically asks:

> What is stalemate in chess?

Read the ranked passages and source links in its Logs. The expected first result explains that stalemate occurs when a player has no legal move and isn't in check, and that the game is a draw.

In Object Storage → your bucket → document-index-demo-01 → outputs, download `search.html` and open it in your browser. `search.json` holds the same passages; the other JSON files record counts and timings. The bucket stays private.

## 4. Clean up

Check that `document-index` is Completed. Cancel an unfinished attempt under Serverless AI → Jobs → ⋯ → Cancel. Completed Jobs release their compute; the saved index and reports remain in Object Storage.

Keep the secret and `.env` if continuing to the optional test below. When you no longer need the data, remove only this run's bucket prefix and temporary SecretStash secret. Preserve shared buckets, access keys and networking. Choose new Job names and fresh prefixes when repeating the guide.

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

Expect **“600 documents already saved, 400 to go.”** The Job should finish with **400 new, 600 reused, 0 remaining** and **1,000 documents / 1,970 chunks**. Here the Job stops on purpose; this is not a real preemption. Check both test Jobs are Completed and apply the same cleanup as step 4.

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

Only fully saved documents are reused. Check Completed and **1,000 documents / 1,970 chunks**, then clean up these test Jobs and their prefix. See [worker/durable.py](worker/durable.py) for the pattern and [VALIDATION.md](VALIDATION.md) for actual execution results.

## Run with an agent

With the [Nebius skills installed](https://github.com/nebius/skills#install), share this cookbook and ask:

```text
Run the document-search recipe at my checked-out RECIPE_REF with
nebius-cloud-basics and nebius-serverless-jobs in my selected project
and approved GPU budget. Keep credentials in SecretStash. Use the
default Job to index all 1,000 documents, inspect the search result,
and confirm the Job finishes as Completed. Preserve the saved
index and my other resources.
```
