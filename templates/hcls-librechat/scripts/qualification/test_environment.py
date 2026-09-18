import unittest
from unittest.mock import patch

from run_campaign import evaluator_environment


class EvaluatorEnvironmentTests(unittest.TestCase):
    def test_missing_evaluator_fails_before_worker_or_admission(self):
        with patch("run_campaign.importlib.import_module", side_effect=ModuleNotFoundError("numpy")):
            with self.assertRaisesRegex(RuntimeError, "before submitting model work"):
                evaluator_environment()

    def test_environment_records_each_required_distribution(self):
        with patch("run_campaign.importlib.import_module"), patch("run_campaign.version", return_value="pinned"):
            result = evaluator_environment()
        self.assertEqual(set(result), {"numpy", "biopython", "gemmi", "rdkit", "h5py", "nibabel", "Pillow"})
