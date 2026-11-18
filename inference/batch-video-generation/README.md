---
title: Generate a Video Dataset with Wan
category: inference
type: cookbook
runtime: Nebius Serverless AI Endpoint
frameworks: [vLLM-Omni]
keywords: [preemptible, video-generation, wan, vbench, batch-processing]
difficulty: intermediate
---

<img src="docs/brand/nebius-logo.svg" alt="Nebius" width="140">

# Generate a Video Dataset with Wan

Generate a 200-clip video dataset with Wan2.1-T2V-1.3B from VBench’s published prompt catalog, with a review gallery and a manifest of prompts, seeds and settings.

Nebius Serverless AI hosts Wan behind an authenticated Endpoint and manages the underlying VM. Your computer submits prompts and saves each finished download.

We’ll use a lower-cost [preemptible GPU](https://docs.nebius.com/compute/virtual-machines/preemptible). Finished clips are saved on your computer and reused after a restart.

![Selected frames from the completed 200-clip dataset](docs/media/result.jpg)

Powered by Nebius Serverless AI · [Completion report](docs/resume-results/complete-200.json) · [Recorded test runs](VALIDATION.md)

## 1. Set up

You need macOS or Ubuntu, Git, Python 3.10+, [Nebius CLI](https://docs.nebius.com/cli/install) 0.12.303+, and FFmpeg with `ffprobe`. Use a billing-enabled eu-north1 project with permission to create Endpoints and pricing policies, quota for a preemptible H100 and 500 GiB of disk, and an internet-enabled subnet. No local GPU is needed.

```bash
git clone https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/inference/batch-video-generation
nebius profile create
```

Complete sign-in and choose your project. If already configured, use `nebius profile activate YOUR_PROFILE_NAME` instead. Run the remaining commands from this cookbook folder.

For missing tools, follow [CLI installation](https://docs.nebius.com/cli/install) or run `nebius update`; install FFmpeg with `brew install ffmpeg` on macOS or `sudo apt-get update && sudo apt-get install -y ffmpeg` on Ubuntu. If needed, [create a network and subnet](https://docs.nebius.com/vpc/networking/resources). Return here after opening a new terminal.

Check the tools and the bundled prompts:

```bash
ffmpeg -version
ffprobe -version
python3 scripts/prepare_data.py --verify
python3 src/generate.py --check-input
```

Expect **200 prompts** and **49 frames at 832×480**. The [source selection and Apache 2.0 license](data/SOURCE.md) are included. This generates a review dataset, not a VBench score.

## 2. Start Wan with a price cap

In the [console](https://console.nebius.com), open Billing → Pricing → Pricing policy → Create pricing policy. Select your project and `gpu-h100-sxm`, check the current rate, and enter the maximum price per GPU hour you accept. The cap limits what you pay per GPU hour; it doesn’t guarantee a GPU. [Pricing policy details](https://docs.nebius.com/signup-billing/manage-pricing-policy).

Copy the project ID from the project selector’s ⋯ menu → Copy project ID, the subnet ID from Networking → Virtual Networks → Subnets, and the new policy ID. Replace all three values:

```bash
cat > .env <<'ENV'
export NEBIUS_PROJECT_ID="YOUR_PROJECT_ID"
export NEBIUS_SUBNET_ID="YOUR_SUBNET_ID"
export SPOT_PRICING_POLICY_ID="YOUR_POLICY_ID"
ENV
source .env
```

The [configuration](config/endpoint.json) uses vLLM-Omni 0.24.0, one H100 and a 500 GiB temporary disk. Wan is public; no Hugging Face token is needed. You’re also billed while the image is pulled and the model loads, and while the Endpoint is idle. The disk is billed separately.

The quoted GPU-and-disk rate was about $2.12–$2.42/hour. At those rates, budget a few dollars for a full run including startup; see the [cost details](VALIDATION.md#quoted-compute-and-disk-costs).

The first command checks your settings; the second creates the Endpoint; the last waits for the model. On Ubuntu, replace `caffeinate -i` with [`systemd-inhibit --what=sleep --mode=block`](https://manpages.ubuntu.com/manpages/noble/man1/systemd-inhibit.1.html) in every command.

```bash
python3 scripts/endpoint.py create \
  --project-id "$NEBIUS_PROJECT_ID" --subnet-id "$NEBIUS_SUBNET_ID" \
  --spot-pricing-policy-id "${SPOT_PRICING_POLICY_ID:?Set SPOT_PRICING_POLICY_ID}" \
  --name wan-video-dataset --dry-run &&
python3 scripts/endpoint.py create \
  --project-id "$NEBIUS_PROJECT_ID" --subnet-id "$NEBIUS_SUBNET_ID" \
  --spot-pricing-policy-id "${SPOT_PRICING_POLICY_ID:?Set SPOT_PRICING_POLICY_ID}" \
  --name wan-video-dataset --yes &&
caffeinate -i python3 scripts/endpoint.py wait --timeout 1800
```

Startup and model loading took about 6½ minutes in our tests. Continue when it prints **Model API ready**. The helper keeps its selection in `.state/` and passes credentials privately. A timeout doesn’t stop compute; inspect logs and stop it while diagnosing. If you open a new terminal, return to this folder and run `source .env`.

For uncapped pricing, omit `--spot-pricing-policy-id` from both create commands. The helper then follows the spot price, which can exceed the regular rate.

## 3. Generate and review 200 clips

Allow about an hour for 200 clips; recorded clip timers averaged 16 seconds in our run. Keep this computer awake and connected, with the lid open: it sends each prompt and downloads each clip. On an automated runner, use persistent storage for the output folder.

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-vbench-200 &&
python3 scripts/check_results.py results-vbench-200
```

For an empty folder, expect **Generated 200; reused 0**, then **"completed": 200** and **"decode_passed": true**. Each clip is 49 frames at 16 fps, about 3.06 seconds, at 832×480. The checker validates hashes, metadata and MP4 decoding.

Open `results-vbench-200/index.html` with `open results-vbench-200/index.html` on macOS, or `xdg-open results-vbench-200/index.html` on Ubuntu. Expect **200 of 200 clips saved**. Play the clips, review prompt alignment and follow the source links. The folder also contains ordinary MP4s, `clips.csv`, per-clip JSON and input provenance.

### Use your own prompts

Keep Wan running. Replace these rows with your prompt catalog; use unique IDs, integer seeds from 0 to 2147483647, and quotes around descriptions containing commas. The client accepts up to 1,000 prompts per CSV.

```bash
cat > data/my-prompts.csv <<'CSV'
id,prompt,seed
coffee,"Steam rising from a cup of coffee in soft morning light",42
coast,"A slow aerial shot of waves breaking along a rocky coastline",43
CSV
python3 src/generate.py --input data/my-prompts.csv --check-input &&
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/my-prompts.csv --output results-custom &&
python3 scripts/check_results.py results-custom
```

Open `results-custom/index.html` the same way. Use a new output folder when changing prompts, seeds or settings.

## 4. Stop the Endpoint

```bash
python3 scripts/endpoint.py stop
python3 scripts/endpoint.py status
```

Expect **STOPPED**. The GPU and temporary disk are released; downloaded results remain. Closing the client or gallery doesn’t stop billing. Keep shared networking in place.

## What if your workload is interrupted?

**Finished clips and their completion records stay on your computer, outside the Endpoint.** Keep the whole output folder, including its JSON records and `.pending` directory, plus the helper’s `.state/` folder. Rerunning the same command skips completed clips and finishes the batch; an unfinished clip may need regeneration.

- Keep the input, model settings and output folder unchanged.
- Use one generation process per folder.
- Use `python3 scripts/endpoint.py status` to choose the recovery case below.
- After recovery, validate all clips and stop the Endpoint as in step 4.

### The client stopped

Run `python3 scripts/endpoint.py status`. If it shows **RUNNING**, rerun the generation command from step 3 without `--retry-lost`. The client checks its saved request IDs, continues pending requests and skips finished downloads.

### The GPU was reclaimed

If status shows **STOPPED**, start the Endpoint and wait for Wan:

```bash
python3 scripts/endpoint.py start
caffeinate -i python3 scripts/endpoint.py wait --timeout 1800
```

Check the saved request by rerunning the original command:

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-vbench-200
```

If it reports “server no longer has this request” or “submission outcome or Endpoint changed”, it stopped before submitting a replacement. If you created a new Endpoint instead of restarting the old one, confirm the old Endpoint shows STOPPED in the console. Then use `--retry-lost` to allow a new paid request for unfinished work:

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-vbench-200 --retry-lost &&
python3 scripts/check_results.py results-vbench-200
```

Then run the two stop/status commands in step 4 and confirm **STOPPED**. If capacity is unavailable, try starting later.

### Try it yourself

Use a new folder. Start and wait as above, then limit the first client run to 20 finished downloads:

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-resume-test --limit 20
```

Expect **Generated 20; reused 0**. Resume without the limit:

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-resume-test &&
python3 scripts/check_results.py results-resume-test
```

Expect **Generated 180; reused 20** and 200 valid clips. This is a deliberate client stop, not a preemption. Finish with step 4 and confirm **STOPPED**. For local checks, run `python3 -m unittest discover -s tests`; see [VALIDATION.md](VALIDATION.md) for execution records.

## Run with an agent

Install the [Nebius skills](https://github.com/nebius/skills#install), share this cookbook and ask:

```text
Run batch-video-generation with nebius-cloud-basics and
nebius-serverless-endpoints in my selected project and subnet, within
my approved GPU budget. Use config/endpoint.json and a price-capped
preemptible Endpoint. Wait for Model API ready; generate all 200 clips.
Require scripts/check_results.py to pass with 200 decoded clips, review
the gallery, stop the Endpoint and confirm STOPPED. Report failures.
Keep credentials private; preserve my results and other resources.
```
