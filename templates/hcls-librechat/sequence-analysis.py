"""Deterministic saved DNA-continuation measurements; no generation or scoring."""

import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import itertools
import json
import math
from pathlib import Path

from scientific_receipts import staged_output


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(raw):
    def invalid(value):
        raise ValueError(f"Nonfinite JSON value {value} is not a measurement.")

    return json.loads(raw, parse_constant=invalid)


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return value


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number.")
    return value


def reference_sequence(raw, reference_id=None):
    """Select one FASTA record or a plain sequence; never concatenate records."""
    text = raw.decode("utf-8")
    records, label, parts = [], None, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if parts or label is not None:
                records.append((label, "".join(parts)))
            label, parts = line[1:], []
        else:
            parts.append(line)
    if parts or label is not None:
        records.append((label, "".join(parts)))
    if reference_id is not None:
        records = [
            (name, seq)
            for name, seq in records
            if name and name.split()[0] == reference_id
        ]
    if len(records) != 1 or not records[0][1]:
        raise ValueError(
            "Select exactly one nonempty reference record; use reference_id for multi-record FASTA."
        )
    name, sequence = records[0]
    if set(sequence.upper()) - set("ACGTN"):
        raise ValueError(
            "Reference contains unsupported non-ACGTN characters; do not silently repair it."
        )
    return name, sequence


def gc(sequence):
    counts = {base: sequence.upper().count(base) for base in "ACGT"}
    canonical = sum(counts.values())
    gc_count = counts["G"] + counts["C"]
    return {
        "length": len(sequence),
        "alphabet": sorted(set(sequence)),
        "canonical_base_count": canonical,
        "other_base_count": len(sequence) - canonical,
        "gc_count": gc_count,
        "gc_fraction_all_positions": gc_count / len(sequence) if sequence else None,
        "gc_fraction_acgt_only": gc_count / canonical if canonical else None,
    }


def operation_measurements(document):
    if document is None:
        return {
            "id": None,
            "model_id": None,
            "status": None,
            "accepted_to_started_seconds": None,
            "started_to_completed_seconds": None,
            "accepted_to_completed_seconds": None,
            "runtime": None,
        }
    if not isinstance(document, dict):
        raise ValueError(
            "Use a saved canonical operation or its structuredContent envelope."
        )
    body = document.get("structuredContent", document)
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("id"), str)
        or not body["id"]
    ):
        raise ValueError(
            "Operation must contain its actual id; raw model results cannot supply invented identities."
        )
    times = {}
    for name in ("accepted_at", "started_at", "completed_at"):
        raw = body.get(name)
        if raw is None:
            times[name] = None
        else:
            if not isinstance(raw, str):
                raise ValueError(f"{name} must be an explicit ISO timestamp.")
            times[name] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if times[name].tzinfo is None:
                raise ValueError("Operation timestamps need explicit time zones.")
    result = {
        key: body.get(key)
        for key in ("id", "model_id", "model_revision", "status", "runtime")
    }
    for title, first, last in [
        ("accepted_to_started", "accepted_at", "started_at"),
        ("started_to_completed", "started_at", "completed_at"),
        ("accepted_to_completed", "accepted_at", "completed_at"),
    ]:
        value = (
            (times[last] - times[first]).total_seconds()
            if times[first] and times[last]
            else None
        )
        result[title + "_seconds"] = number(value, title) if value is not None else None
    return result


