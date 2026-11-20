#!/usr/bin/env python3
"""Prepare 1,000 verified Dolly reference passages for the Serverless Job search example."""
from pathlib import Path
import argparse
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from data import manifest_digest, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/job-documents"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".state/job-data-cache"))
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        manifest = prepare(args.output_dir, args.cache_dir)
        print(json.dumps({"dataset": manifest["dataset"], "revision": manifest["revision"],
                          **manifest["totals"], "output": str(args.output_dir),
                          "manifest_sha256": manifest_digest(args.output_dir),
                          "preparation_seconds": round(time.perf_counter() - started, 3)}, indent=2))
    except (OSError, ValueError, KeyError) as exc:
        print("Error:", str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
