#!/usr/bin/env bash
set -euo pipefail

# Build and publish the pinned public BioIR runtime. Model weights are fetched
# by the first prediction. Use the printed digest in every deployment link.
: "${IMAGE_TAG:?Set IMAGE_TAG to a tag in a public container registry.}"

docker build --pull --platform linux/amd64 --tag "$IMAGE_TAG" .
docker push "$IMAGE_TAG"
printf 'Published %s@%s\n' "${IMAGE_TAG%:*}" "$(crane digest "$IMAGE_TAG")"
