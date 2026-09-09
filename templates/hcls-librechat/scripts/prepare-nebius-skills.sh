#!/usr/bin/env bash
set -euo pipefail

# Fetch with the builder's existing GitHub access. No credentials enter the image.
REVISION=292c7e65a46d0c29994d2babfc19da129d16fa62
TEMPLATE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$TEMPLATE_ROOT/vendor/nebius-skills"
STAGING="$(mktemp -d)"
trap 'rm -rf -- "$STAGING"' EXIT

gh repo clone nebius/skills "$STAGING/upstream" -- --no-checkout --filter=blob:none
git -C "$STAGING/upstream" fetch --depth 1 origin "$REVISION"
git -C "$STAGING/upstream" checkout --detach "$REVISION"
test "$(git -C "$STAGING/upstream" rev-parse HEAD)" = "$REVISION"
python3 - "$STAGING/upstream" "$DEST" "$REVISION" <<'PY'
import hashlib
import json
import shutil
import sys
from pathlib import Path

source, destination, revision = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
manifest = {
    'repository': 'https://github.com/nebius/skills',
    'revision': revision,
    'license': 'Apache-2.0',
    'files': {},
}
for path in sorted((source / 'skills').rglob('*')):
    if path.is_symlink():
        raise ValueError(f'Unexpected symlink in skill bundle: {path.name}')
    if path.is_file():
        relative = path.relative_to(source / 'skills')
        manifest['files'][str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
if destination.exists():
    # Only this generated, Git-ignored build directory is replaced.
    shutil.rmtree(destination)
shutil.copytree(source / 'skills', destination)
shutil.copy2(source / 'LICENSE', destination / 'NEBIUS-LICENSE')
(destination / 'nebius-upstream.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Prepared {len(list(destination.glob("*/SKILL.md")))} official Nebius skills at {revision}')
PY
