---
name: nebius-container-registry
description: Build and push container images to Nebius Container Registry so they can be pulled by Nebius Serverless AI jobs and endpoints. Covers image path format, linux/amd64 platform requirement, buildx push pattern, IAM-token `docker login`, private-pull auth via `--registry-secret` + MysteryBox, and verification with `docker manifest inspect`. Use when the user asks to build a container for Nebius, push an image, fix image pull errors, fix architecture mismatch, construct a registry path, authenticate Docker to Nebius CR, or wire up a private image pull.
allowed-tools: Bash(docker *), Bash(nebius *)
---

# Nebius Container Registry — build & push

Serverless AI jobs/endpoints pull their images from Nebius Container Registry. Three things must be right or the job fails at pull time: **registry path**, **image architecture**, and **auth**.

## Registry path format

```
cr.<region>.nebius.cloud/<registry-short-id>/<image-name>:<tag>
```

Example:

```
cr.eu-north1.nebius.cloud/e00v6ss66950gy4jq5/openmm-serverless:v0.1.7
```

- **Region** matches where you created the registry (e.g. `eu-north1`, `eu-west1`).
- **`<registry-short-id>`** is the ID **without** the `registry-` prefix. The CLI shows registries as `registry-e00v6ss...`; strip the prefix when constructing image URLs. Using the full ID yields `Entity Registry not found by id`.
- **Image + tag** are free-form.

List registries to grab the right short ID:

```bash
nebius registry v1alpha1 registry list --parent-id <project-id>
```

## Architecture: `linux/amd64` is required

Nebius Serverless AI GPU hosts are x86_64. Building on Apple Silicon or ARM without specifying platform produces `linux/arm64`, and the job fails to start with `exec format error` or `no matching manifest`.

**Always build with `--platform linux/amd64`**, even on x86 hosts (reproducibility).

## Build + push in one step (recommended)

`docker buildx build --push` avoids the slow local-load → push round-trip and produces an OCI index the registry accepts cleanly:

```bash
docker buildx build \
  --platform linux/amd64 \
  --tag cr.eu-north1.nebius.cloud/<registry-short-id>/<image>:<tag> \
  --push \
  .
```

First-time setup of a buildx builder:

```bash
docker buildx create --name nebiusbuilder --use --bootstrap
```

## Two-step alternative (build, then push)

Only when you need to inspect locally first:

```bash
docker buildx build --platform linux/amd64 --load -t <full-image-path> .
docker push <full-image-path>
```

`--load` only works for single-platform builds.

## Authenticating to the registry

### Interactive / laptop

```bash
nebius iam get-access-token | \
  docker login --username iam --password-stdin cr.<region>.nebius.cloud
```

The token is short-lived; re-login if push fails with `401 unauthorized`.

### CI (non-interactive)

Assuming a CI profile is already configured (see `nebius-serverless-platform` skill):

```bash
nebius iam get-access-token | docker login --username iam --password-stdin cr.eu-north1.nebius.cloud
```

The CLI mints the token from the active profile's service-account credentials.

## Private image pulls from a job/endpoint

If the image is in a different project or in an external registry:

### Option A — inline credentials (quick, but exposes password to CLI history)

```bash
nebius ai job create ... \
  --registry-username <user> \
  --registry-password <pass>
```

### Option B — MysteryBox secret (preferred for production)

```bash
# 1. Create the secret version with creds
SECRET_ID=$(nebius mysterybox secret create --name docker-registry \
  --parent-id $PROJECT_ID --format jsonpath='{.metadata.id}')

VER_ID=$(nebius mysterybox secret-version create --parent-id "$SECRET_ID" \
  --payload-json '[
    {"key":"REGISTRY_USERNAME","string_value":"my-user"},
    {"key":"REGISTRY_PASSWORD","string_value":"my-pass"}
  ]' --format jsonpath='{.metadata.id}')

# 2. Reference it from the job
nebius ai job create ... --registry-secret "$VER_ID"
```

The MysteryBox payload keys must be exactly `REGISTRY_USERNAME` and `REGISTRY_PASSWORD`.

## Verifying a pushed image

Always check the registry actually has the image + the right arch before submitting a job:

```bash
docker manifest inspect <full-image-path>
```

Look for `"architecture": "amd64"` + `"os": "linux"`. If the only manifests are `arm64` or `unknown`, rebuild with `--platform linux/amd64`.

## Image size considerations

- **No hard cap**, but images >10GB make startup dominated by pull time — jobs can exceed their `--timeout` and endpoints can time out in `STARTING`.
- **Keep weights out of the image.** Mount them via `--volume <bucket>:/models:ro` instead. The same image then serves many models just by changing the mount.
- **Layer reuse:** structure the Dockerfile so rarely-changing layers (CUDA, conda, system deps) come first and source code comes last. Subsequent builds reuse the heavy layers.

## Common failure modes & fixes

| Symptom | Cause | Fix |
|---|---|---|
| Job fails at pull: "no matching manifest for linux/amd64" | Image built for arm64 only | Rebuild with `--platform linux/amd64` |
| `docker push` returns `401 unauthorized` | Expired IAM token, or wrong hostname | Re-run `nebius iam get-access-token \| docker login ...` |
| `Entity Registry not found by id registry-...` | Used the full ID (with `registry-` prefix) in the image URL | Use the short ID (strip `registry-`) |
| Slow multi-GB push | Plain `docker push` after local build | Switch to `docker buildx build --push` |
| Buildx build fails with apt HTTP 413/500 | Transient Ubuntu mirror error | Retry the build |
| Job fails pull for private image | No registry auth passed | `--registry-username/--registry-password` or `--registry-secret <mb-ver-id>` |
| Endpoint stuck in `STARTING` forever | Image too large to pull before start deadline | Slim the image; move weights to a `--volume` mount |

## Reference

- Container Registry docs: https://docs.nebius.com/container-registry
- CLI CR: `nebius registry --help`, `nebius registry image --help`
- Docker buildx: https://docs.docker.com/buildx/
- MysteryBox: https://docs.nebius.com/cli/reference/mysterybox/
- Serverless AI job create (`--registry-secret`): https://docs.nebius.com/cli/reference/ai/job/create
