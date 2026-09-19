import io
from pathlib import Path
import re
import tarfile
import tempfile
import unittest

import numpy as np

from design_protocol_cases import bundle, framework_pattern, trim_terminal_unresolved
from design_protocol_metrics import aligned_rmsd, distinct_pattern_assignment, measure_structure
from evaluators import evaluate


def pdb(length, translation=0, mutate=None):
    # Unit-only coordinate fixture, not a biological qualification input.
    lines = []
    for index in range(1, length + 1):
        name = "GLY" if index == mutate else "ALA"
        x = index * 3.7 + translation
        y, z = np.sin(index) * 0.4, np.cos(index) * 0.4
        lines.append(f"ATOM  {index:5d}  CA  {name} A{index:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C  ")
    return "\n".join(lines + ["TER", "END", ""])


class DesignProtocolTests(unittest.TestCase):
    def test_target_trims_only_unresolved_termini_not_internal_positions(self):
        self.assertEqual(trim_terminal_unresolved("ACDEFGH", [2, 3, 6]), "CDEFG")
        self.assertEqual(trim_terminal_unresolved("ACDEFGH", [1, 7]), "ACDEFGH")
        for positions in ([], [0, 7], [1, 8], [None]):
            with self.assertRaises(ValueError):
                trim_terminal_unresolved("ACDEFGH", positions)

    def test_framework_exclusion_insertion_and_fixed_residues(self):
        config = {"include": [{"chain": {"id": "A", "res_index": "1..6"}}],
                  "design": [{"chain": {"id": "A", "res_index": "2..4"}}],
                  "exclude": [{"chain": {"id": "A", "res_index": "2..3"}}],
                  "design_insertions": [{"insertion": {"id": "A", "res_index": 2, "num_residues": "1..2"}}]}
        pattern = framework_pattern("ACDEFGH", config, "A")
        self.assertIsNotNone(re.fullmatch(pattern, "AYYFG"))
        self.assertIsNotNone(re.fullmatch(pattern, "AWYYFG"))
        self.assertIsNone(re.fullmatch(pattern, "AWYYYFG"))
        self.assertIsNone(re.fullmatch(pattern, "CWYYFG"))

    def test_antibody_requires_distinct_framework_chains(self):
        self.assertIsNone(distinct_pattern_assignment({"A": {"sequence": "ACD"}}, ["ACD", "ACD"]))
        self.assertEqual(distinct_pattern_assignment({"A": {"sequence": "ACD"}, "B": {"sequence": "ACD"}}, ["ACD", "ACD"]), ["A", "B"])

    def test_aligned_not_raw_coordinate_difference(self):
        xyz = np.array([[0, 0, 0], [1, 0, 0], [0, 2, 0], [0, 0, 3]], dtype=float)
        rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        self.assertLess(aligned_rmsd(xyz, xyz @ rotation + 20), 1e-10)
        mirrored = xyz.copy()
        mirrored[:, 0] *= -1
        self.assertGreater(aligned_rmsd(xyz, mirrored), 0.1)

    def test_motif_mapping_and_sequence_are_independent_constraints(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "reference.pdb").write_text(pdb(32))
            expected = {"protocol": "scaffold-motif", "reference_path": "reference.pdb", "reference_chain": "A",
                        "reference_residue_ids": list(range(11, 23)), "output_motif_positions_1based": list(range(11, 23)),
                        "total_residues": 32, "motif_ca_rmsd_limit": 1.5, "minimum_structures": 1}
            result = measure_structure(pdb(32, translation=50), expected, root)
            self.assertTrue(result["constraints_pass"])
            self.assertLess(result["motif_ca_rmsd_angstrom"], 0.001)
            self.assertFalse(measure_structure(pdb(32, mutate=13), expected, root)["constraints_pass"])
            self.assertFalse(measure_structure(pdb(31), expected, root)["constraints_pass"])
            case = {"model_id": "rfdiffusion", "case_id": "unit", "expected": {"evaluator": "design_protocol", **expected}}
            self.assertTrue(evaluate(case, {"outputs": [{"structure": pdb(32)}]}, root)["service_semantic_pass"])

    def test_deterministic_bundle_contains_relative_spec_dependencies(self):
        raw = bundle({"protocol.yaml": b"entities: []\n", "target.pdb": b"END\n"})
        self.assertEqual(raw, bundle({"target.pdb": b"END\n", "protocol.yaml": b"entities: []\n"}))
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            self.assertEqual(archive.getnames(), ["design-specs/protocol.yaml", "target.pdb"])


if __name__ == "__main__":
    unittest.main()
