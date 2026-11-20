#!/usr/bin/env python3
"""Verify bundled VBench inputs, or prepare a reproducible batch."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vbench_data import ROOT, prepare, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check bundled CSV, selection and license without network access")
    parser.add_argument("--output", type=Path, default=ROOT / "data/prompts.csv")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".state/vbench-source")
    parser.add_argument("--per-category", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        result = verify(args.output) if args.verify else prepare(args.output, args.cache_dir, per_category=args.per_category, seed=args.seed)
        print(f"VBench batch: {result['rows']} prompts across eight content categories.")
        print(f"Pinned revision: {result['revision']}; input SHA256: {result['input_sha256']}")
        print("This is a generation subset, not a full VBench score.")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
