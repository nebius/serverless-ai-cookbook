import copy
import hashlib
import json
from pathlib import Path

import pytest

from coverage_overlay import DIMENSIONS, build_overlay, configured_identities, freeze_evidence


def fixture():
    history = {"current_evidence_as_of": "2026-09-18T23:50:00Z", "apps": [
        {"model_id": "example", "modes": ["predict"], "gaps": ["Original failure retained"]}
    ]}
    inventory = {"items": [
        {"app_id": "canonical", "model_ref": "example", "public_model_id": "example", "enabled": True},
        {"app_id": "clone", "model_ref": "example", "public_model_id": "app-clone", "enabled": False},
        {"app_id": "excluded", "model_ref": "excluded", "enabled": False},
    ]}
    notes = {"shared_limitations": ["Not a readiness decision"], "historical_corrections": [], "models": {}}
    for model in ("example", "excluded"):
        notes["models"][model] = {"dimensions": {
            key: {"state": "not_established", "summary": "Bounded explicit claim", "evidence": ["source"]}
            for key in DIMENSIONS
        }, "remaining_gaps": ["Untested modes"]}
    return history, inventory, notes


def test_inventory_includes_disabled_models_and_distinct_clones_without_readiness():
    historical, inventory, notes = fixture()
    original = copy.deepcopy(historical)
    result = build_overlay(historical, inventory, notes, {"source": {}}, as_of="2026-09-19T04:30:00Z")
    assert historical == original
    assert result["inventory_model_rows"] == 2
    assert result["inventory_app_instances"] == 3
    assert result["verdict"] == "not_a_readiness_decision"
    assert result["models"][0]["historical_gaps_preserved"] == ["Original failure retained"]
    assert len(result["models"][0]["captured_app_instances"]) == 2
    assert all(set(row["dimensions"]) == set(DIMENSIONS) for row in result["models"])


@pytest.mark.parametrize("mutation", ["missing_model", "duplicate_app", "pagination", "missing_dimension",
                                     "readiness", "missing_reference"])
def test_incomplete_or_unscoped_claims_fail(mutation):
    history, inventory, notes = fixture()
    if mutation == "missing_model":
        del notes["models"]["excluded"]
    elif mutation == "duplicate_app":
        inventory["items"][1]["app_id"] = "canonical"
    elif mutation == "pagination":
        inventory["next_cursor"] = "more"
    elif mutation == "missing_dimension":
        del notes["models"]["example"]["dimensions"]["snapshot"]
    elif mutation == "readiness":
        notes["models"]["example"]["dimensions"]["service_api"]["state"] = "ready"
    else:
        notes["models"]["example"]["dimensions"]["snapshot"]["evidence"] = ["absent"]
    with pytest.raises(ValueError):
        build_overlay(history, inventory, notes, {"source": {}}, as_of="2026-09-19T04:30:00Z")


def test_source_bytes_are_frozen_without_rewriting_original(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    source = root / "evidence.json"
    original = b'{ "old_failure": true, "new_reassessment": false }\n'
    source.write_bytes(original)
    archive = tmp_path / "frozen"
    archive.mkdir()
    result = freeze_evidence({"sample": {"root": "campaign", "path": "evidence.json"}},
                             {"campaign": root}, archive)
    assert source.read_bytes() == original
    assert result["sample"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert Path(result["sample"]["frozen_copy"]).read_bytes() == original
    assert result == freeze_evidence({"sample": {"root": "campaign", "path": "evidence.json"}},
                                    {"campaign": root}, archive)


def test_captured_admin_http_envelope_requires_success():
    history, inventory, notes = fixture()
    wrapped = {"status": 200, "body": {"meta": {"generated_at": "2026-09-19T03:59:19Z"}, "data": inventory}}
    result = build_overlay(history, wrapped, notes, {"source": {}}, as_of="2026-09-19T04:30:00Z")
    assert result["captured_inventory_generated_at"] == "2026-09-19T03:59:19Z"
    wrapped["status"] = 503
    with pytest.raises(ValueError, match="Failed inventory"):
        build_overlay(history, wrapped, notes, {"source": {}}, as_of="2026-09-19T04:30:00Z")


def test_declared_notes_keep_dimensions_and_evidence_for_every_model():
    notes = json.loads((Path(__file__).parent / "cases/coverage-overlay-notes-20260919.json").read_text())
    assert len(notes["models"]) == 33
    assert "glm-5-2-fp8" in notes["models"]
    for row in notes["models"].values():
        assert set(row["dimensions"]) == set(DIMENSIONS)
        for dimension in row["dimensions"].values():
            assert dimension["evidence"]
            assert set(dimension["evidence"]) <= set(notes["references"])


def test_selected_configuration_is_not_execution_or_snapshot_attestation():
    maps = {"items": [{"data": {"deployment-runtimes.json": json.dumps({"models": {
        "example": {"record": {"runtime": {"image": {"digest": "sha256:" + "a" * 64}},
                               "model": {"source": {"revision": "retained-revision"}}}}
    }})}}]}
    identity = configured_identities(maps)["example"]
    assert identity["kind"] == "captured_serving_selection"
    assert identity["qualification_inherited_by_overlay"] is False
    assert "operation_id" not in identity and "snapshot_qualified" not in identity
