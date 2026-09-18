"""Keep scoped evidence distinct from fixtures and whole-platform readiness."""

import json
from pathlib import Path
import re
import unittest


MATRIX = Path(__file__).parent / "cases" / "coverage-v1.json"


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX.read_text())
        cls.apps = {app["model_id"]: app for app in cls.matrix["apps"]}

    def test_all_apps_remain_and_fixture_is_not_readiness(self):
        self.assertEqual(len(self.matrix["apps"]), 32)
        self.assertEqual(len(self.apps), 32)
        self.assertEqual(self.matrix["verdict"], "not_qualified")
        self.assertIn("not release readiness", self.matrix["reading_guide"])

    def test_current_claims_have_traceable_bounded_references(self):
        for app in self.apps.values():
            evidence = app.get("current_evidence")
            if evidence is None:
                continue
            with self.subTest(model=app["model_id"]):
                self.assertTrue(evidence["state"])
                self.assertTrue(evidence["summary"])
                self.assertTrue(app["gaps"])
                self.assertTrue(evidence["references"])
                for reference in evidence["references"]:
                    self.assertIn(reference["root"], self.matrix["evidence_roots"])
                    self.assertFalse(Path(reference["path"]).is_absolute())
                    self.assertNotIn("..", Path(reference["path"]).parts)
                    if "sha256" in reference:
                        self.assertRegex(reference["sha256"], re.compile(r"^[a-f0-9]{64}$"))
                counts = evidence.get("counts")
                if counts:
                    self.assertEqual(counts["requested"], counts["verified"] + counts["failed"])

    def test_molmim_failures_are_not_relabelled_success(self):
        app = self.apps["molmim"]
        self.assertIn("random latent", " ".join(app["historical"]["gaps"]))
        self.assertNotIn("random latent", " ".join(app["gaps"]))
        self.assertEqual(app["current_evidence"]["counts"], {
            "requested": 48, "verified": 20, "failed": 28,
        })

    def test_prepared_variants_are_not_publicly_qualified(self):
        app = self.apps["proteina-complexa"]
        self.assertEqual(app["fixture_status"], "prepared")
        self.assertEqual(app["current_evidence"]["public_variant_counts"]["verified"], 0)
        self.assertEqual(app["current_evidence"]["isolated_candidate_counts"]["execution_completed"], 5)
        self.assertIn("scientific", " ".join(app["gaps"]) + app["current_evidence"]["summary"])

    def test_unrun_protocols_and_snapshot_boundary_stay_open(self):
        self.assertIn("Five additional", " ".join(self.apps["boltzgen"]["gaps"]))
        self.assertIn("Scaffold-motif", " ".join(self.apps["rfdiffusion"]["gaps"]))
        self.assertIn("snapshot", " ".join(self.apps["cosmos3-nano"]["gaps"]))
        self.assertIn("pending", " ".join(self.apps["cosmos3-lerobot-augmentation"]["gaps"]))


if __name__ == "__main__":
    unittest.main()
