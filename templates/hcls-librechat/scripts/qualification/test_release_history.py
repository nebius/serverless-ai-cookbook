import hashlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from release_history import replace_scientific_execution_map, require_settled_release, resource_changes, verify_published_image
import json


def test_only_reviewed_execution_map_can_replace_immutable_resource():
    def configmap(value):
        return {"immutable": True, "metadata": {"labels": {
            "app.kubernetes.io/component": "scientific-execution-map"}},
            "data": {"map.json": json.dumps(value)}}
    old = {("ConfigMap", "map-old"): configmap({"models": []})}
    replacement = {"models": [{"id": "new"}]}
    new = {("ConfigMap", "map-new"): configmap(replacement)}
    changes = resource_changes(old, new, replacement)
    assert changes == {"ConfigMap/map-old": ["<removed>"], "ConfigMap/map-new": ["<added>"]}
    with pytest.raises(ValueError):
        resource_changes(old, new)
    with pytest.raises(ValueError, match="differs"):
        resource_changes(old, new, {"models": []})
    with pytest.raises(ValueError):
        resource_changes(old, {**new, ("Service", "unexpected"): {}}, replacement)
    new[("ConfigMap", "map-new")]["immutable"] = False
    with pytest.raises(ValueError, match="not the immutable"):
        resource_changes(old, new, replacement)


def test_execution_map_replacement_does_not_retain_obsolete_baselines_or_revert_serving_maps():
    old = {"scientificBatch": {"workers": 16, "executionMap": {"models": [{"id": "old"}],
            "qualification_baselines": {"old": "old"}}},
           "catalog": {"leanRoutes": {"configMapName": "current-cxr-and-cosmos"}}}
    replacement = {"models": [{"id": "new"}], "qualification_baselines": {"retained-siblings": "new"}}
    result = replace_scientific_execution_map(old, replacement)
    assert result["scientificBatch"]["executionMap"] == replacement
    assert "old" not in result["scientificBatch"]["executionMap"]["qualification_baselines"]
    assert result["scientificBatch"]["workers"] == 16
    assert result["catalog"] == old["catalog"]
    assert "old" in old["scientificBatch"]["executionMap"]["qualification_baselines"]


@pytest.mark.parametrize("state", ["pending-upgrade", "pending-rollback", "pending-install"])
def test_recovery_never_overlaps_an_active_transaction(state):
    with pytest.raises(ValueError, match="active Helm transaction"):
        require_settled_release({"version": 165, "info": {"status": state}}, 165)


def test_failed_revision_recovery_is_exact_and_explicit():
    failed = {"version": 165, "info": {"status": "failed"}}
    for revision in (None, 164, 166):
        with pytest.raises(ValueError):
            require_settled_release(failed, revision)
    require_settled_release(failed, 165)
    require_settled_release({"version": 163, "info": {"status": "deployed"}})


def test_checks_exact_repository_and_manifest_bytes():
    manifest = b'{"schemaVersion":2}'
    image = {"repository": "registry.example/platform/control-plane",
             "digest": "sha256:" + hashlib.sha256(manifest).hexdigest()}
    with patch("release_history.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=manifest)) as run:
        result = verify_published_image(image)
    assert run.call_args.args[0][-1] == "docker://" + image["repository"] + "@" + image["digest"]
    assert result["readable"] is True


def test_missing_repository_fails_without_disclosing_registry_stderr():
    with patch("release_history.subprocess.run", return_value=SimpleNamespace(returncode=1, stderr=b"private")):
        with pytest.raises(ValueError, match="not readable") as error:
            verify_published_image({"repository": "registry.example/missing", "digest": "sha256:" + "a" * 64})
    assert "private" not in str(error.value)


def test_wrong_manifest_bytes_rejected():
    with patch("release_history.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"other")):
        with pytest.raises(ValueError, match="do not match"):
            verify_published_image({"repository": "registry.example/right", "digest": "sha256:" + "a" * 64})
