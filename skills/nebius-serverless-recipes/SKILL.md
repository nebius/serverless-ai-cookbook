---
name: nebius-serverless-recipes
description: End-to-end playbooks for common Nebius Serverless AI scenarios — training on one GPU, multi-GPU single-node training, serving a fine-tuned model as a public endpoint, batch inference fan-out, fine-tuning with checkpoints, CI/CD-triggered jobs, debugging failing jobs, and cost-optimized preemptible training. Use when the user asks "how do I …" for any common Serverless AI workflow, wants a complete example from image build to running artifacts, or is kicking off a new kind of workload.
allowed-tools: Bash(nebius *), Bash(docker *), Bash(curl *)
---

# Nebius Serverless AI — Recipes

End-to-end playbooks. Each recipe gives the full CLI chain. Companion skills fill in flag details:

- Jobs surface: `nebius-serverless-job`
- Endpoints surface: `nebius-serverless-endpoint`
- Container build/push: `nebius-container-registry`
- Auth, secrets, volumes, ops: `nebius-serverless-platform`

Conventions used below:
- `<reg>` = short registry ID (strip `registry-` prefix)
- `<subnet>` = output of `nebius vpc subnet get-by-name --name default-subnet --format jsonpath='{.metadata.id}'`
- `<project>` = your project ID

## 1. One-shot 1-GPU training run

Build, push, submit, tail logs, collect artifacts from a bucket mount.

```bash
# 1. Build + push (amd64 mandatory)
docker buildx build --platform linux/amd64 \
  -t cr.eu-north1.nebius.cloud/<reg>/train:v1 --push .

# 2. Submit
JOB=$(nebius ai job create \
  --name train-$(date +%s) \
  --image cr.eu-north1.nebius.cloud/<reg>/train:v1 \
  --platform gpu-h100-sxm --preset 1gpu-16vcpu-200gb \
  --timeout 4h \
  --volume my-artifacts-bucket:/artifacts:rw \
  --subnet-id <subnet> \
  --async --format jsonpath='{.metadata.id}')

# 3. Live tail
nebius ai job logs "$JOB" --follow

# 4. Wait for terminal state
until nebius ai job get "$JOB" | awk '/^  State:/ {print $2}' \
  | grep -qE 'COMPLETED|FAILED|CANCELLED'; do sleep 30; done

# 5. Artifacts are in my-artifacts-bucket — fetch via object-storage CLI.
```

## 2. Multi-GPU single-node training (one VM, many GPUs)

```bash
nebius ai job create \
  --name train-8gpu-$(date +%s) \
  --image cr.eu-north1.nebius.cloud/<reg>/train:v1 \
  --platform gpu-h100-sxm --preset 8gpu-128vcpu-1600gb \
  --container-command torchrun \
  --args "--standalone,--nproc_per_node=8,/app/train.py,--batch-size,64" \
  --timeout 24h \
  --volume my-artifacts-bucket:/artifacts:rw \
  --subnet-id <subnet>
```

**Multi-node is not supported on Serverless AI.** Use Soperator/Managed Slurm or Managed Kubernetes with a GPU node group.

## 3. Serve a fine-tuned LLM as a public endpoint (vLLM, token auth)

```bash
TOKEN=$(openssl rand -hex 32)

nebius ai endpoint create \
  --name my-llm \
  --image vllm/vllm-openai:v0.6.0 \
  --platform gpu-h100-sxm --preset 1gpu-16vcpu-200gb \
  --container-port 8000 --public --auth token --token "$TOKEN" \
  --args "--model,/models/ft" \
  --volume models-bucket:/models:ro \
  --subnet-id <subnet>

# Wait for RUNNING (cold start = image pull + GPU attach)
until nebius ai endpoint get-by-name --name my-llm 2>/dev/null \
  | grep -q '^  State:   RUNNING'; do sleep 15; done

IP=$(nebius ai endpoint get-by-name --name my-llm \
  --format jsonpath='{.status.public_endpoints[0]}')

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://$IP:8000/v1/chat/completions" \
  -d '{"model":"/models/ft","messages":[{"role":"user","content":"hi"}]}'
```

For production, replace `--token "$TOKEN"` with `--token-secret <mb-ver-id>`.

## 4. Batch inference fan-out (no native array jobs)

```bash
# Submit 16 shards in parallel
for i in $(seq 0 15); do
  nebius ai job create \
    --name infer-$i-$(date +%s) \
    --image cr.eu-north1.nebius.cloud/<reg>/infer:v1 \
    --platform gpu-l40s-a --preset 1gpu-8vcpu-32gb \
    --timeout 2h \
    --env SHARD_INDEX=$i --env SHARD_TOTAL=16 \
    --volume input-bucket:/in:ro --volume output-bucket:/out:rw \
    --subnet-id <subnet> \
    --async &
done
wait   # wait for all submit calls to return

# Poll all of them
for j in $(nebius ai job list --parent-id <project> --format json \
  | jq -r '.items[] | select(.metadata.name | startswith("infer-")) | .metadata.id'); do
  nebius ai job operation list --resource-id "$j"
done
```

Alternative: a single multi-GPU job with `torchrun` consuming an S3 manifest.

## 5. Fine-tuning with checkpoints to a mounted bucket

Key additions over recipe #1: `--restart-policy on-failure`, `--restart-attempts -1`, and training code that resumes from the newest checkpoint.

