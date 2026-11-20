#!/usr/bin/env python3
"""Verify a complete video batch, including its input joins and MP4 decoding."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from generate import RecipeError, completed, digest, read_json, read_prompts, validate_video


def check(output: Path) -> dict:
    summary = read_json(output / "summary.json")
    rows = read_prompts(output / "input.csv")
    if summary.get("schema") != 2 or summary.get("input_rows") != len(rows) or summary.get("completed") != len(rows):
        raise RecipeError("The batch is incomplete or its input count is inconsistent.")
    if summary.get("input_sha256") != digest(output / "input.csv"):
        raise RecipeError("The input CSV checksum changed.")
    exported = summary.get("outputs", [])
    if [item.get("id") for item in exported] != [row["id"] for row in rows]:
        raise RecipeError("Result IDs differ from the input order.")
    source = summary.get("input_source", {})
    if source.get("dataset") == "VBench":
        provenance = read_json(output / "input.source.json")
        if provenance.get("input_sha256") != summary["input_sha256"] or provenance.get("selection") != rows:
            raise RecipeError("VBench provenance differs from the input.")
        license_hash = provenance["source_manifest"]["files"]["LICENSE"]["sha256"]
        if digest(output / "DATA_LICENSE") != license_hash or not (output / "DATA_SOURCE.md").read_text().strip():
            raise RecipeError("VBench license or attribution is missing or changed.")
    frames = []
    for row, item in zip(rows, exported):
        fields = {**summary["settings"], "model": summary["model"], "prompt": row["prompt"], "seed": row["seed"]}
        meta = completed(output, row, fields)
        if meta is None or item.get("input_row") != row or item.get("sha256") != meta["sha256"]:
            raise RecipeError("A result record differs from its input or completed clip.")
        validation = validate_video(output / (row["id"] + ".mp4"), fields)
        if item.get("validation") != validation:
            raise RecipeError("A clip's decoded properties differ from the saved record.")
        frames.append(validation["frames_decoded"])
    with (output / "clips.csv").open(encoding="utf-8", newline="") as stream:
        manifest = list(csv.DictReader(stream))
    if [row["id"] for row in manifest] != [row["id"] for row in rows]:
        raise RecipeError("The CSV clip manifest differs from the completed batch.")
    return {"completed": len(rows), "dataset": source.get("dataset"), "frames_per_clip": sorted(set(frames)),
            "input_sha256": summary["input_sha256"], "decode_passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.output), indent=2))
    except (OSError, ValueError, KeyError, RecipeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
