#!/usr/bin/env python3
"""Fail-closed paired scoring; retain worsened and empty hypotheses explicitly."""
import argparse
import hashlib
import json
from pathlib import Path

from score_asr import aggregate, index_jsonl, score_one


def paired_scores(refs, base, tuned):
    if not refs or set(refs) != set(base) or set(refs) != set(tuned):
        raise ValueError("Equal nonempty reference/base/tuned ID sets required; report omitted or failed requests separately")
    fields = ("base_model", "base_revision", "nemo_revision", "precision", "chunk_size_ms", "language")
    identities = {"base": set(), "tuned": set()}
    for identity, ref in refs.items():
        left, right = base[identity], tuned[identity]
        if not left.get("input_sha256") or left["input_sha256"] != right.get("input_sha256"):
            raise ValueError("Paired input hashes missing/different:" + identity)
        if ref.get("audio_sha256") and ref["audio_sha256"] != left["input_sha256"]:
            raise ValueError("Reference input hash differs:" + identity)
        for field in fields:
            if field not in left.get("runtime", {}) or left["runtime"][field] != right.get("runtime", {}).get(field):
                raise ValueError("Runtime comparison setting missing/different:" + field)
        if not left["runtime"].get("checkpoint_sha256") or not right["runtime"].get("checkpoint_sha256"):
            raise ValueError("Both exact checkpoint hashes required")
        if left["runtime"].get("fine_tuned") is not False or right["runtime"].get("fine_tuned") is not True:
            raise ValueError("Explicit base and fine-tuned runtime identities required")
        identities["base"].add(left["runtime"]["checkpoint_sha256"])
        identities["tuned"].add(right["runtime"]["checkpoint_sha256"])
    if any(len(values) != 1 for values in identities.values()):
        raise ValueError("Mixed checkpoint hashes within a cohort")
    scores = {}
    for label, predictions in (("base", base), ("tuned", tuned)):
        rows = [score_one(refs[identity], predictions[identity]) for identity in sorted(refs)]
        scores[label] = {"aggregate": aggregate(rows), "results": rows}
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("reference", "base", "tuned", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Score output exists; use a new version")
    scores = paired_scores(index_jsonl(args.reference), index_jsonl(args.base), index_jsonl(args.tuned))
    hashes = {field + "_sha256": hashlib.sha256(getattr(args, field).read_bytes()).hexdigest() for field in ("reference", "base", "tuned")}
    report = {"inputs": hashes, "scores": scores, "normalization": "NFKC lowercase; punctuation ignored except decimal points/in-word apostrophes; no number or synonym expansion",
              "keyword_error": "Fraction of reference keyword occurrences whose entire aligned token span is not exactly retained. Extra occurrences reported separately. Overlapping lexicon phrases counted separately.",
              "semantic_clinical_review": "PENDING; no automatic dose/negation/speaker factual accuracy claim", "timing": "Unpaced offline runtime includes warmup; not microphone latency or endpoint SLA"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({label: data["aggregate"] for label, data in scores.items()}, indent=2))


if __name__ == "__main__":
    main()
