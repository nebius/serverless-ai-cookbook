"""Scientific invariants: tests catch wrong superposition, mapping and RMSD."""

from pathlib import Path
import base64
import hashlib
from io import BytesIO
import json
import tempfile
import unittest

import numpy as np

from evaluators import (backbone_recovery_metrics, ca_lddt, complex_metrics, design_input_sequence, design_metrics, docking_metrics, evaluate, extract_structures,
                        fit_coordinates, molecular_metrics, parse_chain, phenoage_reference, protein_chain_ids,
                        segmentation_metrics, sequence_pairs, structure_metrics)


def pdb(coordinates, residues=("ALA", "GLY", "SER", "VAL")):
    return "\n".join(
        f"ATOM  {i:5d}  CA  {residue:3s} A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 50.00           C"
        for i, (residue, (x, y, z)) in enumerate(zip(residues, coordinates), 1)
    ) + "\nTER\nEND\n"


class StructureMetricsTest(unittest.TestCase):
    def setUp(self):
        self.reference = np.array([[0, 0, 0], [3.8, 0, 0], [4.4, 3.7, 0], [4.0, 3.8, 3.7]])

    def test_rigid_body_transform_is_not_structure_error(self):
        rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        prediction = self.reference @ rotation + [10, -4, 2]
        measured = structure_metrics(pdb(self.reference), pdb(prediction), input_sequence="AGSV")
        self.assertLess(measured["ca_rmsd_angstrom"], 1e-6)
        self.assertAlmostEqual(measured["ca_lddt_15A"], 1)
        self.assertAlmostEqual(measured["tm_score_kabsch"], 1)
        self.assertTrue(measured["prediction_sequence_exact"])

    def test_mirror_is_not_permitted_as_rigid_fit(self):
        prediction = self.reference * [-1, 1, 1]
        fitted = fit_coordinates(self.reference, prediction)
        self.assertGreater(np.sqrt(np.mean((fitted - self.reference) ** 2)), 0.5)

    def test_missing_residue_mapping_preserves_reference_positions(self):
        self.assertEqual(sequence_pairs("ACDEFG", "ACEFG"), [(0, 0), (1, 1), (3, 2), (4, 3), (5, 4)])

    def test_no_local_pairs_reports_unknown_not_zero(self):
        values = np.array([[0, 0, 0], [100, 100, 100]])
        self.assertIsNone(ca_lddt(values, values))

    def test_wrong_sequence_is_not_semantically_successful(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "reference.pdb").write_text(pdb(self.reference))
            case = {"case_id": "mismatch", "expected": {"evaluator": "protein_structure",
                    "reference_path": "reference.pdb", "input_sequence": "AGSV"}}
            result = {"structures": [{"structure": pdb(self.reference, ("ALA", "GLY", "SER", "LEU"))}]}
            receipt = evaluate(case, result, base)
            self.assertFalse(receipt["service_semantic_pass"])
            self.assertEqual(receipt["predictions"][0]["sequence_identity"], 0.75)

    def test_inverse_design_recovery_keeps_redesigned_positions(self):
        predicted = pdb(self.reference + [12, 4, 8], ("THR", "TYR", "LEU", "LYS"))
        measured = backbone_recovery_metrics(pdb(self.reference), predicted, designed_sequence="TYLK")
        self.assertTrue(measured["prediction_sequence_exact"])
        self.assertEqual(measured["designed_sequence_identity_to_original"], 0)
        self.assertEqual(measured["positional_coverage"], 1)
        self.assertLess(measured["ca_rmsd_angstrom"], 1e-6)
        with self.assertRaisesRegex(ValueError, "equal-length"):
            backbone_recovery_metrics(pdb(self.reference), predicted, designed_sequence="TYL")

    def proteina_result(self):
        from evaluators import fit_coordinates
        raw = pdb(self.reference * 0.5)
        refold = pdb(self.reference)
        for name in ("raw", "refold"):
            value = raw if name == "raw" else refold
            value = "\n".join(line[:21] + "B" + line[22:] if line.startswith("ATOM") else line for line in value.splitlines()) + "\n"
            if name == "raw":
                raw = value
            else:
                refold = value
        raw_xyz, folded_xyz = parse_chain(raw, "B")["coordinates"], parse_chain(refold, "B")["coordinates"]
        rmsd = float(np.sqrt(np.mean(np.sum((raw_xyz - fit_coordinates(raw_xyz, folded_xyz)) ** 2, axis=1))))
        row = {"id_gen": "0", "self_sequence": "AGSV", "self_binder_scRMSD_ca": str(rmsd),
               "generated_structure_artifact": "structure.1", "self_refolded_structure_artifact": "self-refolded.1"}
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        design = {"id_gen": "0", "results_artifact": "results.1", "metric_prefix": "self_",
                  "sequence_sha256": digest("AGSV"), "refolding_model": "AlphaFold2", "relaxation": "not-claimed",
                  "results_row_sha256": digest(json.dumps(row, sort_keys=True, separators=(",", ":"))),
                  "generated": {"artifact_name": "structure.1", "sha256": digest(raw), "binder_chain": "B"},
                  "self_refolded": {"artifact_name": "self-refolded.1", "sha256": digest(refold), "binder_chain": "B"}}
        return {"outputs": [
            {"artifact_name": "structure.1", "structure": raw},
            {"artifact_name": "self-refolded.1", "structure": refold},
            {"artifact_name": "results.1", "csv_rows": [row]},
            {"artifact_name": "design-provenance", "schema_version": "fs2-serve.nebius.ai/proteina-complexa-design-provenance/v1",
             "designs": [design]}]}

    def test_proteina_refold_role_keeps_raw_geometry_without_double_counting_designs(self):
        case = {"case_id": "role-test", "model_id": "proteina-complexa", "expected": {"evaluator": "design_constraints"}}
        measured = evaluate(case, self.proteina_result())
        self.assertTrue(measured["service_semantic_pass"])
        self.assertEqual(measured["design_count"], 1)
        self.assertEqual(measured["coordinate_artifact_count"], 2)
        self.assertEqual(measured["generated_geometry_pass_count"], 0)
        self.assertEqual(measured["self_refolded_geometry_pass_count"], 1)
        self.assertLess(measured["predictions"][0]["rmsd_absolute_difference_angstrom"], 1e-8)

    def test_proteina_cannot_hide_wrong_published_metric_by_rehashing_row(self):
        case = {"case_id": "role-test", "model_id": "proteina-complexa", "expected": {"evaluator": "design_constraints"}}
        result = self.proteina_result()
        row = result["outputs"][2]["csv_rows"][0]
        row["self_binder_scRMSD_ca"] = "22.0"
        result["outputs"][3]["designs"][0]["results_row_sha256"] = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        measured = evaluate(case, result)
        self.assertFalse(measured["service_semantic_pass"])
        self.assertFalse(measured["predictions"][0]["csv_rmsd_agrees"])

    def test_proteina_missing_role_or_reordered_coordinates_cannot_pass(self):
        case = {"case_id": "role-test", "model_id": "proteina-complexa", "expected": {"evaluator": "design_constraints"}}
        result = self.proteina_result()
        result["outputs"][0]["structure"], result["outputs"][1]["structure"] = (
            result["outputs"][1]["structure"], result["outputs"][0]["structure"])
        measured = evaluate(case, result)
        self.assertFalse(measured["service_semantic_pass"])
        self.assertIn("hash mismatch", measured["error"])

    def test_artifact_reference_alone_is_not_structure(self):
        receipt = evaluate({"case_id": "no-bytes", "expected": {"evaluator": "protein_structure"}},
                           {"artifact": {"artifact_id": "some-id"}})
        self.assertFalse(receipt["service_semantic_pass"])
        self.assertIn("fetch the result artifact", receipt["error"])

    def test_native_envelopes_extract_identical_structure(self):
        text = pdb(self.reference)
        envelope = {"structuredContent": {"result": {"structures_in_ranked_order": [{"format": "pdb", "structure": text}]}}}
        self.assertEqual(extract_structures(envelope), [text])

    def test_openfold3_structures_with_scores_extract(self):
        text = pdb(self.reference)
        envelope = {"outputs": [{"structures_with_scores": [{"structure": text, "score": 0.8}]}]}
        self.assertEqual(extract_structures(envelope), [text])

    def test_cif_optional_occupancy_does_not_change_coordinates(self):
        import gemmi
        document = gemmi.read_pdb_string(pdb(self.reference)).make_mmcif_document()
        block = document.sole_block()
        block.find_loop("_atom_site.occupancy").get_loop().remove_column("_atom_site.occupancy")
        parsed = parse_chain(document.as_string())
        self.assertEqual(parsed["sequence"], "AGSV")
        np.testing.assert_allclose(parsed["coordinates"], self.reference)

    def test_alphafold3_cif_provenance_comments_are_preserved(self):
        import gemmi
        text = "# Output terms notice\n# https://example.org/terms\n\n" + gemmi.read_pdb_string(
            pdb(self.reference)).make_mmcif_document().as_string()
        self.assertEqual(extract_structures({"outputs": [{"structure": text}]}), [text])
        self.assertEqual(protein_chain_ids(text), ["A"])
        self.assertEqual(parse_chain(text)["sequence"], "AGSV")
        np.testing.assert_allclose(parse_chain(text)["coordinates"], self.reference)


