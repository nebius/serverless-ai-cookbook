import json
import tempfile
import unittest
from pathlib import Path

from campaign_latency import (
    analyze,
    duration,
    native_identity,
    overlap_seconds,
    phases,
    raw_operations,
    thermal_state,
)


def time(second):
    return f"2026-09-19T00:00:{second:02d}Z"


def operation():
    return {
        "id": "11111111-1111-4111-8111-111111111111",
        "model_id": "model",
        "status": "succeeded",
        "accepted_at": time(10),
        "activation_started_at": time(12),
        "ready_at": time(15),
        "started_at": time(16),
        "completed_at": time(20),
        "runtime": {"pod_uid": "exact-pod"},
    }


class LatencyTest(unittest.TestCase):
    def test_mutated_operation_snapshot_does_not_backdate_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "operation.json").write_text(json.dumps(operation()))
            issues = []
            values = raw_operations(
                {
                    "operation_id": operation()["id"],
                    "sources": [{"path": "operation.json", "sha256": "prior-snapshot"}],
                },
                root,
                issues,
            )
            self.assertEqual(values, [])
            self.assertEqual(issues[0]["reason"], "changed_since_aggregate")

    def test_negative_missing_zero_are_distinct(self):
        self.assertEqual(duration(time(20), time(10))["reason"], "negative_duration")
        self.assertIsNone(duration(None, time(10))["seconds"])
        self.assertEqual(duration(time(10), time(10))["seconds"], 0)

    def test_complete_partition_not_overlapping_composite_sum(self):
        value = phases(operation())
        self.assertEqual(value["end_to_end"]["seconds"], 10)
        self.assertEqual(value["partition"]["sum_seconds"], 10)
        self.assertTrue(value["partition"]["complete_nonoverlapping"])
        self.assertEqual(value["accepted_to_ready"]["seconds"], 5)
        self.assertEqual(value["pre_execution_wait"]["seconds"], 6)

    def test_backwards_phase_invalid_not_clipped(self):
        op = operation()
        op["ready_at"] = time(18)
        value = phases(op)
        self.assertEqual(value["ready_to_execution"]["reason"], "negative_duration")
        self.assertFalse(value["partition"]["complete_nonoverlapping"])
        self.assertIsNone(value["partition"]["sum_seconds"])

    def test_missing_activation_cannot_be_called_queue_or_cold(self):
        op = operation()
        op.pop("activation_started_at")
        op["cold_start_seconds"] = 150
        self.assertIsNone(phases(op)["queue_before_activation"]["seconds"])
        self.assertEqual(thermal_state(op, {}), "unknown")

    def test_activation_and_short_response_do_not_prove_warm(self):
        self.assertEqual(thermal_state(operation(), {}), "unknown")
        op = operation()
        op["cold_start_seconds"] = 0
        self.assertEqual(thermal_state(op, {}), "unknown")

    def pod(self, **values):
        record = {
            "image_digest": "sha256:" + "1" * 64,
            "image_id": "containerd://sha256:" + "1" * 64,
            "container_id": "containerd://container-one",
            "restart_count": 0,
            "created_at": time(1),
            "container_started_at": time(2),
            "ready_at": time(3),
            "source": {"path": "pod.json", "sha256": "known"},
            **values,
        }
        return {
            "exact-pod": [
                {**record, "observed_after": time(15), "observed_before": time(15)},
                {**record, "observed_after": time(21), "observed_before": time(21)},
            ]
        }

    def test_warm_requires_exact_pod_and_prior_readiness(self):
        self.assertEqual(
            thermal_state(operation(), self.pod()), "ready_worker_before_acceptance"
        )
        self.assertEqual(
            thermal_state(operation(), {"another-pod": self.pod()["exact-pod"]}),
            "unknown",
        )

    def test_cold_worker_requires_created_during_request(self):
        self.assertEqual(
            thermal_state(
                operation(),
                self.pod(
                    created_at=time(11),
                    container_started_at=time(13),
                    ready_at=time(15),
                ),
            ),
            "new_worker_during_request",
        )
        self.assertEqual(
            thermal_state(operation(), self.pod(ready_at=time(15))), "unknown"
        )

    def test_later_restart_cannot_supply_old_request_image(self):
        result = native_identity(operation(), self.pod(container_started_at=time(30)))
        self.assertIsNone(result["image_digest"])
        self.assertEqual(
            thermal_state(
                operation(), self.pod(container_started_at=time(30), ready_at=time(31))
            ),
            "unknown",
        )

    def test_exact_uid_image_join_and_conflict(self):
        first = native_identity(operation(), self.pod())
        self.assertEqual(first["image_digest"], "sha256:" + "1" * 64)
        pods = self.pod()
        pods["exact-pod"].append(
            {**pods["exact-pod"][0], "image_digest": "sha256:" + "2" * 64}
        )
        self.assertEqual(
            native_identity(operation(), pods)["method"],
            "conflicting_pod_container_observations",
        )
        self.assertEqual(thermal_state(operation(), pods), "unknown")

    def test_unbracketed_and_restarted_same_image_stay_unknown(self):
        pods = self.pod()
        pods["exact-pod"] = pods["exact-pod"][:1]
        self.assertEqual(
            native_identity(operation(), pods)["method"], "unbracketed_pod_observation"
        )
        self.assertEqual(thermal_state(operation(), pods), "unknown")
        pods = self.pod()
        pods["exact-pod"][1]["container_id"] = "containerd://container-two"
        pods["exact-pod"][1]["restart_count"] = 1
        self.assertIsNone(native_identity(operation(), pods)["image_digest"])
        self.assertEqual(thermal_state(operation(), pods), "unknown")

    def test_desired_image_does_not_overwrite_running_image_identity(self):
        pods = self.pod(image_id="registry/model@sha256:" + "2" * 64)
        identity = native_identity(operation(), pods)
        self.assertIsNone(identity["image_digest"])
        self.assertEqual(
            identity["method"], "desired_actual_image_relationship_unverified"
        )

    def test_stage_overlap_not_double_counted(self):
        value = overlap_seconds(
            [(time(1), time(10)), (time(5), time(15)), (time(20), time(19))]
        )
        self.assertEqual(value["summed_seconds"], 19)
        self.assertEqual(value["union_seconds"], 14)
        self.assertEqual(value["overlap_seconds"], 5)
        self.assertEqual(value["invalid_intervals"], 1)

    def test_duplicate_snapshots_one_latency_sample_and_latest_not_assumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            op = operation()
            (root / "operation.json").write_text(json.dumps(op))
            row = {
                "operation_id": op["id"],
                "model_id": "model",
                "operation_kind": "top_level_serving",
                "workflow": "study",
                "service_state": "succeeded",
                "cause_classification": "not_classified",
                "error_codes": [],
                "receipts": [{"elapsed_seconds": 12}, {"elapsed_seconds": 12}],
                "sources": [{"path": "operation.json"}, {"path": "operation.json"}],
            }
            result = analyze(
                {"as_of": time(40), "operations": [row]},
                root,
                {"apps": {"model": {"runtime_image_digest": "sha256:" + "9" * 64}}},
                self.pod(),
            )
            self.assertEqual(result["all_top_level"]["operations"], 1)
            self.assertEqual(
                result["all_top_level"]["timings_seconds"]["end_to_end"]["observed"], 1
            )
            self.assertEqual(
                result["operations"][0]["runtime_comparison"],
                "historical_or_different_image",
            )


if __name__ == "__main__":
    unittest.main()
