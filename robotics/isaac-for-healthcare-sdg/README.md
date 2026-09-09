---
title: Isaac for Healthcare synthetic data on Nebius AI Jobs — feasibility + headless SDG
category: robotics
type: feasibility + batch-job
runtime: nebius-ai-jobs
frameworks: [isaac-sim, isaac-lab, isaac-for-healthcare]
keywords: [isaac-for-healthcare, i4h, synthetic-data-generation, ultrasound, ray-tracing, omniverse, serverless-jobs, robotics]
difficulty: advanced
---

# Isaac for Healthcare on Nebius — feasibility + headless synthetic data job

[NVIDIA Isaac for Healthcare](https://developer.nvidia.com/isaac/healthcare) (i4h) is a robotics + simulation platform for hospital automation, teleoperation, autonomous ultrasound, surgical autonomy, synthetic data generation, and sensor simulation. The reference workflows live in [`isaac-for-healthcare/i4h-workflows`](https://github.com/isaac-for-healthcare/i4h-workflows).

This recipe answers one question first — **which Isaac for Healthcare workloads actually belong on Nebius Serverless AI Jobs, and which do not** — and then gives a runnable path for the part that does: **headless synthetic data generation (SDG)**.

> **TL;DR:** Only the *headless, non-interactive, render-to-disk* slice (e.g. the robotic-ultrasound `state_machine_scan` SDG protocol) is a good Serverless Job fit, and only on an **RT-Core GPU** (`gpu-l40s-a` or `gpu-rtx6000`). Teleoperation, hardware-in-the-loop, GUI Omniverse/Isaac Lab sessions, and deterministic edge runtime are **not** Serverless-fit — see [Limitations & alternate Nebius paths](#limitations--alternate-nebius-paths).

This is a **research/education** example. It contains **no patient data**, makes **no clinical, diagnostic, or medical-device claims**, and uses only the public, synthetic phantom assets shipped with the i4h workflows.

---

## What this example does

1. **A runnable GPU preflight job** ([Step 1](#step-1--run-the-gpu-preflight-runnable-now)) you can run today with no licensed Isaac assets. It reproduces the i4h GPU compatibility check and tells you whether the GPU you landed on can run the ray tracer — *before* you pull the multi-GB Isaac Sim image.
2. **A headless SDG job template** ([Step 2](#step-2--headless-synthetic-data-generation-job-template)) for users who have accepted the i4h/NGC/RTI licenses and built the i4h container. It runs the automated liver-scan state machine headless, writes HDF5 episodes, and persists them to Object Storage.
3. **A feasibility matrix and explicit limitations** so you pick the right Nebius target for every i4h workflow.

### Why serverless here (and why only partly)

Serverless AI Jobs are run-to-completion batch workloads: provision a GPU, run a container, write artifacts, auto-terminate. That maps cleanly onto **offline synthetic data generation** — render N episodes, upload, exit. It maps poorly onto anything **interactive, low-latency, device-attached, or display-bound**, which is most of the rest of i4h.

### Requirements

| Requirement | Why |
| --- | --- |
| Nebius CLI (authenticated) | Submit and monitor jobs — [install](https://docs.nebius.com/cli/install) / [configure](https://docs.nebius.com/cli/configure) |
| **RT-Core GPU** platform (`gpu-l40s-a` or `gpu-rtx6000`) | Isaac Sim ray tracing needs RT Cores + compute capability ≥ 8.6 (see matrix below) |
| Nebius Object Storage bucket | Persist HDF5 episodes (the VM is destroyed on completion) |
| i4h container image (Step 2 only) | Built per the i4h repo; large (Isaac Sim 5.0 base) — host on a registry |
| Accepted licenses (Step 2 only) | NVIDIA Software/Omniverse EULA, NGC asset terms, and [RTI Connext](https://www.rti.com/products/third-party-integrations/nvidia) DDS evaluation license |

### Runtime / compute

i4h documents these requirements for the ray-traced ultrasound workflow:

- **GPU:** compute capability **≥ 8.6** (Ampere or later) **with RT Cores**. NVIDIA explicitly lists **A100 and H100 as unsupported** (no RT Cores for the ray tracer). VRAM **≥ 24 GB** for sim/inference, **≥ 48 GB** for fine-tuning.
- **OS/driver:** Ubuntu 22.04/24.04, NVIDIA driver ≥ 555.x, CUDA ≥ 12.6 and **< 13.0**.
- **Host:** ≥ 64 GB system RAM, ≥ 100 GB NVMe (asset/model caching).

---

## Feasibility matrix

Which RT-Core GPU you land on is the gate. On Nebius Serverless that means **L40S** or **RTX PRO 6000** — the data-center accelerators do not carry RT Cores for the ray tracer.

| Nebius platform | GPU | Compute cap | RT Cores for i4h ray tracing | Verdict for SDG |
| --- | --- | --- | --- | --- |
| `gpu-l40s-a` / `gpu-l40s-d` | L40S (Ada) | 8.9 | ✅ Yes | **Recommended** — RT Cores + 48 GB, cost-efficient |
| `gpu-rtx6000` | RTX PRO 6000 (Blackwell) | 12.0 | ✅ Yes | **Supported** — RT Cores + 96 GB |
| `gpu-h100-sxm` | H100 | 9.0 | ❌ No (i4h: unsupported) | Do not use for ray tracing |
| `gpu-h200-sxm` | H200 | 9.0 | ❌ No | Do not use for ray tracing |
| `gpu-b200-sxm` / `gpu-b300-sxm` | B200 / B300 | 10.0 | ⚠️ Unverified for i4h | Not recommended — use L40S/RTX6000 |

The preflight in Step 1 encodes exactly this logic and exits non-zero on a non-RT-Core GPU.

### Workflow fit — what belongs on Serverless

| i4h workflow / mode | Nature | Serverless Job fit |
| --- | --- | --- |
| Robotic Ultrasound — `state_machine_scan` (headless SDG) | Automated, render-to-HDF5, no UI | ✅ **Good fit** (Step 2) |
| Robotic Ultrasound — `replay`, `convert_hdf5` (headless) | Batch data processing | ✅ Good fit |
| Robotic Ultrasound / Surgery — policy fine-tune (`train_pi0`, `train_gr00tn1`) | Batch GPU training (needs ≥ 48 GB) | ✅ Good fit (RT Cores not required for pure training, but the SDG that feeds it is) |
| Robotic Ultrasound — `teleop_*`, `full_pipeline`, `visualization` | Interactive GUI / keyboard / SpaceMouse | ❌ Not a fit |
| Robotic Ultrasound — `clarius_cast`, `realsense` (hardware-in-the-loop) | Attached physical probe/camera | ❌ Not a fit |
| Telesurgery | Real-time, low-latency video + haptics | ❌ Not a fit |
| GUI Omniverse / Isaac Lab inspection sessions | Display/streaming-bound | ❌ Not a fit (use Managed K8s / VM) |
| Holoscan deterministic edge runtime | Edge device, real-time SLA | ❌ Not a fit (use IGX / Jetson) |

---

## Step 1 — Run the GPU preflight (runnable now)

This needs **no licensed Isaac assets** — it just checks the GPU you landed on. Use it to confirm an RT-Core GPU before committing to the large SDG image. Source: [`scripts/gpu_preflight.sh`](./scripts/gpu_preflight.sh).

### Locally (Docker)

```bash
docker run --rm --gpus all \
  -v "$(pwd)/robotics/isaac-for-healthcare-sdg/scripts:/scripts:ro" \
  nvidia/cuda:12.6.3-runtime-ubuntu24.04 \
  bash /scripts/gpu_preflight.sh
```

### On Nebius Serverless (the RT-Core platform you intend to use)

The script is small, so we pass it inline (base64) into a stock CUDA image — no image build required:

```bash
B64=$(base64 -w0 robotics/isaac-for-healthcare-sdg/scripts/gpu_preflight.sh)

nebius ai job create \
  --name "isaac-i4h-gpu-preflight" \
  --image "nvidia/cuda:12.6.3-runtime-ubuntu24.04" \
  --container-command "bash" \
  --args "-c 'echo $B64 | base64 -d > /tmp/p.sh && bash /tmp/p.sh'" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-16vcpu-64gb" \
  --timeout "15m"

# stream logs
export JOB_ID=$(nebius ai job get-by-name --name isaac-i4h-gpu-preflight \
  --format jsonpath='{.metadata.id}')
nebius ai logs "$JOB_ID" --follow
```

> **Multiple subnets?** Add `--subnet-id "$SUBNET_ID"` if the CLI asks you to pick one.

### Expected output

On an RT-Core GPU (`gpu-l40s-a`), the job exits `0`:

```
============================================================
Isaac for Healthcare — GPU ray-tracing preflight
============================================================
GPU: NVIDIA L40S, 8.9, 46068 MiB, 555.x
Detected GPU : NVIDIA L40S
Compute cap  : 8.9  (i4h requires >= 8.6)
Compute-cap gate: PASS
RT-Core class  : KNOWN-GOOD

RESULT: PASS — RT-Core GPU suitable for Isaac for Healthcare ray tracing.
On Nebius Serverless use --platform gpu-l40s-a (or gpu-rtx6000).
```

On an H100 it prints `RESULT: FAIL … data-center GPU the i4h docs list as unsupported` and exits `3`. On a pre-Ampere GPU it fails the compute-cap gate and exits `2`.

> **Validated on real hardware.** This preflight was run as a Nebius AI Job on a data-center GPU (B200, compute cap 10.0, 183 GB). It correctly passed the compute-cap gate but flagged `RT-Core class: UNVERIFIED` and steered to `gpu-l40s-a`/`gpu-rtx6000` — confirming that landing on a high-end data-center GPU is *not* sufficient for the Isaac ray tracer. The job reports `FAILED` (the gate exits non-zero by design on a non-RT-Core GPU); on `gpu-l40s-a` it exits `0` and the job succeeds.

---

## Step 2 — Headless synthetic data generation job (template)

> **Prerequisite:** Build the i4h container from [`isaac-for-healthcare/i4h-workflows`](https://github.com/isaac-for-healthcare/i4h-workflows) and push it to a registry you control. By building/running it you accept the NVIDIA Omniverse/Software EULA, NGC asset terms, and the [RTI Connext](https://www.rti.com/products/third-party-integrations/nvidia) DDS license. **Do not commit license keys or assets to this repo.**

The robotic-ultrasound `state_machine_scan` mode drives the simulated Franka arm through a fixed liver-scan protocol and records HDF5 episodes — no GUI interaction. Run it **headless** (Isaac Lab `AppLauncher` supports `--headless` and `--enable_cameras`) and sync results to Object Storage.

### Set up Object Storage

```bash
export AWS_ACCESS_KEY_ID="..." AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="i4h-sdg-<your-suffix>"
export S3_PREFIX="robotic-ultrasound-sdg"
```

### Submit the SDG job

```bash
nebius ai job create \
  --name "i4h-us-sdg-statemachine" \
  --image "<your-registry>/i4h-workflows:<tag>" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-16vcpu-64gb" \
  --disk-size "200Gi" \
  --timeout "4h" \
  --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" \
  --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" \
  --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" \
  --env "S3_BUCKET=$S3_BUCKET" --env "S3_PREFIX=$S3_PREFIX" \
  --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL" \
  --env "RTI_LICENSE_FILE=/workspace/rti_license.dat" \
  --container-command "bash" \
  --args "-c 'set -euo pipefail && \
    ./i4h run robotic_ultrasound state_machine_scan --as-root --headless \
      --run-args=\"--num_episodes 50 --enable_cameras\" && \
    aws s3 sync data/hdf5 s3://\$S3_BUCKET/\$S3_PREFIX/ --endpoint-url \$S3_ENDPOINT_URL'"
```

Notes:
- **`--headless`** is essential — there is no display on a Serverless Job. Confirm the exact flag plumbing against your i4h version (`AppLauncher` options pass through `--run-args`).
- `state_machine_scan` writes to `data/hdf5/<timestamp_task>/`; the `aws s3 sync` persists it before the VM is destroyed.
- `\$S3_*` are escaped so they expand **inside** the container (from `--env`), not in your local shell.
- Provide the RTI Connext license to the container via a mounted secret/volume; do not bake it into the image.

### Retrieve and inspect

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" --endpoint-url "$S3_ENDPOINT_URL"
aws s3 sync "s3://$S3_BUCKET/$S3_PREFIX/" "./i4h-sdg-out/" --endpoint-url "$S3_ENDPOINT_URL"
```

Each episode is an HDF5 file with synchronized robot states, RGB/depth frames, and (when ray tracing is enabled) simulated B-mode ultrasound images — ready for `convert_hdf5` → LeRobot format and downstream policy fine-tuning.

---

## Guardrails

- **GPU / preset:** `gpu-l40s-a` (RT Cores, 48 GB, cost-efficient) or `gpu-rtx6000` (96 GB). Never the data-center GPUs for ray tracing. Start with `1gpu-16vcpu-64gb`.
- **Disk:** `--disk-size 200Gi` — the Isaac Sim 5.0 image plus cached assets are large; 100 Gi is the documented floor.
- **Timeout:** always set `--timeout` (e.g. `15m` preflight, `4h` SDG) so a stalled cold start can't run unbounded. First container pull/build can take **10+ minutes**.
- **Cost:** episode rendering is GPU-bound — start with a small `--num_episodes` (e.g. 5) to estimate per-episode time/cost, then scale. Prefer L40S over RTX6000 for cost unless you need 96 GB.
- **Cleanup:** Serverless **compute** auto-terminates on completion; **Object Storage is not** — delete buckets/objects you no longer need (`aws s3 rb`/`rm`). The preflight job leaves no persistent resources.
- **Safety:** synthetic phantom assets only. No patient data, no clinical/diagnostic/medical-device claims.

---

## Limitations & alternate Nebius paths

Serverless AI Jobs are **not** the right Nebius target for these i4h workflows. Recommended alternatives:

| i4h workload | Why not Serverless | Recommended Nebius target |
| --- | --- | --- |
| Teleoperation / `teleop_*` (keyboard, SpaceMouse, gamepad) | Interactive, needs live input device + display | [Managed Kubernetes](https://docs.nebius.com/kubernetes) or a [GPU VM](https://docs.nebius.com/compute/virtual-machines) with Omniverse streaming |
| Telesurgery | Real-time low-latency video + haptics + cross-host DDS | GPU VM / dedicated cluster close to the operator; not a batch job |
| GUI Omniverse / Isaac Lab inspection (`full_pipeline`, `visualization`) | Display/streaming-bound, long-lived session | GPU VM with [Omniverse Kit streaming](https://docs.nebius.com/compute/virtual-machines) (L40S/RTX6000) |
| Hardware-in-the-loop (Clarius probe, RealSense camera) | Physical device attached to the host | On-prem / edge workstation; Holoscan SDK |
| Deterministic edge runtime (Holoscan) | Real-time SLA at the bedside/edge | NVIDIA IGX / Jetson edge devices |

For long-lived **inference** serving of a trained policy (not the simulator), a [Serverless Endpoint](../../inference/) on an RT-Core GPU can be appropriate — but the simulator and any device I/O stay off Serverless.

---

## How to adapt

- **Switch workflow:** the same headless pattern applies to `robotic_surgery` SDG and `agentic` IsaacLab-Arena episode generation — render headless, sync to S3.
- **Scale episodes:** raise `--num_episodes`; size `--disk-size` and `--timeout` to match.
- **Feed training:** chain `convert_hdf5` → `train_pi0`/`train_gr00tn1` as a second job (training tolerates non-RT GPUs and benefits from ≥ 48 GB VRAM).
- **Augment:** i4h supports Cosmos Transfer augmentation downstream of SDG for cross-scene generalization.

This recipe mirrors the submission pattern used by the other robotics examples — see [`lerobot-finetune-job`](../lerobot-finetune-job/README.md) (image + S3 handoff + GPU job) and [`smolva-ft-norma-core`](../smolva-ft-norma-core/README.md) (bundle workflow). For a life-science batch-job pattern, see [`parabricks-deepvariant`](../../life-science/parabricks-deepvariant/README.md).

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Preflight exits `3` (`UNSUPPORTED`/`UNVERIFIED`) | You landed on a non-RT-Core GPU. Use `--platform gpu-l40s-a` or `gpu-rtx6000`. |
| Preflight exits `2` (compute cap < 8.6) | Pre-Ampere GPU; not supported by Isaac Sim ray tracing. |
| SDG job hangs at start | Isaac Sim cold start / asset download can take 10+ min; raise `--timeout` and watch `nebius ai logs <id> --follow`. |
| `qt.qpa` / display / GLFW errors | Missing `--headless`; there is no display on a Serverless Job. |
| Job completes, bucket empty | Check `AWS_*`/`S3_*` env vars and that `aws s3 sync` ran after the scan in `--args`. |
| RTI Connext / DDS license error | Provide a valid RTI Connext license to the container (mounted secret), not baked into the image. |
| OOM during fine-tuning | Use ≥ 48 GB VRAM (`gpu-rtx6000`) or reduce batch size. |

---

## References

- Isaac for Healthcare: <https://developer.nvidia.com/isaac/healthcare>
- i4h workflows repo: <https://github.com/isaac-for-healthcare/i4h-workflows>
- Robotic Ultrasound workflow (incl. SDG / `state_machine_scan`): <https://github.com/isaac-for-healthcare/i4h-workflows/tree/main/workflows/robotic_ultrasound>
- Isaac for Healthcare documentation: <https://isaac-for-healthcare.github.io/i4h-docs/>
- Isaac Lab `AppLauncher` (`--headless`, `--enable_cameras`): <https://isaac-sim.github.io/IsaacLab/>
- RTI Connext for NVIDIA: <https://www.rti.com/products/third-party-integrations/nvidia>
- Nebius RTX PRO 6000 on Serverless: <https://nebius.com/blog/posts/introducing-rtx-pro-6000>
- Nebius AI Jobs: <https://docs.nebius.com/serverless> · CLI: <https://docs.nebius.com/cli/install>
- Nebius Object Storage quickstart: <https://docs.nebius.com/object-storage/quickstart>
