#!/usr/bin/env python3
"""Project retained adapter cases onto the public runner without changing inputs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from manage_campaign import save


def prepare(cases, reference_base):
    projected = copy.deepcopy(cases)
    seen = set()
    for before, case in zip(cases, projected, strict=True):
        if case["model_id"] != "diffdock" or case["mode"] != "native":
            raise ValueError("Expected frozen native DiffDock cases")
        if case["case_id"] in seen:
            raise ValueError("Duplicate frozen case identity")
        seen.add(case["case_id"])
        for source in case["provenance"]["sources"]:
            path = (reference_base / source["path"]).resolve()
            if not path.is_relative_to(reference_base.resolve()):
                raise ValueError("Reference escapes the retained dataset")
            data = path.read_bytes()
            if len(data) != source["size_bytes"] or hashlib.sha256(data).hexdigest() != source["sha256"]:
                raise ValueError("Retained reference hash/size mismatch")
            source["path"] = str(path)
        reference = (reference_base / case["expected"]["reference_path"]).resolve()
        if not reference.is_relative_to(reference_base.resolve()):
            raise ValueError("Evaluation reference escapes the retained dataset")
        if str(reference) not in {row["path"] for row in case["provenance"]["sources"]}:
            raise ValueError("Evaluation reference lacks frozen checksum")
        case["expected"]["reference_path"] = str(reference)
        assert case["arguments"] == before["arguments"]
    return {"schema_version": 1, "study_id": "diffdock-frozen-candidate-public-replay", "cases": projected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--reference-base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    result = prepare(cases, args.reference_base)
    result["source_cases_sha256"] = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    save(args.output, result)
    print(json.dumps({"cases": len(cases), "source_cases_sha256": result["source_cases_sha256"],
                      "model_arguments_changed": False}))


if __name__ == "__main__":
    main()
