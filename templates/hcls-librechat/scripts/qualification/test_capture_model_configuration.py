import copy
import unittest
from unittest.mock import patch

from capture_model_configuration import capture, compare


class ModelConfigurationTests(unittest.TestCase):
    def fixture(self):
        owner = {"metadata": {"namespace": "models", "name": "app", "uid": "owner", "generation": 2},
                 "spec": {"cache": {"snapshotPreference": "Require"}},
                 "status": {"fastStart": {"qualifiedLevel": "Off"}}}
        deployment = {"metadata": {"namespace": "models", "name": "app-pool",
                                   "ownerReferences": [{"uid": "owner", "controller": True}]},
                      "spec": {"replicas": 1, "template": {"spec": {"containers": [{"image": "fixed"}]}}}}
        return owner, deployment

    def read(self, owner, deployments):
        with patch("capture_model_configuration.kube", side_effect=[{"items": [owner]}, {"items": deployments}]):
            return capture()

    def test_replicas_and_unrelated_workloads_do_not_change_render_identity(self):
        owner, deployment = self.fixture()
        original = self.read(owner, [deployment])
        deployment["spec"]["replicas"] = 0
        unrelated = copy.deepcopy(deployment)
        unrelated["metadata"]["namespace"] = "foreign"
        result = self.read(owner, [deployment, unrelated])
        self.assertEqual(len(result["rendered_pod_templates"]), 1)
        self.assertTrue(all(compare(original, result).values()))

    def test_actual_spec_template_and_level_changes_remain_visible(self):
        owner, deployment = self.fixture()
        original = self.read(owner, [deployment])
        owner["spec"]["cache"]["snapshotPreference"] = "Never"
        owner["status"]["fastStart"]["qualifiedLevel"] = "L1"
        deployment["spec"]["template"]["spec"]["containers"][0]["image"] = "changed"
        result = compare(original, self.read(owner, [deployment]))
        self.assertTrue(result["owner_set_unchanged"])
        self.assertFalse(result["owner_specs_unchanged"])
        self.assertFalse(result["rendered_pod_templates_unchanged"])
        self.assertFalse(result["qualified_levels_unchanged"])
