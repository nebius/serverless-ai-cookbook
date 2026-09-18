from observe_campaign import gpu_capacity


def node(name, ready="True", **spec):
    return {"metadata": {"name": name}, "spec": spec,
            "status": {"conditions": [{"type": "Ready", "status": ready}], "allocatable": {"nvidia.com/gpu": "8"}}}


def test_registered_stopped_gpus_are_not_counted_as_available():
    nodes = [node("live"), node("stopped", "Unknown"), node("shutdown", taints=[
        {"key": "node.cloudprovider.kubernetes.io/shutdown", "effect": "NoSchedule"}]), node("cordoned", unschedulable=True)]
    pods = [{"status": {"phase": "Running"}, "spec": {"nodeName": name,
             "containers": [{"resources": {"requests": {"nvidia.com/gpu": "2"}}}]}} for name in ("live", "stopped")]
    assert gpu_capacity(nodes, pods) == {"ready_allocatable_gpus": 24, "schedulable_allocatable_gpus": 8,
        "ready_reserved_gpus": 2, "schedulable_reserved_gpus": 2, "registered_unready_gpus": 8}
