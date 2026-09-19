import copy
import unittest

from rdkit import Chem

from verify_diffdock_candidate import compare


def result(offset=0.0, confidence=0.5, smiles="CC"):
    molecule = Chem.MolFromSmiles(smiles)
    conformer = Chem.Conformer(molecule.GetNumAtoms())
    for index in range(molecule.GetNumAtoms()):
        conformer.SetAtomPosition(index, (index * 1.5 + offset, 0.0, 0.0))
    molecule.AddConformer(conformer)
    return {"poses": [{"sdf": Chem.MolToMolBlock(molecule), "confidence": confidence}]}


class DiffDockCandidateTest(unittest.TestCase):
    def test_exact_pair_passes(self):
        value = result()
        self.assertTrue(compare(value, copy.deepcopy(value), 0.01, 0.001)["numerical_repeatability_pass"])

    def test_coordinates_are_compared_without_alignment(self):
        measured = compare(result(), result(offset=2), 0.01, 0.001)
        self.assertFalse(measured["numerical_repeatability_pass"])
        self.assertEqual(measured["maximum_coordinate_difference_angstrom"], 2)

    def test_confidence_drift_fails_even_with_same_coordinates(self):
        self.assertFalse(compare(result(), result(confidence=0.51), 0.01, 0.001)["numerical_repeatability_pass"])

    def test_pose_count_mismatch_is_not_partial_success(self):
        with self.assertRaisesRegex(ValueError, "count"):
            compare(result(), {"poses": []}, 0.01, 0.001)

    def test_wrong_ligand_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "topology"):
            compare(result(), result(smiles="CO"), 0.01, 0.001)


if __name__ == "__main__":
    unittest.main()
