import json
import tempfile
import unittest
from pathlib import Path

from aggregate_campaign import markdown, scan, utc

OP = "11111111-1111-4111-8111-111111111111"
CHILD = "22222222-2222-4222-8222-222222222222"
PROBE = "33333333-3333-4333-8333-333333333333"
ATTEMPT = "44444444-4444-4444-8444-444444444444"


class AggregationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def receipt(self, prefix="cohorts/first/scientist-01/case", **kw):
        value = {
            "operation_id": OP,
            "model_id": "model",
            "state": "verified",
            "identity": {"cohort": "first"},
            "finished_at": "2026-09-19T01:00:00Z",
        }
        value.update(kw)
        self.put(prefix + "/receipt.json", value)
        return prefix

    def report(self, **kw):
        return scan(self.root, utc("2026-09-19T02:00:00Z"), **kw)

    def test_duplicates_polls_and_discovery_not_calls(self):
        prefix = self.receipt()
        self.receipt("browser-evidence/download/workspace/run")
        for name in ("operation.json", "status-0001.json", "status-0002.json"):
            self.put(
                prefix + "/" + name,
                {"id": OP, "model_id": "model", "status": "succeeded"},
            )
        self.put(
            prefix + "/discovery.json",
            {"id": CHILD, "model_id": "model", "status": "succeeded"},
        )
        self.put(
            "browser-evidence/acquisition/receipt.json",
            {"conversation_id": PROBE, "files": []},
        )
        report = self.report()
        self.assertEqual(report["counts"]["durable_operation_ids"], 1)
        self.assertEqual(report["counts"]["service_states"], {"succeeded": 1})

    def test_separate_status_refresh_does_not_create_new_admissions(self):
        prefix = self.receipt(state="running")
        self.put(prefix + "/operation.json", {
            "id": OP, "model_id": "model", "status": "running",
            "started_at": "2026-09-19T00:50:00Z",
        })
        self.put("final-refresh/one/operation.json", {
            "id": OP, "model_id": "model", "status": "succeeded",
            "completed_at": "2026-09-19T01:30:00Z",
        })
        self.put("unrelated/operation.json", {
            "id": PROBE, "model_id": "model", "status": "succeeded",
        })
        result = self.report()
        self.assertEqual(result["counts"]["durable_operation_ids"], 1)
        self.assertEqual(result["counts"]["service_states"], {"succeeded": 1})
        self.assertEqual(len(result["operations"][0]["observations"]), 2)

    def test_history_directory_is_not_a_read_error_but_bad_json_still_is(self):
        self.receipt()
        history = self.root / "browser-evidence/run/.receipt-history/receipt.json"
        history.mkdir(parents=True)
        (history / "generation.json").write_text(json.dumps({"operation_id": OP}))
        malformed = self.root / "cohorts/malformed/receipt.json"
        malformed.parent.mkdir(parents=True)
        malformed.write_text("not-json")
        result = self.report()
        self.assertEqual(result["counts"]["durable_operation_ids"], 1)
        self.assertEqual(result["scan"]["receipt_history_directories_excluded"], 1)
        self.assertEqual(result["scan"]["admission_receipt_files"], 2)
        self.assertEqual(result["scan"]["errors"], [{
            "path": "cohorts/malformed/receipt.json",
            "error_type": "JSONDecodeError",
        }])

    def test_separate_child_upload_is_not_a_model_call(self):
        self.receipt()
        self.put("child-refresh/children.json", {"children": [
            {"id": CHILD, "parent_operation_id": OP, "model_id": "child",
             "protocol": "scientific-artifact-upload-v1", "operation": "upload",
             "status": "succeeded", "completed_at": "2026-09-19T01:10:00Z"},
            {"id": PROBE, "parent_operation_id": OP, "model_id": "child",
             "protocol": "native", "operation": "generate-media",
             "status": "succeeded", "started_at": "2026-09-19T01:11:00Z",
             "completed_at": "2026-09-19T01:12:00Z"},
        ]})
        result = self.report()
        self.assertEqual(result["counts"]["durable_operation_ids"], 2)
        self.assertEqual(result["counts"]["operation_kinds"],
                         {"top_level_serving": 1, "child_inference": 1})
        self.assertEqual([r["operation_id"] for r in result["auxiliary_operations_excluded"]], [CHILD])

    def test_future_separate_refresh_does_not_replace_observed_state(self):
        self.receipt(state="running")
        self.put("final-refresh/operation.json", {
            "id": OP, "model_id": "model", "status": "succeeded",
            "completed_at": "2026-09-19T03:00:00Z",
        })
        self.assertEqual(self.report()["counts"]["service_states"], {"running": 1})

    def test_activating_status_is_retained_and_known_upload_not_inference(self):
        self.receipt(state="queued")
        self.put("separate/operation.json", {
            "id": OP, "model_id": "model", "status": "activating", "protocol": "native",
        })
        self.assertEqual(self.report()["counts"]["service_states"], {"activating": 1})
        self.put("separate/operation.json", {
            "id": OP, "model_id": "model", "status": "succeeded",
            "protocol": "scientific-artifact-upload-v1", "operation": "upload",
        })
        result = self.report()
        self.assertEqual(result["counts"]["top_level_inference_request_ids"], 0)
        self.assertEqual(len(result["auxiliary_operations_excluded"]), 1)

    def test_captured_admin_response_requires_success_and_exact_operation_shape(self):
        self.receipt(state="running")
        operation = {"id": OP, "model_id": "model", "status": "succeeded",
                     "completed_at": "2026-09-19T01:30:00Z"}
        self.put("admin/operation.json", {"http_status": 500, "body": {"data": {"operation": operation}}})
        self.assertEqual(self.report()["counts"]["service_states"], {"running": 1})
        self.put("admin/operation.json", {"http_status": 200, "body": {"data": {"operation": operation}}})
        self.assertEqual(self.report()["counts"]["service_states"], {"succeeded": 1})

    def test_offline_reassessments_preserve_failed_history(self):
        prefix = self.receipt(reevaluated_at="2026-09-19T01:10:00Z")
        self.put(
            prefix + "/evaluation-before-abc.json",
            {"service_semantic_pass": False, "evaluator": "protein_structure"},
        )
        self.put(
            prefix + "/evaluation.json",
            {"service_semantic_pass": True, "evaluator": "protein_structure"},
        )
        self.put(
            prefix + "/evaluation-reassessment.json",
            {"service_semantic_pass": True, "evaluator": "protein_structure"},
        )
        row = self.report()["operations"][0]
        self.assertEqual(row["independent_check_state"], "pass")
        self.assertTrue(row["historical_failed_check_retained"])
        self.assertEqual(len(row["evaluations"]), 3)

    def test_conflicting_new_verdicts_not_silently_selected(self):
        prefix = self.receipt()
        self.put(prefix + "/evaluation.json", {"service_semantic_pass": False})
        self.put(
            prefix + "/evaluation-reassessment.json", {"service_semantic_pass": True}
        )
        row = self.report()["operations"][0]
        self.assertEqual(row["independent_check_state"], "mixed_retained_verdicts")

    def test_batch_parent_stages_and_child_probe_separate(self):
        prefix = self.receipt()
        self.put(
            prefix + "/final-status.json",
            {
                "operation": {
                    "id": OP,
                    "model_id": "model",
                    "status": "succeeded",
                    "protocol": "scientific-batch-v1",
                },
                "batch": {
                    "stages": [
                        {
                            "stage_id": "evaluate",
                            "attempts": [
                                {"attempt_id": ATTEMPT, "outcome": "succeeded"}
                            ],
                        }
                    ]
                },
            },
        )
        children = [
            {
                "id": child,
                "parent_operation_id": OP,
                "model_id": "child",
                "status": "succeeded",
                "started_at": started,
            }
            for child, started in [(CHILD, "2026-09-19T01:00:00Z"), (PROBE, None)]
        ]
        self.put(prefix + "/children.json", {"children": children})
        result = self.report()
        self.assertEqual(
            result["counts"]["operation_kinds"],
            {
                "top_level_scientific_batch": 1,
                "child_inference": 1,
                "child_execution_unconfirmed": 1,
            },
        )
        self.assertEqual(result["counts"]["observed_stage_attempts"], 1)
        self.assertEqual(result["counts"]["top_level_inference_request_ids"], 1)
        self.assertEqual(result["counts"]["top_level_service_states"], {"succeeded": 1})
        self.assertEqual(result["counts"]["child_service_states"], {"succeeded": 2})
        self.assertEqual(sum(result["counts"]["service_states"].values()), 3)
        report = markdown(result)
        self.assertIn("Top-level service states", report)
        self.assertIn("separate denominator", report)

    def test_unadmitted_capacity_not_model_failure_and_private_fields_omitted(self):
        for name in ("a", "b"):
            self.receipt(
                "cohorts/run/" + name,
                operation_id=None,
                state="admission_deferred",
                idempotency_key="private-key",
                api_key="SECRET_NOT_IN_REPORT",
                identity={"key_id": "private-caller"},
                error_detail="SECRET_NOT_IN_REPORT",
            )
        result = self.report()
        self.assertEqual(result["counts"]["durable_operation_ids"], 0)
        self.assertEqual(len(result["unadmitted_logical_items"]), 1)
        rendered = json.dumps(result)
        self.assertNotIn("SECRET_NOT_IN_REPORT", rendered)
        self.assertNotIn("private-key", rendered)

    def test_current_runtime_requires_exact_evidence(self):
        prefix = self.receipt()
        self.put(
            prefix + "/result-envelope.json",
            {
                "schema": "fs2-serve.nebius.ai/scientific-run-result/v1",
                "operation_id": OP,
                "terminal_status": "succeeded",
                "execution_identity": {
                    "model_id": "model",
                    "runtime_image_digest": "sha256:old",
                    "execution_identity_sha256": "old",
                },
            },
        )
        result = self.report(
            current={"apps": {"model": {"execution_identity_sha256": "new"}}}
        )
        self.assertEqual(
            result["operations"][0]["runtime_comparison"],
            "different_or_historical_identity",
        )

    def test_synthetic_tests_and_isolated_are_not_public(self):
        self.receipt("workbench-tests/test_live/record")
        self.receipt("diffdock-final-isolated-r6/results")
        self.assertEqual(self.report()["counts"]["durable_operation_ids"], 0)

    def test_upload_operation_is_not_model_inference(self):
        self.receipt(
            state="finalized", upload_id=CHILD, artifact={"artifact_id": PROBE}
        )
        self.assertEqual(self.report()["counts"]["durable_operation_ids"], 0)

    def test_stage_public_result_uses_status_and_deduplicates(self):
        prefix = self.receipt()
        self.put(
            prefix + "/result-envelope.json",
            {
                "schema": "fs2-serve.nebius.ai/scientific-run-result/v1",
                "operation_id": OP,
                "terminal_status": "succeeded",
                "execution_identity": {"model_id": "model"},
                "attempts": [
                    {
                        "attempt_id": ATTEMPT,
                        "stage_id": "generate",
                        "status": "succeeded",
                    }
                ],
            },
        )
        self.assertEqual(
            self.report()["counts"]["stage_attempt_states"], {"succeeded": 1}
        )

    def test_design_outputs_and_reassessment_not_additional_calls(self):
        prefix = self.receipt()
        self.put(
            prefix + "/evaluation.json",
            {
                "evaluator": "design_constraints",
                "service_semantic_pass": True,
                "design_count": 4,
                "coordinate_artifact_count": 8,
                "self_refolded_geometry_pass_count": 4,
            },
        )
        self.put(
            prefix + "/evaluation-reassessment.json",
            {
                "evaluator": "design_constraints",
                "service_semantic_pass": True,
                "design_count": 4,
            },
        )
        report = self.report()
        self.assertEqual(report["counts"]["durable_operation_ids"], 1)
        self.assertEqual(
            report["by_app"]["model"]["observed_output_counts_not_calls"][
                "design_count"
            ],
            4,
        )

    def test_exhausted_finite_search_not_unknown_platform_error(self):
        prefix = self.receipt(state="failed")
        self.put(
            prefix + "/operation.json",
            {
                "id": OP,
                "model_id": "model",
                "status": "failed",
                "error_code": "generation_exhausted",
            },
        )
        self.assertEqual(
            self.report()["operations"][0]["cause_classification"],
            "bounded_generation_exhaustion",
        )

    def test_future_receipt_excluded(self):
        self.receipt(finished_at="2026-09-19T03:00:00Z")
        self.assertEqual(self.report()["counts"]["durable_operation_ids"], 0)

    def test_unknown_failure_not_guessed_capacity(self):
        prefix = self.receipt(state="failed")
        self.put(
            prefix + "/operation.json",
            {
                "id": OP,
                "model_id": "model",
                "status": "failed",
                "error_code": "upstream_error",
            },
        )
        self.assertEqual(
            self.report()["operations"][0]["cause_classification"], "unknown_cause"
        )

    def test_markdown_separates_samples_and_calls(self):
        self.receipt()
        output = markdown(self.report())
        self.assertIn("not a readiness verdict", output)
        self.assertIn("not scientific efficacy", output)


if __name__ == "__main__":
    unittest.main()
