"""A frozen motif case must use the UUID returned by its actual upload."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from batch_transport import prepare_arguments


class ManifestBindingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        data = b"retained-pdb-bytes"
        (self.root / "target.pdb").write_bytes(data)
        self.case = {
            "case_id": "motif", "model_id": "rfdiffusion",
            "arguments": {"parameters": {"operation": "scaffold-motif"}},
            "preparation": {
                "artifact_id_parameters": {"input_pdb_artifact_id": "target_structure"},
                "inputs": [{"name": "target_structure", "local_path": "target.pdb",
                            "media_type": "chemical/x-pdb", "semantic_type": "protein-structure/v1",
                            "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}],
            },
        }
        self.reference = {"artifact_id": "ea22963e-2a17-484d-a51c-cf9a2fc474ed"}

    def test_actual_uploaded_uuid_is_bound_without_mutating_frozen_case(self):
        original = copy.deepcopy(self.case)
        with patch("batch_transport.upload", side_effect=[self.reference, {"artifact_id": "manifest"}]) as uploaded:
            actual = prepare_arguments(None, self.case, self.root, self.root, "key", {})
        self.assertEqual(actual["parameters"]["input_pdb_artifact_id"], self.reference["artifact_id"])
        self.assertEqual(self.case, original)
        self.assertEqual(uploaded.call_count, 2)

    def test_replay_uses_retained_actual_reference_without_new_upload(self):
        receipt = {"input_artifacts": {"target_structure": self.reference},
                   "input_manifest": {"artifact_id": "manifest"}}
        with patch("batch_transport.upload") as uploaded:
            actual = prepare_arguments(None, self.case, self.root, self.root, "key", receipt)
        uploaded.assert_not_called()
        self.assertEqual(actual["parameters"]["input_pdb_artifact_id"], self.reference["artifact_id"])

    def test_unresolved_binding_rejected_before_upload_or_admission(self):
        for invalid in ({"input_pdb_artifact_id": "missing"}, {"nested.path": "target_structure"}, []):
            with self.subTest(invalid=invalid), patch("batch_transport.upload") as uploaded:
                self.case["preparation"]["artifact_id_parameters"] = invalid
                with self.assertRaises(ValueError):
                    prepare_arguments(None, self.case, self.root, self.root, "key", {})
                uploaded.assert_not_called()

    def test_missing_or_friendly_artifact_id_is_not_admitted(self):
        for invalid in ({}, {"artifact_id": "target_structure"}, {"artifact_id": None}):
            with self.subTest(invalid=invalid), patch("batch_transport.upload", return_value=invalid) as uploaded:
                with self.assertRaisesRegex(ValueError, "valid artifact UUID"):
                    prepare_arguments(None, self.case, self.root, self.root, "key", {})
                self.assertEqual(uploaded.call_count, 1)

    def test_unbound_existing_case_keeps_parameters(self):
        del self.case["preparation"]["artifact_id_parameters"]
        with patch("batch_transport.upload", side_effect=[self.reference, {"artifact_id": "manifest"}]):
            actual = prepare_arguments(None, self.case, self.root, self.root, "key", {})
        self.assertEqual(actual["parameters"], self.case["arguments"]["parameters"])


if __name__ == "__main__":
    unittest.main()
