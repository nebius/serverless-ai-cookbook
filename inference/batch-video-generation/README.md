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

Let’s generate 200 videos from VBench prompts so you can compare how Wan handles motion across eight types of scene. You’ll get an MP4 for each prompt, a gallery for side-by-side review, and a manifest with the seeds and settings to repeat the experiment.

A Nebius Serverless Endpoint runs Wan2.1-T2V-1.3B on a lower-cost [preemptible GPU](https://docs.nebius.com/compute/virtual-machines/preemptible). Your computer saves each finished clip, so you can resume if Nebius reclaims the GPU or your connection drops.

![Selected frames from the completed 200-clip dataset](docs/media/result.jpg)

Watch one clip from the batch. Wan generated “fireworks display in the sky at night” with seed `24530229`. [Original 3-second MP4](docs/media/vbench-scenery-0014.mp4)

Powered by Nebius Serverless AI · [Recorded test runs](VALIDATION.md)

## 1. Set up

You need macOS or Ubuntu, Git, Python 3.10+, [Nebius CLI](https://docs.nebius.com/cli/install) 0.12.303+, and FFmpeg with `ffprobe`. Use a billing-enabled eu-north1 project with permission to create Endpoints and pricing policies, quota for a preemptible H100 and 500 GiB of disk, and an internet-enabled subnet. No local GPU is needed.

```bash
git clone https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/inference/batch-video-generation
nebius profile create
```

Complete sign-in and choose your project. If already configured, use `nebius profile activate YOUR_PROFILE_NAME` instead. Run the remaining commands from this cookbook folder.

For missing tools, follow [CLI installation](https://docs.nebius.com/cli/install) or run `nebius update`. Install FFmpeg with `brew install ffmpeg` on macOS or `sudo apt-get update && sudo apt-get install -y ffmpeg` on Ubuntu. If needed, [create a network and subnet](https://docs.nebius.com/vpc/networking/resources). Return here after opening a new terminal.

Check the tools and the bundled prompts:

```bash
ffmpeg -version
ffprobe -version
python3 scripts/prepare_data.py --verify
python3 src/generate.py --check-input
```

Expect **200 prompts** and **49 frames at 832×480**. The [source selection and Apache 2.0 license](data/SOURCE.md) are included. VBench supplies the prompts. This recipe does not calculate a benchmark score.

## 2. Start Wan with a price cap

In the [console](https://console.nebius.com), open Billing → Pricing → Pricing policy → Create pricing policy. Select your project and `gpu-h100-sxm`, check the current rate, and enter the maximum price per GPU hour you accept. The cap limits the hourly GPU price. You pay for the time the Endpoint runs, and capacity can still be unavailable. [Pricing policy details](https://docs.nebius.com/signup-billing/manage-pricing-policy).

Copy the project ID from the project selector’s ⋯ menu → Copy project ID, the subnet ID from Networking → Virtual Networks → Subnets, and the new policy ID. Replace all three values:

```bash
cat > .env <<'ENV'
export NEBIUS_PROJECT_ID="YOUR_PROJECT_ID"
export NEBIUS_SUBNET_ID="YOUR_SUBNET_ID"
export SPOT_PRICING_POLICY_ID="YOUR_POLICY_ID"
ENV
source .env
```

Wan runs with vLLM-Omni 0.24.0, one H100 and a 500 GiB temporary disk. Startup and idle time count toward the bill. On November 17–18, 2026, we were quoted $2.12–$2.42 an hour for GPU and disk combined. At those rates, allow a few dollars for a run with about an hour of generation plus startup. Longer interruptions can cost more while the Endpoint is running. [Recorded rates and costs](VALIDATION.md#quoted-compute-and-disk-costs)

Check the configuration, create the Endpoint and wait for Wan. On Ubuntu, replace `caffeinate -i` with [`systemd-inhibit --what=sleep --mode=block`](https://manpages.ubuntu.com/manpages/noble/man1/systemd-inhibit.1.html) in every command.

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

Continue when you see **Model API ready**. In our November 17, 2026 run, the first clip was saved about seven minutes after we started creating the Endpoint. Allow extra time for account setup and available capacity. If the wait times out, stop the Endpoint while you diagnose it. If you open a new terminal, return to this folder and run `source .env`.

## 3. Generate 200 clips

Keep your computer awake and connected while it sends prompts and saves downloads. Leave the lid open if you’re using a laptop. For an unattended run, use a machine with persistent storage for the output folder.

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-vbench-200
```

From an empty folder, expect **Generated 200; reused 0**. Allow about an hour of active generation. Clip timers averaged 16 seconds in the batch completed November 18, 2026. Wall time depends on startup and interruptions.

### Use your own prompts

If you want a second batch from your own prompts, run it before stopping Wan. Put each prompt on a separate row with a unique ID and an integer seed from 0 to 2147483647. Use quotes around descriptions containing commas. The client accepts up to 1,000 prompts per CSV.

```bash
cat > data/my-prompts.csv <<'CSV'
id,prompt,seed
coffee,"Steam rising from a cup of coffee in soft morning light",42
coast,"A slow aerial shot of waves breaking along a rocky coastline",43
CSV
python3 src/generate.py --input data/my-prompts.csv --check-input &&
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/my-prompts.csv --output results-custom
```

Use a new output folder when changing prompts, seeds or settings.

## 4. Stop the Endpoint and review your clips

As soon as your last download finishes, stop the Endpoint. The checks and gallery run on your computer.

```bash
python3 scripts/endpoint.py stop
python3 scripts/endpoint.py status
```

Confirm **STOPPED**. Then check the saved videos:

```bash
python3 scripts/check_results.py results-vbench-200
```

On November 18, 2026, the checker verified the hashes and decoded all 200 clips from our Wan-AI/Wan2.1-T2V-1.3B-Diffusers run. Look for these fields:

```json
{"completed": 200, "frames_per_clip": [49], "decode_passed": true}
```

Open `results-vbench-200/index.html` on your computer with `open results-vbench-200/index.html` on macOS or `xdg-open results-vbench-200/index.html` on Ubuntu. Play a clip beside its prompt and seed. Each MP4 is about three seconds long at 832×480 and 16 fps. The gallery should show **200 of 200 clips saved**. You can use the MP4s and `clips.csv` directly in another workflow.

If you also ran the custom batch, use `python3 scripts/check_results.py results-custom` and open `results-custom/index.html`.

## What if your workload is interrupted?

**Keep the same output folder.** It holds each finished MP4, its completion record and the pending request IDs. Keep `.state/` too, so the helper can find your Endpoint. Use the same prompts, seeds and model settings, with one client writing to the folder.

In our November 17–18, 2026 run, the laptop went to sleep after saving 54 clips. The first resume added 3. The next reused all 57 and added the final 143. Across those three commands, about 2 hours 45 minutes elapsed, including pauses. [Run records](VALIDATION.md#completed-200-clip-dataset-2026-11-18-utc)

1. Run `python3 scripts/endpoint.py status`. If it shows **RUNNING**, go straight to the generation command below. If it shows **STOPPED**, start the Endpoint when capacity is available and wait for Wan:

   ```bash
   python3 scripts/endpoint.py start
   caffeinate -i python3 scripts/endpoint.py wait --timeout 1800
   ```

2. Rerun the original command. It skips verified downloads and checks the saved ID for the unfinished clip:

   ```bash
   caffeinate -i python3 scripts/endpoint.py run -- \
     python3 src/generate.py --input data/prompts.csv --output results-vbench-200
   ```

3. If the client asks for `--retry-lost`, inspect the last request. Wan may have lost its ID, reported it failed or cancelled, or the original submission may be unconfirmed. If you replaced the Endpoint, confirm the old one is stopped. To authorize a new paid request for that unfinished clip, rerun in the same folder:

   ```bash
   caffeinate -i python3 scripts/endpoint.py run -- \
     python3 src/generate.py --input data/prompts.csv --output results-vbench-200 --retry-lost
   ```

Once the downloads finish, stop the Endpoint and check your files as in step 4.

### Try it yourself

To practice recovery during your first 200-clip run, use these commands in place of step 3. If you already completed the main run, repeating it in a fresh folder pays for another 200 clips. Start the Endpoint again and wait for Wan first. This 20/180 split was tested locally with fixture videos.

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-resume-test --limit 20
```

Wait for **Generated 20; reused 0**. Leave Wan running and remove the limit:

```bash
caffeinate -i python3 scripts/endpoint.py run -- \
  python3 src/generate.py --input data/prompts.csv --output results-resume-test
```

Expect **Generated 180; reused 20**. Stop the Endpoint as in step 4, then run `python3 scripts/check_results.py results-resume-test`.

## Run with an agent

Share the recipe with your coding agent. If it has the [Nebius skills](https://github.com/nebius/skills#install), it can use them for the Endpoint steps.

```text
Run the 200-prompt Wan recipe in my selected project and subnet. Confirm my
GPU price cap and spending budget, validate the config, and start the
preemptible Endpoint. Generate into results-vbench-200. If interrupted,
preserve that folder and try the same command first. Ask before retrying
an ambiguous paid request. Stop the Endpoint after the last download and
confirm STOPPED. Then check that all 200 clips decode to 49 frames and show
me the gallery, new and reused counts, and any failures.
```