def analyze_case(case, request, result, reference, operation=None):
    if not isinstance(request, dict) or not isinstance(result, dict):
        raise ValueError(
            "Use saved raw request and result objects, not compact summaries."
        )
    prefix = request.get("sequence")
    if not isinstance(prefix, str) or not prefix or set(prefix.upper()) - set("ACGTN"):
        raise ValueError(
            "Request sequence must be nonempty DNA; original bytes are not repaired."
        )
    requested = integer(request.get("num_tokens"), "num_tokens", 1)
    seed = integer(request.get("random_seed"), "random_seed")
    start = integer(case.get("start_zero_based"), "start_zero_based")
    end = start + len(prefix)
    if end + requested > len(reference):
        raise ValueError(
            "Reference is too short for the declared prefix and continuation window."
        )
    if prefix.upper() != reference[start:end].upper():
        raise ValueError(
            "Original request prefix does not match the declared reference window."
        )
    returned = result.get("sequence")
    if not isinstance(returned, str):
        raise ValueError(
            "Current Evo2 saved result requires sequence:string; no heuristic search for plausible DNA."
        )
    mode = case.get("sequence_mode", "suffix")
    if mode == "suffix":
        suffix = returned
    elif mode == "prefix-and-suffix":
        if not returned.startswith(prefix):
            raise ValueError(
                "Declared returned prefix does not exactly match the original request."
            )
        suffix = returned[len(prefix) :]
    else:
        raise ValueError("sequence_mode must be suffix or explicit prefix-and-suffix.")
    next_reference = reference[end : end + requested]
    flags = []
    if len(suffix) != requested:
        flags.append("underfilled" if len(suffix) < requested else "overfilled")
    if set(suffix.upper()) - set("ACGT"):
        flags.append("non_acgt_output_retained")
    elapsed = result.get("elapsed_ms")
    if elapsed is not None:
        number(elapsed, "elapsed_ms")
    per_token = result.get("elapsed_ms_per_token")
    if per_token is not None:
        if not isinstance(per_token, list):
            raise ValueError("elapsed_ms_per_token must be a list or null.")
        for value in per_token:
            number(value, "elapsed_ms_per_token")
        if len(per_token) != len(suffix):
            flags.append("per_token_timing_length_mismatch")
    probabilities = result.get("sampled_probs")
    if probabilities is not None:
        if not isinstance(probabilities, list):
            raise ValueError(
                "sampled_probs must be a saved list or null, not a derived likelihood."
            )
        for value in probabilities:
            if number(value, "sampled_probs") > 1:
                raise ValueError("Sampled probabilities must lie between zero and one.")
        if len(probabilities) != len(suffix):
            flags.append("sampled_probability_length_mismatch")
    op = operation_measurements(operation)
    if op["status"] is not None and op["status"] != "succeeded":
        flags.append("operation_not_succeeded")
    overlap = min(len(suffix), len(next_reference))
    matches = sum(
        a.upper() == b.upper() and a.upper() in "ACGT"
        for a, b in zip(suffix, next_reference)
    )
    return {
        "id": case["id"],
        "start_zero_based": start,
        "prefix_length": len(prefix),
        "request": request,
        "request_seed_not_determinism_proof": seed,
        "reference_prefix_exact_case_match": prefix == reference[start:end],
        "prefix_sha256": digest(prefix.encode()),
        "sequence_mode": mode,
        "returned_sequence": returned,
        "new_sequence": suffix,
        "requested_new_bases": requested,
        "new_sequence_sha256": digest(suffix.encode()),
        "prompt": gc(prefix),
        "suffix": gc(suffix),
        "next_reference": gc(next_reference),
        "reference_suffix_sha256": digest(next_reference.encode()),
        "reference_matching_acgt_positions": matches,
        "reference_overlap_positions": overlap,
        "reference_requested_positions": requested,
        "reference_match_fraction_requested": matches / requested,
        "reference_match_fraction_overlap": matches / overlap if overlap else None,
        "model_elapsed_ms": elapsed,
        "model_elapsed_seconds": str(Decimal(str(elapsed)) / 1000)
        if elapsed is not None
        else None,
        "model_elapsed_ms_per_token": per_token,
        "sampled_probs": probabilities,
        "logits": result.get("logits"),
        "result_fields": sorted(result),
        "operation": op,
        "flags": flags,
    }


