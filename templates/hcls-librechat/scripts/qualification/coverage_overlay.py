"""Freeze a dated evidence overlay; do not infer readiness or count model calls.

The parent campaign aggregator owns request denominators. This helper only
reconciles the App inventory and pins explicitly reviewed coverage statements.
It never queries the platform or modifies an original evidence file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DIMENSIONS = ("service_api", "natural_client", "scientific_correctness", "snapshot")


def configured_identities(configmaps):
    """Record selected configuration, never attach it to historical execution."""
    identities = {}
    for configmap in configmaps.get("items", []):
        data = configmap.get("data", {})
        if "deployment-runtimes.json" in data:
            for model_id, entry in json.loads(data["deployment-runtimes.json"])["models"].items():
                record = entry["record"]
                identities[model_id] = {
                    "kind": "captured_serving_selection",
                    "runtime_image_digest": record["runtime"]["image"]["digest"],
                    "model_revision": record["model"]["source"]["revision"],
                    "qualification_inherited_by_overlay": False,
                }
        if "execution-map.json" in data:
            for entry in json.loads(data["execution-map.json"])["models"]:
                identities[entry["model_id"]] = {
                    "kind": "captured_scientific_selection",
                    "execution_identity_sha256": entry["execution_identity_sha256"],
                    "stage_images": sorted({stage["image"] for stage in entry["stages"]}),
                    "qualification_inherited_by_overlay": False,
                }
    return identities


def build_overlay(historical, inventory, notes, evidence, *, as_of, configuration=None):
    previous = {row["model_id"]: row for row in historical["apps"]}
    if "body" in inventory:
        if inventory.get("status") != 200:
            raise ValueError("Failed inventory capture is not coverage authority")
        inventory = inventory["body"]
    captured = inventory.get("data", inventory)
    instances = captured["items"]
    if captured.get("next_cursor"):
        raise ValueError("An incomplete paginated App inventory cannot establish coverage")
    model_ids = set(previous) | {row["model_ref"] for row in instances}
    if set(notes["models"]) != model_ids:
        raise ValueError("Coverage notes must account for every historical and captured model")
    app_ids = [row["app_id"] for row in instances]
    if len(app_ids) != len(set(app_ids)):
        raise ValueError("Captured App identities must be unique")
    result = []
    identities = configured_identities(configuration or {})
    for model_id in sorted(model_ids):
        note = notes["models"][model_id]
        if set(note["dimensions"]) != set(DIMENSIONS):
            raise ValueError(f"Missing evidence dimension for {model_id}")
        for dimension in note["dimensions"].values():
            if dimension["state"] in {"ready", "customer_ready", "qualified"}:
                raise ValueError("An overlay cannot make an unscoped readiness claim")
            if not dimension["summary"] or not dimension["evidence"]:
                raise ValueError("Every statement needs an explicit summary and source")
            if set(dimension["evidence"]) - set(evidence):
                raise ValueError("Coverage statement references absent evidence")
        result.append({
            "model_id": model_id,
            "historical_modes": previous.get(model_id, {}).get("modes", []),
            "historical_gaps_preserved": previous.get(model_id, {}).get("gaps", []),
            "captured_app_instances": [
                {key: row.get(key) for key in (
                    "app_id", "public_model_id", "display_name", "enabled", "status",
                )}
                for row in instances if row["model_ref"] == model_id
            ],
            "captured_runtime_configuration": identities.get(model_id, {
                "kind": "not_projected_from_selected_maps",
                "note": "Consult exact runtime evidence; absence here is not a disabled-route or unknown-image verdict.",
            }),
            **note,
        })
    return {
        "schema": "fs2.qualification-coverage-overlay/v1",
        "as_of": as_of,
        "verdict": "not_a_readiness_decision",
        "scope": "Retained-evidence coverage, not request aggregation or a new qualification run",
        "historical_as_of": historical["current_evidence_as_of"],
        "captured_inventory_generated_at": inventory.get("meta", {}).get("generated_at"),
        "inventory_model_rows": len(result),
        "inventory_app_instances": len(instances),
        "shared_limitations": notes["shared_limitations"],
        "historical_corrections": notes["historical_corrections"],
        "evidence": evidence,
        "models": result,
    }


def freeze_evidence(references, roots, snapshot_dir):
    frozen = {}
    for name, reference in references.items():
        relative = Path(reference["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Evidence paths must be relative to their declared root")
        source = roots[reference["root"]] / relative
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        destination = snapshot_dir / digest
        if destination.exists():
            if destination.read_bytes() != payload:
                raise ValueError("Frozen evidence content conflict")
        else:
            with destination.open("xb") as stream:
                stream.write(payload)
            destination.chmod(0o600)
        frozen[name] = {**reference, "sha256": digest, "size_bytes": len(payload),
                        "frozen_copy": str(destination)}
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--workbench", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    args = parser.parse_args()
    roots = {key: getattr(args, key) for key in ("campaign", "backend", "workbench")}
    notes = json.loads(args.notes.read_text())
    args.snapshot_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    evidence = freeze_evidence(notes["references"], roots, args.snapshot_dir)
    def read_frozen(name):
        return json.loads(Path(evidence[name]["frozen_copy"]).read_bytes())
    result = build_overlay(read_frozen("historical"), read_frozen("inventory"), notes,
                           evidence, as_of=datetime.now(timezone.utc).isoformat(),
                           configuration=read_frozen("runtime179"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
