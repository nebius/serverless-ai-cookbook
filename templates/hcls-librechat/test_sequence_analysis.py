"""Saved DNA continuation contracts; never hosted generation."""

import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "sequence_analysis", Path(__file__).with_name("sequence-analysis.py")
)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def request(seed=1):
    return {
        "sequence": "ACGT",
        "num_tokens": 4,
        "random_seed": seed,
        "temperature": 0.7,
        "top_k": 4,
        "top_p": 0.95,
    }


def result(sequence="GCGT"):
    return {
        "sequence": sequence,
        "elapsed_ms": 2951.319835,
        "elapsed_ms_per_token": [1.0, 2.0, 3.0, 4.0],
        "sampled_probs": None,
        "logits": None,
    }


def case(**extra):
    return {"id": "sample", "start_zero_based": 0, **extra}


def operation():
    return {
        "structuredContent": {
            "id": "actual-op",
            "model_id": "evo2-40b",
            "status": "succeeded",
            "accepted_at": "2026-09-19T18:00:00Z",
            "started_at": "2026-09-19T18:00:03Z",
            "completed_at": "2026-09-19T18:00:07Z",
            "runtime": {"pod_uid": "observed-pod"},
        }
    }


def test_suffix_units_counts_and_actual_operation_identity():
    row = analysis.analyze_case(case(), request(), result(), "ACGTGCAA", operation())
    assert row["new_sequence"] == "GCGT" and row["sequence_mode"] == "suffix"
    assert (
        row["suffix"]["gc_count"] == 3
        and row["suffix"]["gc_fraction_all_positions"] == 0.75
    )
    assert row["reference_matching_acgt_positions"] == 2
    assert row["reference_match_fraction_requested"] == 0.5
    assert (
        row["model_elapsed_ms"] == 2951.319835
        and row["model_elapsed_seconds"] == "2.951319835"
    )
    assert (
        row["operation"]["id"] == "actual-op"
        and row["operation"]["accepted_to_started_seconds"] == 3
    )
    assert (
        row["operation"]["started_to_completed_seconds"] == 4
        and row["operation"]["accepted_to_completed_seconds"] == 7
    )
    assert row["operation"]["runtime"] == {"pod_uid": "observed-pod"}
    assert row["sampled_probs"] is None and row["flags"] == []


def test_prefix_echo_is_explicit_not_startswith_guessing():
    row = analysis.analyze_case(
        case(sequence_mode="prefix-and-suffix"),
        request(),
        result("ACGTGCGT"),
        "ACGTGCAA",
    )
    assert row["new_sequence"] == "GCGT"
    raw = analysis.analyze_case(case(), request(), result("ACGT"), "ACGTGCAA")
    assert raw["new_sequence"] == "ACGT" and raw["suffix"]["length"] == 4
    with pytest.raises(ValueError, match="Declared returned prefix"):
        analysis.analyze_case(
            case(sequence_mode="prefix-and-suffix"),
            request(),
            result("WRONG"),
            "ACGTGCAA",
        )


@pytest.mark.parametrize(
    "sequence,flags",
    [
        ("", ["underfilled", "per_token_timing_length_mismatch"]),
        (
            "NC",
            [
                "underfilled",
                "non_acgt_output_retained",
                "per_token_timing_length_mismatch",
            ],
        ),
        ("ACGTA", ["overfilled", "per_token_timing_length_mismatch"]),
    ],
)
def test_poor_ambiguous_and_wrong_length_results_are_retained(sequence, flags):
    row = analysis.analyze_case(case(), request(), result(sequence), "ACGTGCAA")
    assert row["new_sequence"] == sequence and row["flags"] == flags
    if sequence == "NC":
        assert row["suffix"]["gc_fraction_all_positions"] == 0.5
        assert row["suffix"]["gc_fraction_acgt_only"] == 1
    if not sequence:
        assert row["suffix"]["gc_fraction_all_positions"] is None
        assert row["reference_match_fraction_overlap"] is None


def test_returned_sampling_probabilities_preserved_not_likelihood():
    data = result()
    data["sampled_probs"] = [0.1, 0.2, 0.3, 0.4]
    data["logits"] = [[-1, 2]]
    row = analysis.analyze_case(case(), request(), data, "ACGTGCAA")
    assert (
        row["sampled_probs"] == data["sampled_probs"]
        and row["logits"] == data["logits"]
    )
    assert "likelihood" not in row


def test_unknown_identity_and_timing_remain_unknown():
    row = analysis.analyze_case(case(), request(), {"sequence": "AAAA"}, "ACGTGCAA")
    assert row["model_elapsed_seconds"] is None and row["operation"]["id"] is None
    assert row["operation"]["accepted_to_completed_seconds"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"elapsed_ms": -1},
        {"elapsed_ms": True},
        {"elapsed_ms_per_token": "1"},
        {"sampled_probs": [float("nan")]},
        {"sampled_probs": [1.1]},
        {"sequence": None},
    ],
)
def test_invalid_measurement_schema_fails_explicitly(change):
    with pytest.raises(ValueError):
        analysis.analyze_case(case(), request(), result() | change, "ACGTGCAA")


