#!/usr/bin/env bash
# Entry point of the CPU job: log the nebius CLI in as the service account,
# then run the given command, e.g. `uv run /app/src/prefect/flow.py ...`.
set -euo pipefail

# Install the CLI into /usr/local/bin. The installer reads $SHELL, which
# containers usually leave unset.
curl -sSL https://artifacts.nebius.cloud/cli/install.sh \
  | SHELL=/bin/bash NEBIUS_INSTALL_FOLDER=/usr/local/bin bash

nebius profile create \
  --endpoint api.nebius.cloud \
  --service-account-file /secrets/nebius-credentials.json \
  --parent-id "$PROJECT_ID" \
  --profile spot-flow

exec "$@"
