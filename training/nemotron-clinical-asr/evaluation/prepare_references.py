#!/usr/bin/env python3
"""Attach a frozen lexical reference vocabulary, without accessing predictions."""
import argparse
import hashlib
import json
from pathlib import Path

from score_asr import occurrences, tokens, index_jsonl


def annotate(row, lexicon):
    sequence = tokens(row["text"])
    return {**row, "keywords": [{"text": term, "category": category}
            for category, values in lexicon["categories"].items() for term in values if occurrences(sequence, tokens(term))],
            "example_exposure": row.get("example_exposure", "training_manifest_membership_only" if row.get("split") == "train" else row.get("split", "unspecified")),
            "clinical_annotation_status": "lexicon_matching_only_not_human_semantic_adjudication"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, default=Path(__file__).with_name("clinical_terms.json"))
    args = parser.parse_args()
    receipt = args.output.with_suffix(".references.json")
    if args.output.exists() or receipt.exists():
        raise ValueError("Reference output exists; use a new version")
    lexicon = json.loads(args.lexicon.read_text())
    rows = [annotate(row, lexicon) for row in index_jsonl(args.manifest).values()]
    data = ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(data)
    counts = sum(len(occurrences(tokens(row["text"]), tokens(term["text"]))) for row in rows for term in row["keywords"])
    summary = {"reference_sha256": hashlib.sha256(data).hexdigest(), "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
               "lexicon_sha256": hashlib.sha256(args.lexicon.read_bytes()).hexdigest(), "examples": len(rows),
               "clinical_keyword_occurrences": counts, "source": "human references only; no model outputs accessed",
               "semantic_review": "PENDING; lexical annotations are not clinical factual labels"}
    with receipt.open("x") as stream:
        stream.write(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
