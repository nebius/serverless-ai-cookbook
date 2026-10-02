---
title: Sweep Isaac Sim Franka Pick and Place with Nebius AI Jobs
category: robotics
type: batch-job
runtime: nebius-ai-jobs
frameworks: [isaac-sim, python]
keywords: [robotics, simulation, parameter-sweep, s3]
difficulty: intermediate
---

# Isaac Sim pick-and-place sweep

Run a headless [Franka Panda pick-and-place task](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/core_api_tutorials/tutorial_core_multiple_tasks.html) in an Isaac Sim Docker image. `launch.py` reads [`sweep.json`](./sweep.json) and submits **one Nebius AI Job per combination** of cube pickup X and placement Y. Jobs run independently and can execute at the same time. Each job records controller completion, the cube's measured final pose, placement error, and a success flag in its own S3 prefix.

The sample grid has four cases. Success means the controller finished and the cube ended within 8 cm in XY and Z of its target. A completed job can contain `"success": false`: that is a valid simulation result.

## Requirements

- An authenticated Nebius CLI, Docker, a Nebius Container Registry you can push to, and a project with an RTX-capable GPU platform (the example uses `gpu-l40s-a`).
- A Nebius Object Storage bucket, its regional S3 endpoint, and access keys stored in MysteryBox. `nebius ai job create --env-secret` reads the keys into the container; the launcher never places their values in job arguments.
- A Linux NVIDIA Docker host if you want the optional local GPU check. Docker Desktop on macOS cannot run this Isaac Sim GPU container.

This recipe pins `nvcr.io/nvidia/isaac-sim:5.1.0`. NVIDIA lists Linux driver `580.65.06` as its tested version and says GPUs without RT cores, including H100 and A100, are unsupported. Check the driver and platform available in your Nebius region before the first job. Isaac Sim also needs network access to its hosted assets. [NVIDIA requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html), [container guide](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html).

## 1. Build and push the container

The [Dockerfile](./Dockerfile) starts from `nvcr.io/nvidia/isaac-sim:5.1.0` and copies in [`run.py`](./run.py). The base image already includes `boto3`. From this directory, set `IMAGE` to a full image URI in your Nebius registry, then build and push it:

```bash
export IMAGE='cr.eu-north1.nebius.cloud/<registry-namespace>/isaac-pick-place-sweep:v1'
nebius registry configure-helper
docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"
```

Edit the Dockerfile to add packages or assets, or edit `run.py` to change the task. Build and push a new tag after either change, then pass that tag to the launcher. The `.dockerignore` sends only the Dockerfile and runner to the build.

You must accept NVIDIA's EULA to run it; the job launcher passes `ACCEPT_EULA=Y`.

## 2. Set the bucket and secret selectors

Create a bucket and access keys using the [Nebius Object Storage quickstart](https://docs.nebius.com/object-storage/quickstart). Store them in MysteryBox as payload entries named `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, then set their selectors below. The two entries may share one secret. A selector can be a secret name or ID, as described by `nebius ai job create --help`.

```bash
export S3_BUCKET='<bucket-name>'
export S3_ENDPOINT_URL='https://storage.eu-north1.nebius.cloud'
export AWS_DEFAULT_REGION='eu-north1'
export ACCESS_KEY_SECRET='<access-key-secret-selector>'
export SECRET_KEY_SECRET='<secret-key-secret-selector>'

aws configure --profile isaac-sweep   # enter the same S3 access keys and region
export AWS_PROFILE=isaac-sweep
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT_URL"
```

If you already have an AWS CLI profile for this bucket, use it instead. Do not put key values in `sweep.json` or shell command arguments.

## 3. Inspect and launch the sweep

Edit [`sweep.json`](./sweep.json) to change the grid. Its two nonempty arrays form a Cartesian product; the default values create four jobs near NVIDIA's example scene. First inspect the exact requests locally:

```bash
python3 launch.py \
  --image "$IMAGE" \
  --bucket "$S3_BUCKET" \
  --endpoint "$S3_ENDPOINT_URL" \
  --region "$AWS_DEFAULT_REGION" \
  --access-key-secret "$ACCESS_KEY_SECRET" \
  --secret-key-secret "$SECRET_KEY_SECRET" \
  --dry-run
```

Remove `--dry-run` to submit the jobs. If your project uses another RTX platform, preset, subnet, or CLI profile, add `--platform`, `--preset`, `--subnet-id`, or `--profile` to the command. The launcher prints each job ID and writes `runs/<run-id>/jobs.jsonl` as it submits; if a later submission fails, the earlier IDs remain recorded. Each invocation creates a new run ID and S3 prefix.

## 4. Check jobs and results

For a job ID printed by the launcher:

```bash
nebius ai job get '<job-id>' --format json
nebius ai job logs '<job-id>' --follow
aws s3 ls "s3://$S3_BUCKET/isaac-pick-place/<run-id>/<case-id>/" \
  --endpoint-url "$S3_ENDPOINT_URL"
aws s3 cp "s3://$S3_BUCKET/isaac-pick-place/<run-id>/<case-id>/result.json" ./result.json \
  --endpoint-url "$S3_ENDPOINT_URL"
```

Each case publishes `result.json`, then an empty `COMPLETE` object. `COMPLETE` means the result upload finished. Check the `success` field for robot task success. The result also contains `pick_position_m`, `target_position_m`, `final_cube_position_m`, `controller_done`, `steps`, `xy_error_m`, and `z_error_m`.

In a Nebius L40S run on 2026-10-02 using the same `run.py` with the official base image, all four jobs reached `COMPLETED` and each S3 prefix contained both objects. The two `pick_x=0.15` cases placed the cube within 6 mm of the target; the two `pick_x=0.1` cases missed the grasp and reported `success: false`. The sweep therefore records robot-task outcomes separately from job and upload completion.

A second run built and pushed this Dockerfile, then submitted two jobs through `launch.py`. Both reached `COMPLETED`, published `result.json` and `COMPLETE`, and reported successful placements with 5.2 mm and 5.9 mm XY error.

## Optional local GPU check

On a Linux Docker host with a compatible RTX GPU, run one case without S3:

```bash
docker run --name isaac-pick-local --gpus all --shm-size 16g \
  -e ACCEPT_EULA=Y \
  "$IMAGE" --run-id local --case-id case-000 \
  --pick-x 0.1 --place-y -0.25 --local
docker cp isaac-pick-local:/tmp/isaac-results/result.json ./result.json
docker rm isaac-pick-local
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Container fails before the task starts | Driver compatibility, RTX GPU, memory, EULA acceptance, and asset network access. |
| Image cannot be pulled by a Job | Confirm the pushed tag exists and the job can read your registry. |
| Job fails after simulation | S3 endpoint, bucket permissions, and MysteryBox secret selectors; no `COMPLETE` object should appear. |
| Job completes with `"success": false` | Inspect `controller_done`, final pose, and errors. This is a robot-task outcome, not a storage failure. |

The recipe is a small parameter sweep, not a robot benchmark. Use fixed versions, seeds, and repeated trials before comparing controller quality.
