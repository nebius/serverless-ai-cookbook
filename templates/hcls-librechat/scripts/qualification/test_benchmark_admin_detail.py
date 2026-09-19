import json
from unittest.mock import Mock

import httpx
import pytest

from benchmark_admin_detail import run_probe


OP = "00000000-0000-4000-8000-000000000001"


def probe(tmp_path, outcomes):
    client = Mock()
    client.get.side_effect = outcomes
    ticks = iter(range(len(outcomes) * 2))
    output = tmp_path / "new"
    report = run_probe(client, [OP], len(outcomes), output, clock=lambda: next(ticks), pause=lambda _: None)
    return report, client, output


def test_success_records_only_planned_gets_and_protected_files(tmp_path):
    report, client, output = probe(tmp_path, [httpx.Response(200, json={
        "meta": {"request_id": "request-1"}, "data": {"run": {"id": OP}, "artifacts": []}})] * 2)
    assert report["all_http_200"] and report["all_detail_envelopes_valid"]
    assert report["requests"] == 2 and report["median_seconds"] == 1
    assert report["status_counts"] == {"200": 2}
    assert all(call.args == ("/admin/api/v1/scientific-runs/" + OP,) for call in client.get.call_args_list)
    assert json.loads((output / "observations.json").read_text())[0]["request_id"] == "request-1"
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())


def test_json_and_html_503_are_retained_without_retry_or_denominator_loss(tmp_path):
    report, client, output = probe(tmp_path, [
        httpx.Response(503, json={"meta": {"request_id": "json-id"}, "error": "unavailable"}),
        httpx.Response(503, text="upstream unavailable", headers={"x-request-id": "html-id"}),
    ])
    assert not report["all_http_200"] and not report["all_detail_envelopes_valid"]
    assert report["requests"] == client.get.call_count == 2
    assert report["status_counts"] == {"503": 2}
    retained = json.loads((output / f"1-{OP}.json").read_text())
    assert retained["body_text"] == "upstream unavailable"
    assert retained["observation"]["request_id"] == "html-id"
    assert retained["observation"]["body_error"] == "non_json_response"


@pytest.mark.parametrize("body", [None, [], {"data": []}, {"meta": None, "data": {}}, "not an envelope"])
def test_200_malformed_envelope_is_not_semantic_success(tmp_path, body):
    report, _, _ = probe(tmp_path, [httpx.Response(200, content=json.dumps(body))])
    assert report["all_http_200"] and not report["all_detail_envelopes_valid"]


def test_transport_failure_retains_type_not_private_exception_message(tmp_path):
    report, client, output = probe(tmp_path, [httpx.ReadTimeout("private URL or credential")])
    assert report["status_counts"] == {"transport_error": 1}
    assert report["requests"] == client.get.call_count == 1
    rows = json.loads((output / "observations.json").read_text())
    assert rows[0]["transport_error"] == "ReadTimeout"
    assert rows[0]["http_status"] is None
    assert "private" not in "".join(path.read_text() for path in output.iterdir())


def test_existing_evidence_is_never_overwritten(tmp_path):
    client = Mock()
    with pytest.raises(ValueError, match="Preserve"):
        run_probe(client, [OP], 1, tmp_path)
    client.get.assert_not_called()


@pytest.mark.parametrize("operations,repetitions", [([], 1), ([OP], 0), ([OP], 21), (["not-a-uuid"], 1)])
def test_invalid_probe_rejected_before_network_or_files(tmp_path, operations, repetitions):
    client = Mock()
    output = tmp_path / "new"
    with pytest.raises(ValueError):
        run_probe(client, operations, repetitions, output)
    client.get.assert_not_called()
    assert not output.exists()