def analyze_plan(plan, base=Path(".")):
    if (
        not isinstance(plan, dict)
        or not isinstance(plan.get("cases"), list)
        or not plan["cases"]
    ):
        raise ValueError(
            "Provide nonempty cases with explicit reference coordinates and original files."
        )
    if not isinstance(plan.get("title", ""), str):
        raise ValueError("Report title must be text.")
    sources = []

    def read(name, role):
        if not isinstance(name, str) or not name:
            raise ValueError(f"{role} requires an actual source file path.")
        path = Path(name)
        if not path.is_absolute():
            path = base / path
        raw = path.read_bytes()
        sources.append(
            {
                "role": role,
                "path": str(path),
                "size_bytes": len(raw),
                "sha256": digest(raw),
            }
        )
        return raw

    raw = read(plan.get("reference_file"), "reference")
    label, reference = reference_sequence(raw, plan.get("reference_id"))
    rows, seen = [], set()
    for case in plan["cases"]:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not case["id"].strip()
            or case["id"] in seen
        ):
            raise ValueError(
                "Every case needs a unique nonempty id; duplicates are not independent cases."
            )
        seen.add(case["id"])
        request = load_json(read(case.get("input_file"), case["id"] + ":request"))
        result = load_json(read(case.get("result_file"), case["id"] + ":result"))
        operation = (
            load_json(read(case["operation_file"], case["id"] + ":operation"))
            if case.get("operation_file") is not None
            else None
        )
        rows.append(analyze_case(case, request, result, reference, operation))
    pairs = []

    def controls(row):
        return {
            key: value for key, value in row["request"].items() if key != "random_seed"
        }

    for left, right in itertools.combinations(rows, 2):
        if left["start_zero_based"] != right["start_zero_based"] or controls(
            left
        ) != controls(right):
            continue
        first, second = left["new_sequence"], right["new_sequence"]
        overlap = min(len(first), len(second))
        matching = sum(a == b for a, b in zip(first, second))
        pairs.append(
            {
                "left": left["id"],
                "right": right["id"],
                "left_seed": left["request_seed_not_determinism_proof"],
                "right_seed": right["request_seed_not_determinism_proof"],
                "kind": "same-seed-repeat"
                if left["request_seed_not_determinism_proof"]
                == right["request_seed_not_determinism_proof"]
                else "different-seed",
                "overlap_positions": overlap,
                "matching_positions": matching,
                "hamming_distance": len(first) - matching
                if len(first) == len(second)
                else None,
                "identity_fraction_overlap": matching / overlap if overlap else None,
                "same_length": len(first) == len(second),
                "identical_suffix": first == second,
            }
        )
    return {
        "schema": "scientific-ai/dna-continuation/v1",
        "title": plan.get("title", "Saved DNA continuation measurements"),
        "reference_header": label,
        "reference_length": len(reference),
        "cases": rows,
        "case_count": len(rows),
        "pairs": pairs,
        "pair_count": len(pairs),
        "sources": sources,
        "inference_submitted": False,
        "scientific_claims_validated": False,
        "limitations": [
            "Generation is not reference likelihood or variant-effect scoring; no unavailable scores are inferred.",
            "Returned sampled probabilities/logits are retained with their field names, not relabelled reference scores.",
            "Case-insensitive ACGT reference matches are descriptive. Unknown symbols, underfill, overfill and poor agreement remain visible.",
            "GC reports both all-position and canonical-ACGT denominators; ambiguous bases are not silently removed.",
            "Only identical reference windows and sampling controls are paired. Seeds alone do not prove runtime determinism or independent samples.",
            "Model milliseconds, service intervals, queue/activation wait and GPU occupancy are different. Accepted-to-started is not pure cold start.",
            "Training-data overlap is unknown. No gene-function, fitness, clinical or full-paper benchmark validation is claimed.",
        ],
    }


