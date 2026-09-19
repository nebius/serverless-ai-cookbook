import json
from pathlib import Path
import tempfile
import unittest

from summarize_design_recovery import sha, summarize


class RecoverySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "cases.json"
        self.cohort = self.root / "cohort"
        (self.root / "reference.pdb").write_text("fixed public reference")
        self.reference_sha = sha((self.root / "reference.pdb").read_bytes())
        self.cases = [{"case_id": name, "expected": {"evaluator": "backbone_recovery", "reference_path": "reference.pdb"},
                       "provenance": {"upstream_model_id": "proteinmpnn", "upstream_case_id": "shared-input",
                                      "reference_sha256": self.reference_sha}} for name in ("one", "two")]
        self.manifest.write_text(json.dumps({"cases": self.cases}))

    def receipt(self, name, state="verified", rmsd=1.0, scientist="scientist-01"):
        folder = self.cohort / scientist / name
        folder.mkdir(parents=True)
        (folder / "receipt.json").write_text(json.dumps({"case_id": name, "state": state, "operation_id": name}))
        (folder / "result.json").write_text('{"result":"retained"}')
        (folder / "evaluation.json").write_text(json.dumps({"evaluator": "backbone_recovery",
            "reference_sha256": self.reference_sha, "service_semantic_pass": state == "verified",
            "predictions": [{"ca_rmsd_angstrom": rmsd, "ca_lddt_15A": 0.5}]}))

    def test_missing_case_stays_in_denominator_and_backbones_not_independent(self):
        self.receipt("one")
        result = summarize(self.manifest, self.cohort)
        self.assertEqual(result["selected_frozen_cases"], 2)
        group = result["groups"][0]
        self.assertEqual(group["case_states"], {"verified": 1, "not_observed": 1})
        self.assertEqual(group["source_requests"], 1)
        self.assertEqual(group["unique_backbone_references"], 1)
        self.assertEqual(group["measured_predictions"], 1)
        self.assertIn("result_sha256", result["rows"][0])

    def test_failed_case_and_bad_geometry_are_not_filtered_out(self):
        self.receipt("one", rmsd=0.5)
        self.receipt("two", state="semantic_failed", rmsd=100)
        result = summarize(self.manifest, self.cohort)
        self.assertEqual(result["groups"][0]["metrics"]["ca_rmsd_angstrom"]["max"], 100)
        self.assertFalse(result["rows"][1]["independent_semantic_pass"])

    def test_duplicate_receipt_is_not_silently_selected(self):
        self.receipt("one")
        self.receipt("one", scientist="scientist-02")
        with self.assertRaisesRegex(ValueError, "Duplicate case receipt"):
            summarize(self.manifest, self.cohort)

    def test_reference_mismatch_not_a_success(self):
        self.receipt("one")
        (self.root / "reference.pdb").write_text("different source")
        with self.assertRaisesRegex(ValueError, "Reference bytes"):
            summarize(self.manifest, self.cohort)

    def test_nonfinite_metric_not_counted_as_success(self):
        self.receipt("one", rmsd=float("nan"))
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            summarize(self.manifest, self.cohort)
