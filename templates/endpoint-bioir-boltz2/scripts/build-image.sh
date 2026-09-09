#!/usr/bin/env bash
set -euo pipefail

# Build and publish the thin public launcher. It contains no BioIR release
# artifact or model weight: those are acquired from upstream when an endpoint
# starts. Use the printed immutable digest in release notes and manual deploys.
: "${IMAGE_TAG:?Set IMAGE_TAG to a tag in a public container registry.}"

docker build --pull --tag "$IMAGE_TAG" .
docker push "$IMAGE_TAG"
printf 'Published %s@%s\n' "$IMAGE_TAG" "$(crane digest "$IMAGE_TAG")"
