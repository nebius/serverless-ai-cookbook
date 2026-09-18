#!/usr/bin/env python3
"""Re-evaluate immutable saved results, preserving original verdict evidence.

This is an offline evaluator correction, not a new model test or retry. Only
terminal verified/semantic_failed receipts are eligible. No credentials/network.
"""

import argparse
import json
from pathlib import Path

from datasets import digest
from evaluators import evaluate
from manage_campaign import now, save
from run_campaign import journal


def rebuild_summaries(results: Path) -> list[dict]:
    """Reconcile finished-cohort projections against authoritative receipts."""
    rows = {json.loads(path.read_text())["case_id"]: json.loads(path.read_text())
            for path in results.rglob("receipt.json")}
    updates = []
    for path in sorted(results.rglob("summary.json")):
        previous = json.loads(path.read_text())
        if not isinstance(previous, list):
            continue
        updated = [rows.get(row.get("case_id"), row) for row in previous]
        if previous != updated:
            before_hash = digest(path.read_bytes())
            save(path.with_name(f"summary-before-{before_hash[:16]}.json"), previous)
            save(path, updated)
            journal(path.parent, {"event": "summary_rebuilt_from_receipts", "previous_summary_sha256": before_hash,
                                 "rows": len(updated), "gpu_rerun": False})
            updates.append({"path": str(path), "rows": len(updated)})
    return updates


def run(manifest_path: Path, results: Path, model_id: str, reason: str, rebuild: bool = False) -> dict:
    cases = {case["case_id"]: case for case in json.loads(manifest_path.read_text())["cases"]}
    corrected = []
    for path in sorted(results.rglob("receipt.json")):
        receipt = json.loads(path.read_text())
        case = cases.get(receipt.get("case_id"))
        if not case or case["model_id"] != model_id or receipt.get("state") not in {"verified", "semantic_failed"}:
            continue
        folder = path.parent
        previous = json.loads((folder / "evaluation.json").read_text())
        result = json.loads((folder / "result.json").read_text())
        updated = evaluate(case, result, manifest_path.parent)
        if case["mode"] == "scientific-batch" and result.get("platform_semantic_validation", {}).get("status") != "passed":
            updated.update(service_semantic_pass=False, platform_semantic_validation_failed=True)
        if previous == updated:
            continue
        previous_hash = digest((folder / "evaluation.json").read_bytes())
        backup = folder / f"evaluation-before-{previous_hash[:16]}.json"
        if not backup.exists():
            save(backup, previous)
        journal(folder, {"event": "offline_evaluator_correction", "reason": reason,
                         "previous_state": receipt["state"], "previous_evaluation": previous,
                         "previous_evaluation_sha256": previous_hash,
                         "new_service_semantic_pass": updated["service_semantic_pass"],
                         "result_sha256": digest((folder / "result.json").read_bytes()),
                         "gpu_rerun": False})
        save(folder / "evaluation.json", updated)
        receipt.update(state="verified" if updated["service_semantic_pass"] else "semantic_failed",
                       service_semantic_pass=updated["service_semantic_pass"], reevaluated_at=now(),
                       reevaluation_reason=reason)
        save(path, receipt)
        corrected.append({"case_id": case["case_id"], "pass": updated["service_semantic_pass"]})
    return {"corrected": len(corrected), "cases": corrected,
            "summaries_rebuilt": rebuild_summaries(results) if rebuild else []}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--rebuild-summaries", action="store_true", help="Use only after cohort workers finish.")
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.results, args.model_id, args.reason, args.rebuild_summaries), indent=2))