```bash
nebius ai job create \
  --name ft-$(date +%s) \
  --image cr.eu-north1.nebius.cloud/<reg>/ft:v1 \
  --platform gpu-h100-sxm --preset 1gpu-16vcpu-200gb \
  --timeout 72h \
  --restart-policy on-failure --restart-attempts -1 \
  --volume ckpt-fs:/ckpts:rw \
  --env CKPT_DIR=/ckpts --env RESUME_FROM_LATEST=true \
  --subnet-id <subnet>
```

Prefer a **filesystem** mount (not a bucket) for checkpoint directories — small random writes perform better.

## 6. CI/CD from GitHub Actions

Assumes you've registered a CI service account + public key (see `nebius-serverless-platform` → "Non-interactive (CI)").

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Nebius CLI
        run: |
          curl -fsSL https://storage.ai.nebius.cloud/nebius/install.sh -o nb.sh
          # inspect before running in production; for brevity:
          sh nb.sh

      - name: Configure non-interactive profile
        run: |
          echo "${{ secrets.NEBIUS_SA_KEY }}" > /tmp/key.pem
          chmod 600 /tmp/key.pem
          nebius profile create --name ci \
            --service-account-id ${{ secrets.NEBIUS_SA_ID }} \
            --private-key-file /tmp/key.pem \
            --public-key-id ${{ secrets.NEBIUS_PUBKEY_ID }} \
            --parent-id ${{ secrets.NEBIUS_PROJECT_ID }}

      - name: Build + push image
        run: |
          nebius iam get-access-token | docker login --username iam \
            --password-stdin cr.eu-north1.nebius.cloud
          docker buildx build --platform linux/amd64 \
            -t cr.eu-north1.nebius.cloud/${{ secrets.NEBIUS_REGISTRY }}/app:${{ github.sha }} \
            --push .

      - name: Cancel previous jobs for this branch
        run: |
          BRANCH="${GITHUB_REF_NAME//\//-}"
          for j in $(nebius ai job list --format json \
            | jq -r '.items[] | select(.metadata.name | startswith("ci-'"$BRANCH"'-")) | .metadata.id'); do
            nebius ai job cancel "$j" || true
          done

      - name: Submit job
        run: |
          nebius ai job create \
            --name ci-${GITHUB_REF_NAME//\//-}-${GITHUB_SHA:0:7} \
            --image cr.eu-north1.nebius.cloud/${{ secrets.NEBIUS_REGISTRY }}/app:${{ github.sha }} \
            --platform gpu-l40s-a --preset 1gpu-8vcpu-32gb \
            --timeout 1h \
            --subnet-id ${{ secrets.NEBIUS_SUBNET_ID }}
```

**Use `--dry-run` in a pre-submit step** to catch spec errors cheaply:

```bash
nebius ai job create --dry-run ... && echo "spec OK"
```

## 7. Debug a failing job

```bash
# Spec-level info and last state
nebius ai job get <id>                          # look at status.state_details

# Logs — remember the --since default is 1h!
nebius ai job logs <id> --since 24h --tail 1000

# Live SSH — only works while RUNNING and if --ssh-key was passed at create
nebius ai job ssh <id>

# Post-mortem SSH trick: submit the failing command with `|| sleep 3600`
nebius ai job create ... \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --container-command bash \
  --args "-c,python train.py || sleep 3600"
# The job stays RUNNING after the crash; ssh in, inspect, then `cancel`.

# Reproduce locally
docker run --rm --gpus all -e KEY=VAL <image> <cmd>
```

## 8. Cost-optimized preemptible training

Get the spot discount by letting the platform reclaim the VM when it needs capacity. Only safe when your training script checkpoints frequently and resumes from the newest checkpoint at startup.

```bash
nebius ai job create \
  --name ft-spot-$(date +%s) \
  --image cr.eu-north1.nebius.cloud/<reg>/ft:v1 \
  --platform gpu-h100-sxm --preset 1gpu-16vcpu-200gb \
  --timeout 72h \
  --preemptible \
  --restart-policy on-failure --restart-attempts -1 \
  --volume ckpt-fs:/ckpts:rw \
  --env CKPT_DIR=/ckpts --env RESUME_FROM_LATEST=true \
  --subnet-id <subnet>
```

Tradeoffs:
- **Upside:** meaningful discount on per-second VM rate (see Compute pricing page).
- **Downside:** each preemption loses progress since the last checkpoint. Checkpoint every ~5–15 min of compute.
- Not suitable for tight wall-clock deadlines.

## 9. Validate a spec before spending GPU time

```bash
nebius ai job create --dry-run \
  --name dry-$(date +%s) --image ... --platform ... --preset ... \
  --subnet-id <subnet>
```

Use at the top of every CI workflow.

## Reference

- Overview: https://docs.nebius.com/serverless/overview
- Quickstart: https://docs.nebius.com/serverless/quickstart
- Jobs: https://docs.nebius.com/serverless/jobs
- Endpoints: https://docs.nebius.com/serverless/endpoints
- CLI index: https://docs.nebius.com/cli/reference/ai/
- IAM service accounts: https://docs.nebius.com/cli/reference/iam/service-account/
- MysteryBox: https://docs.nebius.com/cli/reference/mysterybox/
- Compute pricing (incl. preemptible): https://docs.nebius.com/compute/resources/pricing
