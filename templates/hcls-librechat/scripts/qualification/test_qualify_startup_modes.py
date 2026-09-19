import json

from qualify_startup_modes import mechanisms, policy_body


def test_only_startup_choice_changes_not_limits_pause_or_reason():
    original = {"revision": 3, "paused": False, "max_active_runs": 2,
                "reason": "Existing tenant choice", "startup_policies": {}}
    startup = {"fold": {"backend": "cuda-criu", "bundle_id": "exact-bundle"}}
    result = policy_body(original, startup, revision=4)
    assert result == {"expected_revision": 4, "paused": False, "max_active_runs": 2,
                      "reason": "Existing tenant choice", "startup_policies": startup}
    assert original["revision"] == 3 and original["startup_policies"] == {}
    assert policy_body(original, {})["expected_revision"] == 3


def test_mechanism_needs_an_actual_supervisor_witness_not_requested_policy(tmp_path):
    folder = tmp_path / "worker-logs"
    folder.mkdir()
    assert mechanisms(tmp_path) == []
    snapshot = {"pod_uid": "owned-pod", "containers": {"stage": {"text":
        '2026-09-19T00:00:00Z {"event":"scientific_snapshot_request","mechanism":"normal-load-fallback"}\n'
        '2026-09-19T00:00:01Z {"event":"not_request","mechanism":"cuda-criu-restored"}\n'
        '2026-09-19T00:00:02Z broken "scientific_snapshot_request"\n'}}}
    (folder / "first.json").write_text(json.dumps(snapshot))
    (folder / "second.json").write_text(json.dumps(snapshot))
    assert mechanisms(tmp_path) == [{"pod_uid": "owned-pod", "at": "2026-09-19T00:00:00Z",
                                    "mechanism": "normal-load-fallback"}]