class DockingMetricsTest(unittest.TestCase):
    def setUp(self):
        from rdkit import Chem
        from rdkit.Chem import AllChem
        self.Chem = Chem
        self.reference = Chem.AddHs(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O"))
        self.assertEqual(AllChem.EmbedMolecule(self.reference, randomSeed=7), 0)
        self.reference = Chem.RemoveHs(self.reference)

    def test_docking_does_not_align_away_translation(self):
        prediction = self.Chem.Mol(self.reference)
        conformer = prediction.GetConformer()
        for index in range(prediction.GetNumAtoms()):
            point = conformer.GetAtomPosition(index)
            conformer.SetAtomPosition(index, (point.x + 3, point.y, point.z))
        result = docking_metrics(self.Chem.MolToMolBlock(self.reference), self.Chem.MolToMolBlock(prediction))
        self.assertAlmostEqual(result["heavy_atom_rmsd_angstrom"], 3, places=3)
        self.assertFalse(result["within_2_angstrom"])

    def test_atom_order_does_not_create_false_docking_error(self):
        reordered = self.Chem.RenumberAtoms(self.reference, list(reversed(range(self.reference.GetNumAtoms()))))
        result = docking_metrics(self.Chem.MolToMolBlock(self.reference), self.Chem.MolToMolBlock(reordered))
        self.assertLess(result["heavy_atom_rmsd_angstrom"], 1e-6)

    def test_invalid_sdf_is_not_success(self):
        with self.assertRaisesRegex(ValueError, "unparsable"):
            docking_metrics("invalid", self.Chem.MolToMolBlock(self.reference))


class ComplexMetricsTest(unittest.TestCase):
    def setUp(self):
        self.first = np.array([[0, 0, 0], [3.8, 0, 0], [4.4, 3.7, 0], [4, 3.8, 3.7]])
        self.second = self.first + [0, 5, 0]
        self.expected = {"chains": [{"reference_chain": "A", "input_sequence": "AGSV"},
                                    {"reference_chain": "B", "input_sequence": "TYLK"}]}

    def structure(self, first, second):
        return pdb(first).replace("END\n", "") + pdb(second, ("THR", "TYR", "LEU", "LYS")).replace(" A", " B")

    def test_interface_invariant_to_shared_rigid_transform(self):
        measured = complex_metrics(self.structure(self.first, self.second),
            self.structure(self.first + [10, 2, 3], self.second + [10, 2, 3]), self.expected)
        self.assertLess(measured["complex_ca_rmsd_angstrom"], 1e-6)
        self.assertEqual(measured["native_ca_contact_recall"], 1)

    def test_partner_translation_is_not_aligned_away(self):
        measured = complex_metrics(self.structure(self.first, self.second),
            self.structure(self.first, self.second + [0, 20, 0]), self.expected)
        self.assertAlmostEqual(measured["partner_ca_rmsd_after_receptor_fit_angstrom"], 20)
        self.assertEqual(measured["native_ca_contact_recall"], 0)

    def test_design_contact_measurement_does_not_imply_binding(self):
        near = design_metrics(self.structure(self.first, self.second), {})
        far = design_metrics(self.structure(self.first, self.second + [0, 30, 0]), {})
        self.assertGreater(near["interfaces"][0]["ca_contact_pairs_below_8A"], 0)
        self.assertEqual(far["interfaces"][0]["ca_contact_pairs_below_8A"], 0)
        self.assertEqual(near["binding_efficacy"], "not_evaluated")
        self.assertEqual(design_metrics(pdb(self.first), {})["interface_coordinate_coverage"],
                         "single_chain_only_no_interface_coordinates")


class AdditionalEvaluatorTest(unittest.TestCase):
    def test_inverse_folding_keeps_residue_without_ca(self):
        partial = pdb(np.array([[0, 0, 0], [3.8, 0, 0], [4.4, 3.7, 0], [4, 3.8, 3.7]])).replace("  CA  ALA", "  C   ALA", 1)
        self.assertEqual(design_input_sequence(partial, ["A"]), "AGSV")
        self.assertEqual(parse_chain(partial)["sequence"], "GSV")

    def test_msa_rows_respect_requested_limit(self):
        case = {"case_id": "msa", "expected": {"evaluator": "msa_alignment", "input_sequence": "ACDE", "max_sequences": 1}}
        result = {"alignments": {"pdb70_220313": {"a3m": {"alignment": ">q\nACDE\n>hit\nAC-E\n"}}}}
        self.assertFalse(evaluate(case, result)["service_semantic_pass"])

    def test_msa_insertions_do_not_shift_query_columns(self):
        case = {"case_id": "msa", "expected": {"evaluator": "msa_alignment", "input_sequence": "ACDE", "max_sequences": 3}}
        result = {"alignments": {"pdb70_220313": {"a3m": {"alignment": ">q\nACDE\n>hit\nACxx-E\n"}}}}
        measured = evaluate(case, result)
        self.assertTrue(measured["service_semantic_pass"])
        self.assertTrue(measured["can_support_downstream_comparison"])

    def test_scalar_sample_identity_cannot_be_duplicated(self):
        case = {"case_id": "age", "expected": {"evaluator": "scalar_predictions", "prediction_field": "age",
                "reference_predictions": {"a": 50, "b": 60}, "absolute_tolerance": 0.01}}
        self.assertFalse(evaluate(case, {"predictions": [{"sample_id": "a", "age": 50}, {"sample_id": "a", "age": 60}]})["service_semantic_pass"])

    def test_scalar_missingness_counts_are_part_of_semantics(self):
        case = {"case_id": "age", "expected": {"evaluator": "scalar_predictions", "prediction_field": "age",
                "reference_predictions": {"a": 50}, "absolute_tolerance": 0.01, "imputed_counts": {"a": 4}}}
        self.assertFalse(evaluate(case, {"predictions": [{"sample_id": "a", "age": 50, "imputed_cpg_count": 0}]})["service_semantic_pass"])

    def test_proteinmpnn_underfilled_samples_fail(self):
        case = {"case_id": "mpnn", "expected": {"evaluator": "protein_sequence_design", "input_sequence": "AGSV", "num_sequences": 2}}
        self.assertFalse(evaluate(case, {"mfasta": ">sample1\nAGSV\n"})["service_semantic_pass"])

    def test_proteinmpnn_input_gaps_need_explicit_matching_output_metadata(self):
        case = {"case_id": "mpnn", "expected": {"evaluator": "protein_sequence_design", "input_sequence": "AGXV", "num_sequences": 1, "omit_AAs": ["X"]}}
        response = {"mfasta": ">sample1\nAAXV\n"}
        self.assertFalse(evaluate(case, response)["service_semantic_pass"])
        response["backbone_coverage"] = {"complete": False, "chains": [{"chain_id": "A", "unresolved_sequence_positions_1based": [3]}]}
        measured = evaluate(case, response)
        self.assertTrue(measured["service_semantic_pass"])
        self.assertEqual(measured["scientific_coverage"], "partial_incomplete_backbone")
        self.assertEqual(measured["scientifically_designable_residues"], 3)
        self.assertEqual(measured["unresolved_sequence_residues"], 1)
        self.assertEqual(measured["backbone_design_coverage"], 0.75)
        self.assertAlmostEqual(measured["sequences"][0]["sequence_recovery"], 2 / 3)
        response["mfasta"] = ">sample1\nAAAV\n"
        self.assertFalse(evaluate(case, response)["service_semantic_pass"])

    def test_proteinmpnn_multichain_gap_metadata_is_chain_relative(self):
        first = pdb(np.array([[0, 0, 0], [3.8, 0, 0], [4.4, 3.7, 0], [4, 3.8, 3.7]])).replace("END\n", "")
        atoms = [line for line in first.splitlines() if line.startswith("ATOM")][:3]
        second = "\n".join(line[:21] + "B" + f"{number:4d}" + line[26:]
                           for line, number in zip(atoms, (1, 2, 4))) + "\nTER\nEND\n"
        case = {"case_id": "multichain-gap", "arguments": {"input_pdb": first + second, "input_pdb_chains": ["A", "B"]},
                "expected": {"evaluator": "protein_sequence_design", "input_sequence": "AGSVAGXS", "num_sequences": 1}}
        response = {"mfasta": ">sample1\nAGSV/AGXS\n", "backbone_coverage": {"complete": False,
                    "chains": [{"chain_id": "B", "unresolved_sequence_positions_1based": [3]}]}}
        measured = evaluate(case, response)
        self.assertTrue(measured["service_semantic_pass"], measured)
        self.assertEqual(measured["unresolved_input_positions_1based"], [7])
        self.assertEqual(measured["sequences"][0]["chains"], [
            {"chain_id": "A", "sequence": "AGSV"}, {"chain_id": "B", "sequence": "AGXS"}])
        for invalid_chains in ("AGSVAGXS", "AGS/VAGXS", "AGSV/AGX/S"):
            response["mfasta"] = ">sample1\n" + invalid_chains + "\n"
            self.assertFalse(evaluate(case, response)["service_semantic_pass"])
        response["mfasta"] = ">sample1\nAGSV/AGXS\n"
        response["backbone_coverage"]["chains"][0]["chain_id"] = "A"
        self.assertFalse(evaluate(case, response)["service_semantic_pass"])

    def test_molecular_underfill_is_not_success(self):
        from rdkit import Chem
        from rdkit.Chem import QED
        molecule = Chem.MolFromSmiles("CCO")
        measured = molecular_metrics({"molecules": [{"smiles": "CCO", "score": QED.qed(molecule)}]}, {"num_molecules": 2, "scoring": "QED"})
        self.assertFalse(measured["service_semantic_pass"])

    def test_molecular_reported_score_is_independently_checked(self):
        measured = molecular_metrics({"molecules": [{"smiles": "CCO", "score": 1.0}]}, {"num_molecules": 1, "scoring": "QED"})
        self.assertFalse(measured["service_semantic_pass"])

    def test_phenoage_age_coefficient_and_units_have_expected_effect(self):
        sample = {"age_years": 50, "albumin_g_l": 45, "creatinine_umol_l": 80,
                  "glucose_mmol_l": 5, "c_reactive_protein_mg_dl": 0.1, "lymphocyte_percent": 30,
                  "mean_cell_volume_fl": 90, "red_cell_distribution_width_percent": 13,
                  "alkaline_phosphatase_u_l": 60, "white_blood_cell_count_10e3_per_ul": 6}
        baseline = phenoage_reference(sample)
        advanced = phenoage_reference({**sample, "age_years": 60})
        self.assertAlmostEqual(advanced - baseline, 10 * 0.0804 / 0.090165)
        self.assertTrue(20 < baseline < 60)


class SegmentationMetricsTest(unittest.TestCase):
    def setUp(self):
        import nibabel as nib
        self.nib = nib
        self.data = np.zeros((10, 12, 14), dtype=np.uint8)
        self.data[2:6, 3:8, 4:10] = 1
        self.reference = nib.Nifti1Image(self.data, np.diag([2.0, 2.0, 3.0, 1]))
        self.expected = {"reference_foreground_label": 1, "prediction_foreground_label": 3}

    def test_exact_mask_label_mapping(self):
        predicted = self.nib.Nifti1Image(self.data * 3, self.reference.affine)
        measured = segmentation_metrics(self.reference, predicted, self.expected)
        self.assertEqual(measured["dice"], 1)
        self.assertEqual(measured["iou"], 1)
        self.assertAlmostEqual(measured["reference_volume_ml"], 1.44)

    def test_empty_prediction_not_hidden_as_perfect_background(self):
        predicted = self.nib.Nifti1Image(np.zeros_like(self.data), self.reference.affine)
        measured = segmentation_metrics(self.reference, predicted, self.expected)
        self.assertEqual(measured["dice"], 0)
        self.assertFalse(measured["foreground_returned"])

    def test_wrong_affine_is_not_accepted(self):
        predicted = self.nib.Nifti1Image(self.data * 3, np.eye(4))
        with self.assertRaisesRegex(ValueError, "affine"):
            segmentation_metrics(self.reference, predicted, self.expected)


class GeneralAppMetricsTest(unittest.TestCase):
    def test_dna_length_and_alphabet_are_enforced(self):
        case = {"case_id": "dna", "expected": {"evaluator": "dna_continuation", "num_tokens": 4,
                                               "reference_continuation": "ACGT"}}
        result = {"sequence": "ACGT", "elapsed_ms_per_token": [2, 2, 2, 2]}
        self.assertTrue(evaluate(case, result)["service_semantic_pass"])
        self.assertFalse(evaluate(case, {**result, "sequence": "ACG!"})["service_semantic_pass"])

    def test_chat_scientific_accuracy_is_not_confused_with_json_contract(self):
        case = {"case_id": "chat", "expected": {"evaluator": "chat_json", "reference_answer": {"residues": 76}}}
        result = {"choices": [{"message": {"content": '{"residues": 75}'}, "finish_reason": "stop"}]}
        measured = evaluate(case, result)
        self.assertTrue(measured["service_semantic_pass"])
        self.assertFalse(measured["scientific_checks_pass"])

    def test_reasoning_only_output_is_not_a_visible_answer(self):
        case = {"case_id": "chat", "expected": {"evaluator": "chat_json", "reference_answer": {"residues": 76}}}
        result = {"choices": [{"message": {"content": "", "reasoning": 'I think the answer is {"residues":76}'}, "finish_reason": "length"}]}
        self.assertFalse(evaluate(case, result)["service_semantic_pass"])

    def test_tool_arguments_must_match_requested_function(self):
        case = {"case_id": "tool", "expected": {"evaluator": "chat_tool_call", "tool_name": "record", "reference_answer": {"residues": 76}}}
        result = {"choices": [{"message": {"tool_calls": [{"function": {"name": "record", "arguments": '{"residues":76}'}}]}, "finish_reason": "tool_calls"}]}
        self.assertTrue(evaluate(case, result)["service_semantic_pass"])
        result["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "invented"
        self.assertFalse(evaluate(case, result)["service_semantic_pass"])

    def test_cxr_weak_labels_remain_separate_from_service_pass(self):
        case = {"case_id": "cxr", "expected": {"evaluator": "cxr_findings", "allowed_findings": ["No Finding", "Nodule"], "reference_findings": ["Nodule"]}}
        result = {"choices": [{"message": {"content": '{"findings":["No Finding"]}'}, "finish_reason": "stop"}]}
        measured = evaluate(case, result)
        self.assertTrue(measured["service_semantic_pass"])
        self.assertFalse(measured["exact_weak_label_match"])
        self.assertEqual(measured["clinical_use"], "not_qualified")

    def test_blank_png_cannot_pass_generated_content_check(self):
        from PIL import Image
        image = Image.new("RGB", (512, 512), color="white")
        data = BytesIO()
        image.save(data, format="PNG")
        case = {"case_id": "image", "expected": {"evaluator": "generated_image", "size": [512, 512]}}
        result = {"data": [{"b64_json": base64.b64encode(data.getvalue()).decode()}]}
        self.assertFalse(evaluate(case, result)["service_semantic_pass"])


if __name__ == "__main__":
    unittest.main()