def publish(plan_file, output_dir):
    plan_file, output_dir = Path(plan_file), Path(output_dir)
    raw = plan_file.read_bytes()
    report = analyze_plan(load_json(raw), plan_file.parent)
    report["plan_sha256"] = digest(raw)
    columns = [
        "id",
        "start_zero_based",
        "seed",
        "operation_id",
        "prefix_length",
        "new_length",
        "requested_new_bases",
        "gc_count",
        "gc_fraction_all_positions",
        "reference_matching_acgt_positions",
        "reference_requested_positions",
        "reference_match_fraction_requested",
        "model_elapsed_ms",
        "model_elapsed_seconds",
        "new_sequence_sha256",
        "flags",
    ]
    exported = []
    for row in report["cases"]:
        exported.append(
            {key: row[key] for key in columns if key in row}
            | {
                "seed": row["request_seed_not_determinism_proof"],
                "operation_id": row["operation"]["id"],
                "new_length": row["suffix"]["length"],
                "gc_count": row["suffix"]["gc_count"],
                "gc_fraction_all_positions": row["suffix"]["gc_fraction_all_positions"],
                "flags": ";".join(row["flags"]),
            }
        )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(exported)

    def cell(value):
        return (
            "unavailable"
            if value is None
            else str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
        )

    lines = [
        f"# {cell(report['title'])}",
        "",
        f"Cases measured: {report['case_count']}; explicitly comparable pairs: {report['pair_count']}.",
        f"Reference: {cell(report['reference_header'])}; {report['reference_length']} bases.",
        "",
        "GC denominator below is every returned suffix position. Reference fraction denominator is the requested continuation length.",
        "",
        "| Case | Seed | New / requested bases | GC fraction | Reference matches / requested | Model elapsed (ms) | Model elapsed (s) | Flags |",
        "| --- | ---: | --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in exported:
        lines.append(
            "| "
            + " | ".join(
                cell(value)
                for value in [
                    row["id"],
                    row["seed"],
                    f"{row['new_length']} / {row['requested_new_bases']}",
                    row["gc_fraction_all_positions"],
                    f"{row['reference_matching_acgt_positions']} / {row['reference_requested_positions']}",
                    row["model_elapsed_ms"],
                    row["model_elapsed_seconds"],
                    row["flags"] or "none",
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## Seed/repeat comparisons",
        "",
        "| Left | Right | Kind | Matching / compared positions | Hamming distance (equal lengths only) | Identical suffix |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for pair in report["pairs"]:
        lines.append(
            "| "
            + " | ".join(
                cell(value)
                for value in [
                    pair["left"],
                    pair["right"],
                    pair["kind"],
                    f"{pair['matching_positions']} / {pair['overlap_positions']}",
                    pair["hamming_distance"],
                    pair["identical_suffix"],
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## Provenance and limits",
        "",
        "Original requests, operation identities, returned sequences/probabilities, explicit timing units and every source hash are retained in metrics.json. Missing identity/timing remains unavailable.",
        "",
        *report["limitations"],
    ]
    files = {
        "metrics.json": (json.dumps(report, indent=2, allow_nan=False) + "\n").encode(),
        "rows.csv": buffer.getvalue().encode(),
        "report.md": ("\n".join(lines) + "\n").encode(),
    }
    manifest = {
        "schema": "scientific-ai/dna-continuation-artifacts/v1",
        "state": "complete",
        "inference_submitted": False,
        "scientific_claims_validated": False,
        "plan_sha256": digest(raw),
        "helper_sha256": digest(Path(__file__).read_bytes()),
        "inputs": report["sources"],
        "artifacts": [
            {"path": name, "size_bytes": len(data), "sha256": digest(data)}
            for name, data in files.items()
        ],
    }
    files["completion-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    for name, data in files.items():
        with staged_output(output_dir / name) as staged:
            staged.path.write_bytes(data)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    arguments = parser.parse_args()
    manifest = publish(arguments.plan, arguments.output_dir)
    print(
        json.dumps(
            {
                "state": manifest["state"],
                "artifacts": manifest["artifacts"],
                "inference_submitted": False,
            }
        )
    )


if __name__ == "__main__":
    main()