@pytest.mark.parametrize(
    "change",
    [
        {"num_tokens": True},
        {"num_tokens": 0},
        {"random_seed": "7"},
        {"sequence": "TTTT"},
    ],
)
def test_invalid_request_or_wrong_reference_not_repaired(change):
    with pytest.raises(ValueError):
        analysis.analyze_case(case(), request() | change, result(), "ACGTGCAA")


def test_reference_bounds_and_explicit_fasta_selection():
    assert analysis.reference_sequence(b"ACGT\nGCAA\n") == (None, "ACGTGCAA")
    fasta = b">one description\nACGT\n>two\nGCAA\n"
    assert analysis.reference_sequence(fasta, "two") == ("two", "GCAA")
    with pytest.raises(ValueError, match="exactly one"):
        analysis.reference_sequence(fasta)
    with pytest.raises(ValueError, match="too short"):
        analysis.analyze_case(case(), request(), result(), "ACGT")


def test_negative_operation_durations_and_wrong_envelopes_fail():
    op = operation()
    op["structuredContent"]["started_at"] = "2026-09-19T17:59:00Z"
    with pytest.raises(ValueError):
        analysis.operation_measurements(op)
    with pytest.raises(ValueError, match="actual id"):
        analysis.operation_measurements(result())


def files(tmp_path, count=2):
    (tmp_path / "ref.fa").write_bytes(b">reference\nACGTGCAA\n")
    plan = {
        "title": "Observed continuations, not function",
        "reference_file": "ref.fa",
        "cases": [],
    }
    for index in range(count):
        for name, value in [
            ("request", request(index)),
            ("result", result("AAAA" if index else "GCGT")),
            ("operation", {"id": f"op-{index}", "status": "succeeded"}),
        ]:
            (tmp_path / f"{index}-{name}.json").write_text(json.dumps(value))
        plan["cases"].append(
            {
                "id": f"case-{index}",
                "start_zero_based": 0,
                "input_file": f"{index}-request.json",
                "result_file": f"{index}-result.json",
                "operation_file": f"{index}-operation.json",
            }
        )
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return path


@pytest.mark.parametrize("count", [1, 2, 3])
def test_measured_case_pair_counts_are_not_frozen_campaign_constants(tmp_path, count):
    plan = files(tmp_path, count)
    measured = analysis.analyze_plan(json.loads(plan.read_text()), tmp_path)
    assert (
        measured["case_count"] == count
        and measured["pair_count"] == count * (count - 1) // 2
    )
    if count > 1:
        assert measured["pairs"][0]["hamming_distance"] == 4
        assert measured["pairs"][0]["kind"] == "different-seed"


def test_different_sampling_settings_not_paired_and_same_seed_not_independence(
    tmp_path,
):
    plan = files(tmp_path)
    data = json.loads((tmp_path / "1-request.json").read_text())
    data["temperature"] = 0.8
    (tmp_path / "1-request.json").write_text(json.dumps(data))
    assert (
        analysis.analyze_plan(json.loads(plan.read_text()), tmp_path)["pair_count"] == 0
    )
    data["temperature"] = 0.7
    data["random_seed"] = 0
    (tmp_path / "1-request.json").write_text(json.dumps(data))
    assert (
        analysis.analyze_plan(json.loads(plan.read_text()), tmp_path)["pairs"][0][
            "kind"
        ]
        == "same-seed-repeat"
    )


def test_real_cli_two_seed_regression_manifest_and_idempotent_bytes(tmp_path):
    plan = files(tmp_path)
    originals = {p: p.read_bytes() for p in tmp_path.iterdir()}
    out = tmp_path / "out"
    subprocess.run(
        [sys.executable, spec.origin, "--plan", str(plan), "--output-dir", str(out)],
        check=True,
        capture_output=True,
    )
    assert sorted(p.name for p in out.iterdir()) == [
        "completion-manifest.json",
        "metrics.json",
        "report.md",
        "rows.csv",
    ]
    completion = json.loads((out / "completion-manifest.json").read_text())
    assert completion["state"] == "complete" and not completion["inference_submitted"]
    for row in completion["artifacts"]:
        raw = (out / row["path"]).read_bytes()
        assert len(raw) == row["size_bytes"] and analysis.digest(raw) == row["sha256"]
    for path, raw in originals.items():
        assert path.read_bytes() == raw
    rows = list(csv.DictReader((out / "rows.csv").open()))
    assert [r["operation_id"] for r in rows] == ["op-0", "op-1"]
    assert rows[0]["model_elapsed_seconds"] == "2.951319835"
    assert "not reference likelihood" in (out / "report.md").read_text()
    before = {p: p.read_bytes() for p in out.iterdir()}
    analysis.publish(plan, out)
    assert {p: p.read_bytes() for p in out.iterdir()} == before


def test_conflict_preserved_and_no_completion_manifest(tmp_path):
    plan = files(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.md").write_bytes(b"Original failed report evidence")
    with pytest.raises(RuntimeError, match="differ"):
        analysis.publish(plan, out)
    assert (out / "report.md").read_bytes() == b"Original failed report evidence"
    assert not (out / "completion-manifest.json").exists()


def test_no_artifact_publication_on_invalid_request(tmp_path):
    plan = files(tmp_path)
    (tmp_path / "0-request.json").write_text('{"sequence":"WRONG"}')
    with pytest.raises(ValueError):
        analysis.publish(plan, tmp_path / "out")
    assert not (tmp_path / "out").exists()
