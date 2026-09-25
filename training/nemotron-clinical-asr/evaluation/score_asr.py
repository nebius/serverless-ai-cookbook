#!/usr/bin/env python3
"""Paired ASR scoring with explicit term-level keyword error and no model calls."""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


def tokens(text: str) -> list[str]:
    # Do not expand numbers or abbreviations, drop negation, or normalize doses.
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    return re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+(?:'[^\W\d_]+)?", text, flags=re.UNICODE)


def align(ref: list[str], hyp: list[str]):
    """Levenshtein alignment: deterministic tie-break diagonal, deletion, insertion."""
    costs = [list(range(len(hyp) + 1))]
    for i, ref_token in enumerate(ref, 1):
        row = [i]
        for j, hyp_token in enumerate(hyp, 1):
            row.append(min(costs[-1][j-1] + (ref_token != hyp_token), costs[-1][j] + 1, row[-1] + 1))
        costs.append(row)
    i, j, operations, mapping = len(ref), len(hyp), [], {}
    while i or j:
        if i and j and costs[i][j] == costs[i-1][j-1] + (ref[i-1] != hyp[j-1]):
            op = "equal" if ref[i-1] == hyp[j-1] else "substitution"
            operations.append(op)
            mapping[i-1] = j-1
            i -= 1
            j -= 1
        elif i and costs[i][j] == costs[i-1][j] + 1:
            operations.append("deletion")
            mapping[i-1] = None
            i -= 1
        else:
            operations.append("insertion")
            j -= 1
    return Counter(operations), mapping


def occurrences(sequence: list[str], phrase: list[str]):
    if not phrase:
        return []
    return [i for i in range(len(sequence)-len(phrase)+1) if sequence[i:i+len(phrase)] == phrase]


def score_one(reference: dict, prediction: dict) -> dict:
    ref, hyp = tokens(reference["text"]), tokens(prediction["text"])
    counts, mapping = align(ref, hyp)
    terms = []
    seen = set()
    for keyword in reference.get("keywords", []):
        term = tokens(keyword["text"])
        identity = (keyword.get("category", "clinical"), tuple(term))
        if identity in seen:
            continue
        seen.add(identity)
        starts = occurrences(ref, term)
        if not starts:
            raise ValueError(f"Keyword {keyword['text']!r} absent from reference {reference['id']}")
        correct = 0
        for start in starts:
            mapped = [mapping.get(i) for i in range(start, start+len(term))]
            if None not in mapped and mapped == list(range(mapped[0], mapped[0]+len(term))):
                if hyp[mapped[0]:mapped[0]+len(term)] == term:
                    correct += 1
        predicted = len(occurrences(hyp, term))
        terms.append({"text": keyword["text"], "category": identity[0], "reference_count": len(starts),
                      "correct_count": correct, "error_count": len(starts)-correct,
                      "unsupported_occurrences": max(0, predicted-correct)})
    return {"id": reference["id"], "reference_words": len(ref), "substitutions": counts["substitution"],
            "deletions": counts["deletion"], "insertions": counts["insertion"],
            "wer": (counts["substitution"]+counts["deletion"]+counts["insertion"])/len(ref) if ref else None,
            "keywords": terms,
            "audio_duration_seconds": reference.get("duration"),
            "elapsed_seconds": prediction.get("elapsed_seconds"),
            "time_to_first_partial_seconds": prediction.get("time_to_first_partial_seconds"),
            "finalization_seconds": prediction.get("finalization_seconds"),
            "example_exposure": reference.get("example_exposure", reference.get("split", "unspecified"))}


def index_jsonl(path: Path) -> dict:
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        identity = item.get("id", item.get("conversation_id"))
        if identity is None or identity in result:
            raise ValueError(f"Missing or duplicate id in {path}: {identity}")
        result[identity] = {**item, "id": identity}
    return result


def aggregate(rows: list[dict]) -> dict:
    words = sum(row["reference_words"] for row in rows)
    errors = {k: sum(row[k] for row in rows) for k in ("substitutions", "deletions", "insertions")}
    term_totals = Counter()
    categories = {}
    for row in rows:
        for term in row["keywords"]:
            counts = {k: term[k] for k in ("reference_count", "correct_count", "error_count", "unsupported_occurrences")}
            term_totals.update(counts)
            categories.setdefault(term["category"], Counter()).update(counts)
    def term_metrics(counts):
        total, correct, errors, extra = [counts[x] for x in ("reference_count", "correct_count", "error_count", "unsupported_occurrences")]
        return {**dict(counts), "keyword_error_rate": errors/total if total else None,
                "keyword_recall": correct/total if total else None,
                "keyword_precision": correct/(correct+extra) if correct+extra else None}
    timed = [row for row in rows if row["elapsed_seconds"] is not None and row["audio_duration_seconds"]]
    return {"examples": len(rows), "reference_words": words, **errors,
            "wer": sum(errors.values())/words if words else None,
            "clinical_keywords": term_metrics(term_totals),
            "keywords_by_category": {category: term_metrics(value) for category, value in categories.items()},
            "real_time_factor": sum(r["elapsed_seconds"] for r in timed)/sum(r["audio_duration_seconds"] for r in timed) if timed else None,
            "timed_examples": len(timed),
            "dose_negation_speaker_semantic_accuracy": None,
            "semantic_accuracy_note": "PENDING independent human adjudication; keyword matching is not a semantic safety assessment."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Score output exists; use a new version")
    refs, preds = index_jsonl(args.reference), index_jsonl(args.predictions)
    if set(refs) != set(preds):
        raise ValueError(f"Paired scoring requires equal ids; missing={set(refs)-set(preds)} unexpected={set(preds)-set(refs)}")
    for identity, reference in refs.items():
        if reference.get("audio_sha256") and preds[identity].get("input_sha256") != reference["audio_sha256"]:
            raise ValueError(f"Prediction input hash mismatch or missing: {identity}")
    rows = [score_one(refs[identity], preds[identity]) for identity in sorted(refs)]
    exposures = sorted({row["example_exposure"] for row in rows})
    result = {"schema_version": 1,
              "normalization": "Unicode NFKC, lowercase, punctuation ignored except decimal points and in-word apostrophes; no numeric/abbreviation expansion",
              "keyword_error_definition": "Fraction of annotated reference term occurrences whose full token span is not exactly preserved at its aligned position; substitutions/deletions, not generic WER. Extra observed occurrences reported separately.",
              "aggregate": aggregate(rows),
              "by_exposure": {exposure: aggregate([row for row in rows if row["example_exposure"] == exposure]) for exposure in exposures},
              "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps(result["aggregate"], indent=2))


if __name__ == "__main__":
    main()
