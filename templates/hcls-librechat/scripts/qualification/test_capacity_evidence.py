import pytest

from capacity_evidence import per_pool_reservations, seconds_between, summarize_reservations


def test_missing_ready_measurements_do_not_use_registered_capacity():
    result = summarize_reservations([{"allocatable_gpus": 30, "reserved_gpus": 2}])
    assert result["measured_samples"] == 0
    assert result["unreserved_resource_units"] is None


def test_inconsistent_reservations_are_not_clamped():
    with pytest.raises(ValueError):
        summarize_reservations([{"schedulable_allocatable_gpus": 1, "schedulable_reserved_gpus": 2}])


def test_reservation_residual_does_not_claim_gpu_utilization_or_model_fit():
    result = summarize_reservations([{"schedulable_allocatable_gpus": 8, "schedulable_reserved_gpus": 3}])
    assert result["unreserved_resource_units"]["min"] == 5
    assert not result["is_gpu_utilization"] and not result["is_model_placement_headroom"]


def test_negative_duration_rejected():
    with pytest.raises(ValueError):
        seconds_between("2026-09-19T04:00:00Z", "2026-09-19T03:00:00Z")


def test_queue_interval_is_not_workflow_runtime():
    assert seconds_between("2026-09-19T02:56:42Z", "2026-09-19T03:14:43Z") == 1081


def test_unready_and_completed_reservations_excluded():
    nodes = [{"metadata": {"name": "ready"}, "status": {"allocatable": {"nvidia.com/gpu": "2"},
              "conditions": [{"type": "Ready", "status": "True"}]}},
             {"metadata": {"name": "lost"}, "status": {"allocatable": {"nvidia.com/gpu": "8"},
              "conditions": [{"type": "Ready", "status": "Unknown"}]}}]
    pods = [{"spec": {"nodeName": "ready", "containers": [{"resources": {
        "requests": {"nvidia.com/gpu": "1"}}}]}, "status": {"phase": phase}}
            for phase in ("Running", "Succeeded")]
    assert per_pool_reservations(nodes, pods) == [{"pool_id": "unknown", "nodes": 1,
        "ready_gpu_units": 2, "reserved_gpu_units": 1, "unreserved_gpu_units": 1}]
