#!/usr/bin/env python3
"""Attach a frozen lexical reference vocabulary, without accessing predictions."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from score_asr import occurrences, tokens, index_jsonl


def annotate(row, lexicon):
    sequence = tokens(row["text"])
    return {**row, "keywords": [{"text": term, "category": category}
            for category, values in lexicon["categories"].items() for term in values if occurrences(sequence, tokens(term))],
            "example_exposure": row.get("example_exposure", "training_manifest_membership_only" if row.get("split") == "train" else row.get("split", "unspecified")),
            "clinical_annotation_status": "lexicon_matching_only_not_human_semantic_adjudication"}


def map_published_audio(rows, publication, run_id):
    """Map only exact published clinical clips; never infer a bucket key."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,100}", run_id):
        raise ValueError("Invalid cloud run ID")
    if publication.get("status") != "completed" or publication.get("run_id") != run_id:
        raise ValueError("Matching completed publication required")
    objects = {}
    for item in publication["objects"]:
        key = item["key"]
        if key in objects or not key.startswith("runs/" + run_id + "/") or ".." in PurePosixPath(key).parts:
            raise ValueError("Invalid or duplicate publication key")
        objects[key] = item
    source_prefix = PurePosixPath("/output") / run_id / "segments/audio"
    mapped, changes = [], []
    for row in rows:
        path = PurePosixPath(row["audio_filepath"])
        if ".." in path.parts or path.parent != source_prefix or path.name != row["id"] + ".wav":
            raise ValueError("Expected exact /output/<run-id>/segments/audio/<id>.wav path")
        key = f"runs/{run_id}/segments/audio/{path.name}"
        item = objects.get(key)
        if not item or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) or item.get("bytes", 0) <= 0:
            raise ValueError("Exact published clip hash and byte count required")
        if row.get("audio_sha256") and row["audio_sha256"] != item["sha256"]:
            raise ValueError("Manifest audio hash differs from publication")
        target = "/data/clinical-speech/" + key
        mapped.append({**row, "audio_filepath": target, "audio_sha256": item["sha256"]})
        changes.append({"id": row["id"], "original_audio_filepath": str(path),
                        "audio_filepath": target, "audio_sha256": item["sha256"],
                        "audio_hash_added": not bool(row.get("audio_sha256"))})
    return mapped, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, default=Path(__file__).with_name("clinical_terms.json"))
    parser.add_argument("--cloud-run-id", help="Explicit source cloud-run identity; requires --cloud-publication")
    parser.add_argument("--cloud-publication", type=Path, help="Verified completed.json for mapping published /output clip paths into the bucket mount")
    args = parser.parse_args()
    receipt = args.output.with_suffix(".references.json")
    if args.output.exists() or receipt.exists():
        raise ValueError("Reference output exists; use a new version")
    if bool(args.cloud_run_id) != bool(args.cloud_publication):
        raise ValueError("Provide cloud run ID and completed publication together")
    lexicon = json.loads(args.lexicon.read_text())
    originals = list(index_jsonl(args.manifest).values())
    mapping = None
    if args.cloud_publication:
        originals, changes = map_published_audio(originals, json.loads(args.cloud_publication.read_text()), args.cloud_run_id)
        mapping = {"run_id": args.cloud_run_id, "publication_sha256": hashlib.sha256(args.cloud_publication.read_bytes()).hexdigest(),
                   "rows": changes, "scope": "Exact publication-validated path/hash mapping; IDs, order and reference text retained. Cloud evaluator independently verifies actual audio bytes before inference."}
    rows = [annotate(row, lexicon) for row in originals]
    data = ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(data)
    counts = sum(len(occurrences(tokens(row["text"]), tokens(term["text"]))) for row in rows for term in row["keywords"])
    summary = {"reference_sha256": hashlib.sha256(data).hexdigest(), "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
               "lexicon_sha256": hashlib.sha256(args.lexicon.read_bytes()).hexdigest(), "examples": len(rows),
               "clinical_keyword_occurrences": counts, "source": "human references only; no model outputs accessed",
               "semantic_review": "PENDING; lexical annotations are not clinical factual labels"}
    if mapping is not None:
        summary["cloud_audio_mapping"] = mapping
    with receipt.open("x") as stream:
        stream.write(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
