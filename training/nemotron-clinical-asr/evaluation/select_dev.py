#!/usr/bin/env python3
"""Freeze a reference-enriched dev cohort; never read ASR predictions."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_references import annotate
from score_asr import index_jsonl

RULE = {"version": 1, "anchor": "earliest chronological segment containing a frozen lexicon term",
        "fallback": "floor((n-1)*q) for q=0.25,0.50,0.75",
        "rank": "distance to nearest anchor, then chronological index", "min_seconds": 30, "max_seconds": 45,
        "unit": "whole segment, emitted chronologically; skip additions above maximum; record all missing/short conversations",
        "scope": "reference-enriched dev, not population benchmark or final held-out test"}


def select(rows, lexicon):
    rows = sorted((annotate(row, lexicon) for row in rows), key=lambda row: (row["source_word_start"], row["id"]))
    medical = [i for i, row in enumerate(rows) if row["keywords"]]
    anchors = [medical[0]] if medical else [int((len(rows)-1)*q) for q in (.25, .5, .75)]
    ranked = sorted(range(len(rows)), key=lambda i: (min(abs(i-a) for a in anchors), i))
    chosen, duration = [], 0.
    for index in ranked:
        if duration + rows[index]["duration"] <= RULE["max_seconds"] + 1e-6:
            chosen.append(index)
            duration += rows[index]["duration"]
        if duration >= RULE["min_seconds"]:
            break
    return [rows[i] for i in sorted(chosen)], {"anchor": "medical" if medical else "fixed_fallback", "seconds": duration,
                                             "shortfall": duration < RULE["min_seconds"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aligned-dev", type=Path, required=True)
    parser.add_argument("--source-dev", type=Path, required=True, help="Frozen full-conversation dev NFA manifest")
    parser.add_argument("--lexicon", type=Path, default=Path(__file__).with_name("clinical_terms.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = args.output.with_suffix(".selection.json")
    if args.output.exists() or receipt.exists():
        raise ValueError("Frozen output exists; use a new version")
    sources = index_jsonl(args.source_dev)
    if not sources or any(row["split"] != "dev" for row in sources.values()):
        raise ValueError("Expected nonempty dev-only source")
    grouped = {row["conversation_id"]: [] for row in sources.values()}
    for row in index_jsonl(args.aligned_dev).values():
        if row["split"] != "dev" or row["conversation_id"] not in grouped or not .5 <= row["duration"] <= 30:
            raise ValueError("Invalid dev membership/duration")
        grouped[row["conversation_id"]].append(row)
    lexicon = json.loads(args.lexicon.read_text())
    rows, audit = [], {}
    for identity, segments in sorted(grouped.items()):
        if not segments:
            audit[identity] = {"missing": True, "reason": "no eligible alignment supplied; join original alignment failures"}
            continue
        selected, audit[identity] = select(segments, lexicon)
        rows.extend({**row, "example_exposure": "dev_used_for_selection_not_final_test"} for row in selected)
    data = ("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(data)
    report = {"rule": RULE, "selector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "lexicon_sha256": hashlib.sha256(args.lexicon.read_bytes()).hexdigest(), "source_dev_sha256": hashlib.sha256(args.source_dev.read_bytes()).hexdigest(),
              "aligned_dev_sha256": hashlib.sha256(args.aligned_dev.read_bytes()).hexdigest(), "selected_sha256": hashlib.sha256(data).hexdigest(),
              "examples": len(rows), "seconds": sum(r["duration"] for r in rows), "conversations": audit, "hypotheses_accessed": False}
    with receipt.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "examples": len(rows), "seconds": report["seconds"]}))


if __name__ == "__main__":
    main()
