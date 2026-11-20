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

You need a [Nebius AI Cloud account](https://docs.nebius.com/signup-billing/sign-up) with access to a project that can run paid GPU workloads. Use your project's region if it offers Serverless AI, Object Storage and a compatible preemptible GPU. The Job needs a subnet with internet access. [Regional availability](https://docs.nebius.com/overview/regions)

On your computer, install Git and the [Nebius CLI](https://docs.nebius.com/cli/install) 0.12.305 or newer, then get the recipe:

```bash
git clone https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/inference/document-search
```

Use your existing CLI profile for that project (`nebius profile activate PROFILE_NAME` to switch). If this is your first sign-in, run `nebius profile create` and select the project.

In the [console](https://console.nebius.com), open the same project and prepare:

- A private Object Storage bucket in your project's region and an [S3 access key](https://docs.nebius.com/iam/service-accounts/access-keys) for a service account with `storage.object-editor` access to it.
- One active SecretStash secret for this bucket with two text entries, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Reuse the secret from a previous document-index Job if it’s still active. For a first run, open Cryptography → SecretStash → Create secret and use **Add pair** for the second entry. Copy the secret’s `mbsec-…` ID. [SecretStash setup](https://docs.nebius.com/mysterybox/secrets/create).
- Your project ID from the project selector’s ⋯ menu → Copy project ID, and a subnet ID from Networking → Virtual Networks → Subnets.

Your account needs permission to create Jobs and read the secret payload (`mysterybox.payload-viewer`, included in `admin`).

Run `nebius compute platform list --parent-id YOUR_PROJECT_ID` with your project ID. Choose a platform marked `allowed_for_preemptibles: true` and one of its single-GPU presets. [GPU platforms and presets](https://docs.nebius.com/compute/virtual-machines/types).

| GPU | `GPU_PLATFORM` | `GPU_PRESET` |
| --- | --- | --- |
| H100 | `gpu-h100-sxm` | `1gpu-16vcpu-200gb` |
| L40S (AMD) | `gpu-l40s-d` | `1gpu-16vcpu-96gb` |
| H200 | `gpu-h200-sxm` | `1gpu-16vcpu-200gb` |

We ran the Job live on L40S and H100 GPUs in `eu-north1`. For selected configurations in other regions, offline tests checked the launch arguments only. The launcher selects the PyTorch CUDA 12.8 image for Blackwell GPUs such as B200 and RTX PRO 6000.

Fill in your region, the two GPU IDs and the resource IDs below. Use a fresh bucket prefix. The Job uses `NEBIUS_REGION` to connect to your bucket’s regional S3 endpoint.

```bash
cat > .env <<'ENV'
export NEBIUS_PROJECT_ID="YOUR_PROJECT_ID"
export NEBIUS_SUBNET_ID="YOUR_SUBNET_ID"
export NEBIUS_REGION="YOUR_BUCKET_REGION"
export GPU_PLATFORM="YOUR_GPU_PLATFORM"
export GPU_PRESET="YOUR_ONE_GPU_PRESET"
export S3_SECRET_ID="YOUR_SECRET_ID"
export RUN_ROOT="s3://YOUR_BUCKET/document-index-demo-01"
export RECIPE_REF="$(git rev-parse HEAD)"
ENV
source .env
```

Jobs download worker files from `nebius/serverless-ai-cookbook` at `RECIPE_REF`, matching this checkout. Local worker edits aren't uploaded; publish changes and select their commit to test them. For a fork, update the repository URL in `scripts/run_job.py`.

The Job uses the selected GPU, an 80 GiB temporary disk and a one-hour timeout. You’re billed while the image and model load. [Current prices](https://nebius.com/prices)

Each Job prepares the same pinned passage data automatically. These are reference passages, not full articles; their [provenance and CC BY-SA 3.0 license](worker/data/SOURCE.md) are included.

## 2. Index all 1,000 documents

The commands below follow the current spot price with no GPU-hour price cap. For our November 19, 2026 run, L40S capacity was unavailable in the test project, so we used an H100 with a separate $2.50/GPU-hour cap.

The first command checks your settings. The second submits the Job.

```bash
JOB_NAME=document-index bash scripts/submit.sh --dry-run &&
JOB_NAME=document-index bash scripts/submit.sh --async
```

Open Serverless AI → Jobs → document-index → Logs. Allow a few minutes for startup. The L40S run on November 13 and the H100 run on November 19, 2026 both finished about six minutes after submission. [Run records](VALIDATION.md). Account and storage setup take additional time. Wait for Completed and check:

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

Nebius has an `on-failure` restart policy, which restarts a container that fails inside a running Job. It doesn’t cover preemption, missing capacity at startup, unexpected VM stops, or failures and timeouts during startup. We use `--restart-policy never` here so you can inspect what happened and decide when to resubmit. [Automatic job restarts](https://docs.nebius.com/serverless/jobs/auto-restarts#when-jobs-aren%E2%80%99t-restarted).

- Wait for the previous attempt to show Completed, Failed, Cancelled or Error.
- Give the new Job a new name. Reuse the original `RUN_ROOT` and bucket region (`NEBIUS_REGION`), along with the same `RECIPE_REF`, input and model settings.
- Check the log's reused and remaining counts. An unfinished document is recomputed.
- Use one active Job per prefix. Changed input or model settings require a fresh prefix.

### Try it yourself

Use a new test prefix and limit the first Job to 600 documents:

```bash
JOB_NAME=document-index-600 RUN_ROOT="$RUN_ROOT/optional-resume" \
  MAX_NEW_DOCUMENTS=600 bash scripts/submit.sh --async
```

Wait for Completed, then check the log for **600 new, 0 reused, 400 remaining**. Now submit a Job against that same test prefix with the document limit removed:

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

Only fully saved documents are reused. Check the recovery Job for Completed and **1,000 documents / 1,970 chunks**. See the [recovery code](worker/durable.py) and [run records](VALIDATION.md).

## 4. Clean up

Once a Job shows Completed, its compute has been released. The index and reports stay in Object Storage. To stop an unfinished attempt, use Serverless AI → Jobs → ⋯ → Cancel.

Before deleting resources, check that every Job using them shows Completed, Failed, Cancelled or Error. When you’re finished, delete the prefixes and SecretStash secret you created for this recipe. If you created a dedicated S3 key, delete it under the service account’s Access keys. Keep any keys and buckets you share with other workloads.

## Run with an agent

If your agent has the [Nebius skills](https://github.com/nebius/skills#install), it can use them for Jobs and SecretStash. From this recipe directory, ask:

```text
Run the document-search recipe at my checked-out revision in the selected project
of my Nebius AI Cloud account. Confirm that its region offers Serverless AI and
use my private bucket in that region. Set NEBIUS_REGION to the bucket's region.
List the project's platforms and choose an eligible one-GPU preset. The launcher
selects the CUDA image. Set GPU_PLATFORM and GPU_PRESET to that pair.
The launcher follows the spot price without a GPU-hour cap. If my budget
requires a hard hourly cap, stop before submitting and explain why.
Otherwise use my approved budget, or ask for a limit.

Find the S3 secret before asking me for its ID. Check S3_SECRET_ID from
this recipe first. If it is missing or stale, look at a successful
document-index Job for the same project and bucket. Read only the secret references bound to AWS_ACCESS_KEY_ID
and AWS_SECRET_ACCESS_KEY. Both should point to the same mbsec-… ID.
Check the secret and its primary version using metadata only. Include
scheduled deletions in discovery (--show-scheduled-for-deletion).
A secret name alone doesn’t tell you which keys it contains.

Reuse a confirmed active match. If the secret or its primary version is
scheduled for deletion, ask whether to restore that item or use another.
After an approved restore, verify both are active. If several candidates
fit, ask once which reference to use. If access to a known ID is denied,
explain which metadata you need permission to read or ask for another
usable reference. For a new secret, guide me through console setup. Ask
only for the mbsec-… ID. Never fetch the payload or request key values.

Prepare the test data with python3 scripts/prepare_job_data.py, then run
python3 -m unittest discover -s tests. Run the dry run before submitting
one Job for all 1,000 documents on a fresh prefix. Confirm Completed,
1,000 indexed documents and a first-ranked stalemate passage that opens
in the Dolly dataset viewer. Preserve the index and any shared resources.
```
