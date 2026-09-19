import copy

import pytest

from set_test_replicas import proposed_spec


def spec():
    return {"availability": {"minReplicas": 1, "maxReplicas": 4},
            "lifecycle": {"desiredState": "Enabled"},
            "runtime": {"image": "registry/exact@sha256:unchanged"},
            "placement": {"gpuCount": 1}}


def test_only_minimum_changes_and_input_is_unchanged():
    original = spec()
    before = copy.deepcopy(original)
    changed = proposed_spec(original, 2)
    assert original == before
    changed["availability"]["minReplicas"] = 1
    assert changed == before


@pytest.mark.parametrize("replicas", [-1, 5, True, 1.5, "2"])
def test_existing_maximum_and_integer_contract(replicas):
    with pytest.raises(ValueError):
        proposed_spec(spec(), replicas)


def test_do_not_reactivate_drained_app():
    original = spec()
    original["lifecycle"]["desiredState"] = "Draining"
    with pytest.raises(ValueError):
        proposed_spec(original, 2)
