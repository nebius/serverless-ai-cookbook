# Axolotl

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/job/create?image=docker.io%2Faxolotlai%2Faxolotl%3Amain-20260309-py3.11-cu128-2.9.1&amp;command=curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftraining%2Faxolotl-finetuning%2Fsrc%2Fconfig.yaml%20-o%20%2Fworkspace%2Fdata%2Fconfig.yaml%20%26%26%20export%20RUN_ID%3Drun-%24%28date%20%2B%25Y%25m%25d-%25H%25M%25S%29%20%26%26%20axolotl%20train%20%2Fworkspace%2Fdata%2Fconfig.yaml%20%26%26%20mkdir%20-p%20%2Fworkspace%2Fdata%2Foutput%2F%24RUN_ID%20%26%26%20cp%20-r%20%2Fworkspace%2Foutput%2F.%20%2Fworkspace%2Fdata%2Foutput%2F%24RUN_ID&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;volume=%2Fworkspace%2Fdata&amp;diskSize=500GiB&amp;preemptible=true"><img src="../assets/create-job.svg" alt="Create Job" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Axolotl finetunes Qwen2.5-0.5B (Apache-2.0) on a preemptible H100 using the cookbook train config.

**License:** [Apache-2.0](https://github.com/axolotl-ai-cloud/axolotl/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/Qwen/Qwen2.5-0.5B)

<!-- /factory:intro -->

## Test request

After the job completes, check logs for training progress and confirm checkpoints
land under the mounted volume (`/workspace/data/output/…`).

```bash
nebius ai job logs <job-id>
```

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so Hub
model downloads are authenticated and usually faster (not required for the
default Apache-2.0 base model).

> ⚠️ When you are done testing, **delete the job** so it stops billing — see
> [How to delete a job](https://docs.nebius.com/serverless/jobs/manage#how-to-delete-a-job).

<!-- factory:cli -->

## CLI alternative

```bash
# bucket in the same project + region; create with: nebius storage bucket create --name axolotl-output --parent-id <project-id>
BUCKET=$(nebius storage bucket get-by-name --name axolotl-output --format jsonpath='{.metadata.id}')

nebius ai job create \
  --name axolotl-finetune-$(date +%Y%m%d-%H%M%S) \
  --image docker.io/axolotlai/axolotl:main-20260309-py3.11-cu128-2.9.1 \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --preemptible \
  --follows-spot-price \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --volume "$BUCKET:/workspace/data:rw" \
  --container-command bash \
  --args '-c "curl -fsSL https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/main/training/axolotl-finetuning/src/config.yaml -o /workspace/data/config.yaml && export RUN_ID=run-$(date +%Y%m%d-%H%M%S) && axolotl train /workspace/data/config.yaml && mkdir -p /workspace/data/output/$RUN_ID && cp -r /workspace/output/. /workspace/data/output/$RUN_ID"'
```

Keep the outer single quotes: they stop your local shell from expanding `$(date …)` and
`$RUN_ID`, so the container sets them. With outer double quotes `$RUN_ID` is empty and the
checkpoints are copied straight into `output/`.

> ⚠️ `--follows-spot-price` accepts the current spot price with no cap. The price can
> change every 15 minutes while the resource is running, and a higher price does not
> stop it. Capacity preemption can still stop it — see
> [Choosing a pricing option](https://docs.nebius.com/signup-billing/pricing-policy#choosing-a-pricing-option).

<!-- /factory:cli -->

## Troubleshooting

- **Slow Hub pull** — add optional env `HF_TOKEN`; template asks for 500 Gi disk for pull bandwidth.
- **OOM / NER** — confirm `gpu-h100-sxm` / `1gpu-16vcpu-200gb` and volume mount `/workspace/data`.
