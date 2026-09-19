import copy
from uuid import uuid4

import pytest

from qualify_worker_recovery import LABEL, eviction_body, request_identity, recovery_verified
import qualify_worker_recovery as recovery


def fixture():
    owner = {"operation_id": str(uuid4()), "workload_id": str(uuid4()),
             "tenant_id": "qualification-lab", "stage_id": "fold"}
    labels = {LABEL + key.replace("_", "-"): value for key, value in owner.items()}
    labels[LABEL + "attempt-id"] = str(uuid4())
    pod = {"metadata": {"name": "owned-worker", "namespace": "fs2-models", "uid": str(uuid4()),
           "labels": labels, "ownerReferences": [{"kind": "Job", "controller": True}]},
           "spec": {"nodeName": "test-node", "containers": [{"resources": {"requests": {"nvidia.com/gpu": 1}}}]},
           "status": {"phase": "Running"}}
    return pod, owner


def test_eviction_is_uid_bound_and_only_one_pod():
    pod, owner = fixture()
    result = eviction_body(pod, **owner)
    assert result["deleteOptions"]["preconditions"] == {"uid": pod["metadata"]["uid"]}
    assert result["metadata"] == {"name": "owned-worker", "namespace": "fs2-models"}
    assert result["kind"] == "Eviction"
    assert "gracePeriodSeconds" not in result["deleteOptions"]


@pytest.mark.parametrize("label", ["operation-id", "workload-id", "tenant-id", "stage-id"])
def test_unrelated_worker_is_refused(label):
    pod, owner = fixture()
    pod["metadata"]["labels"][LABEL + label] = "another-owner"
    with pytest.raises(ValueError, match="ownership"):
        eviction_body(pod, **owner)


@pytest.mark.parametrize("phase", ["Pending", "Succeeded", "Failed"])
def test_only_running_worker(phase):
    pod, owner = fixture()
    pod["status"]["phase"] = phase
    with pytest.raises(ValueError, match="active"):
        eviction_body(pod, **owner)


def test_terminal_or_unowned_or_cpu_worker_refused():
    original, owner = fixture()
    changes = [lambda p: p["metadata"].update(deletionTimestamp="2026-09-19T00:00:00Z"),
               lambda p: p["metadata"].update(ownerReferences=[]),
               lambda p: p["spec"]["containers"][0]["resources"].update(requests={}),
               lambda p: p["spec"].pop("nodeName")]
    for change in changes:
        pod = copy.deepcopy(original)
        change(pod)
        with pytest.raises(ValueError):
            eviction_body(pod, **owner)


def test_new_fixture_preserves_scientific_request_and_immutable_input():
    source = {"parameters": {"seed": 7}, "input_manifest": {"sha256": "a" * 64},
              "idempotency_key": "old", "client_context": {"display_name": "old"}}
    result, digest = request_identity(source, run_id="new")
    assert result["parameters"] == source["parameters"]
    assert result["input_manifest"] == source["input_manifest"]
    assert result["idempotency_key"] == "new"
    assert source["idempotency_key"] == "old"
    assert digest == request_identity(source, run_id="another")[1]


def test_recovery_requires_exact_bounded_attempt_lineage_and_resource_release():
    attempts = [
        {"attempt_id": "first", "attempt_number": 1, "outcome": "failed",
         "failure_kind": "infrastructure", "resource_released": True},
        {"attempt_id": "second", "attempt_number": 2, "outcome": "succeeded",
         "failure_kind": None, "resource_released": True}]
    assert recovery_verified(attempts, {"attempt_id": "first"})
    assert recovery_verified(list(reversed(attempts)), {"attempt_id": "first"})
    for index, key, value in [(0, "failure_kind", "application"),
                              (0, "attempt_id", "unrelated"),
                              (1, "attempt_id", "first"),
                              (1, "attempt_number", 3),
                              (1, "outcome", "failed"),
                              (0, "resource_released", False),
                              (1, "resource_released", False)]:
        changed = copy.deepcopy(attempts)
        changed[index][key] = value
        assert not recovery_verified(changed, {"attempt_id": "first"})
    assert not recovery_verified(attempts[:1], {"attempt_id": "first"})
    assert not recovery_verified(attempts, None)


def test_node_capture_is_read_only_uid_bound_and_keeps_driver_package_suffix(monkeypatch):
    pod, _ = fixture()
    calls = []
    def read(*args):
        calls.append(args)
        return {'metadata': {'name': 'test-node', 'uid': 'node-uid',
            'labels': {'nebius.com/nvidia_driver_version': '580.159.04-1ubuntu1'}}}
    monkeypatch.setattr(recovery, 'kube', read)
    value = recovery.worker_node(pod)
    assert calls == [('get', 'node', 'test-node')]
    assert value['pod_uid'] == pod['metadata']['uid']
    assert value['node']['metadata']['labels']['nebius.com/nvidia_driver_version'] == '580.159.04-1ubuntu1'
    assert 'not an in-container' in value['driver_evidence']
    assert value['available']
    pod['spec'].pop('nodeName')
    assert recovery.worker_node(pod) is None
    assert len(calls) == 1


def test_unavailable_node_observation_does_not_cancel_admitted_model(monkeypatch):
    pod, _ = fixture()
    def unavailable(*args):
        raise RuntimeError('Diagnostic read unavailable')
    monkeypatch.setattr(recovery, 'kube', unavailable)
    value = recovery.worker_node(pod)
    assert value['available'] is False and value['error_type'] == 'RuntimeError'
