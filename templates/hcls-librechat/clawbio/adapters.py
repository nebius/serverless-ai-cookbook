"""Small headless integrations; scientific calculations stay in pinned upstream."""

import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", choices=["article-data-fetcher"])
    parser.add_argument("--id", required=True, help="Paper DOI, PMID or repository URL")
    parser.add_argument("--types", required=True, help="Explicit comma-separated extensions, or all")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-unzip", action="store_true")
    args = parser.parse_args()
    extensions = {value.strip().lower() for value in args.types.split(",") if value.strip()}
    if not extensions:
        parser.error("Select file types explicitly")
    root = Path(os.environ.get("SCIENTIFIC_CLAWBIO_ROOT", "/opt/clawbio"))
    path = root / "source/skills/article-data-fetcher/article_data_fetcher.py"
    spec = importlib.util.spec_from_file_location("clawbio_article_fetcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run(identifier=args.id, file_types=extensions, output_dir=args.output,
               unzip=not args.no_unzip, non_interactive=True)
    # A report alone is not a download. Check every selected artifact and fix
    # the upstream manifest's stale .gz path when it decompressed the file.
    manifest_path = args.output / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}
    failed = []
    for item in manifest.get("files", []):
        path = Path(item.get("local_path", ""))
        if not path.is_file() and path.suffix == ".gz" and not args.no_unzip:
            path = path.with_suffix("")
        if not item.get("downloaded") or not path.is_file() or not path.stat().st_size:
            failed.append(item.get("filename", "unknown"))
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        item.update(local_path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())
    if manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    if not manifest.get("files") or failed:
        parser.exit(1, "Retrieval incomplete; inspect manifest.json. Partial outputs are retained; no complete-data claim.\n")


if __name__ == "__main__":
    main()
