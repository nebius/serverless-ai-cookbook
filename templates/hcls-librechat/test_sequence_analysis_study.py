"""Offline real-worker/CLI regression with synthetic saved Evo2 envelopes.

No model/provider calls: preparation writes the hosted response shape, the typed
phase resolves future FILE references, and the real report helper publishes it.
Import the runtime module normally so installed-image tests exercise /opt rather
than substituting source helpers from the directory containing this test.
"""

import asyncio
import csv
import hashlib
import json
from pathlib import Path

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow, known_output_files


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def test_typed_evo2_future_files_reach_real_report_and_final_publication(
    tmp_path, monkeypatch
):
    for name, value in {
        "SCIENTIFIC_WORKSPACE": str(tmp_path),
        "SCIENTIFIC_MODELS_MCP_URL": "https://platform.test/mcp",
        "SCIENTIFIC_MODELS_API_KEY": "offline-sequence-test-only",
        "SEED_DEFAULT_USER_EMAIL": "sequence-analysis@example.test",
        "SCIENTIFIC_STUDY_OWNER_MODE": "first-instance",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        study,
        "workflow_module",
        lambda: pytest.fail("Retained-result analysis must not initialize inference"),
    )
    reference = tmp_path / "reference.fa"
    reference.write_bytes(b">synthetic-reference\nACGTGCAA\n")
    original_reference = reference.read_bytes()
    steps, cases, expected = [], [], []
    for seed, suffix, elapsed in [(1, "GCGT", 2951.319835), (7, "AAAA", 1234.5)]:
        identifier = f"seed-{seed}"
        request = {
            "sequence": "ACGT",
            "num_tokens": 4,
            "random_seed": seed,
            "temperature": 0.7,
            "top_k": 4,
            "top_p": 0.95,
        }
        result = {
            "sequence": suffix,
            "elapsed_ms": elapsed,
            "elapsed_ms_per_token": [1.0, 2.0, 3.0, 4.0],
            "sampled_probs": None,
            "logits": None,
        }
        # The hosted operation envelope, not result.json, supplies the ID.
        operation = {
            "structuredContent": {
                "id": f"00000000-0000-4000-8000-{seed:012d}",
                "model_id": "evo2-40b",
                "status": "succeeded",
                "model_revision": "synthetic-recorded-revision",
                "accepted_at": "2026-09-19T18:00:00Z",
                "started_at": "2026-09-19T18:00:03Z",
                "completed_at": "2026-09-19T18:00:07Z",
                "runtime": {"pod_uid": f"synthetic-observed-pod-{seed}"},
            }
        }
        case = {"id": identifier, "start_zero_based": 0}
        for name, payload, argument in [
            ("request", request, "input_file"),
            ("result", result, "result_file"),
            ("operation", operation, "operation_file"),
        ]:
            step_id, filename = f"{identifier}-{name}", f"{name}.json"
            steps.append(
                {
                    "id": step_id,
                    "kind": "preparation",
                    "method": "write-json",
                    "arguments": {"filename": filename, "value": payload},
                }
            )
            case[argument] = {"step": step_id, "file": filename}
        cases.append(case)
        expected.append((request, result, operation))
    measure = {
        "id": "measure",
        "kind": "analysis",
        "method": "evo2-continuation",
        "arguments": {
            "reference_file": str(reference),
            "reference_id": "synthetic-reference",
            "cases": cases,
        },
    }
    steps.extend(
        [
            measure,
            {
                "id": "report",
                "kind": "analysis",
                "method": "report",
                "arguments": {
                    "title": "Recorded continuation measurements, not likelihood",
                    "sections": [
                        {
                            "title": "Measured generation",
                            "format": "markdown",
                            "file": {"step": "measure", "file": "report.md"},
                        },
                        {
                            "title": "Exact measured rows",
                            "format": "csv",
                            "file": {"step": "measure", "file": "rows.csv"},
                        },
                    ],
                },
            },
        ]
    )
    value = {
        "schema": study.SCHEMA,
        "title": "Synthetic saved Evo2 continuation study",
        "steps": steps,
        "deliverables": [
            {"name": name, "role": role, "source": {"step": phase, "file": file}}
            for name, role, phase, file in [
                ("report.md", "report", "report", "report.md"),
                ("metrics.json", "metrics", "measure", "metrics.json"),
                ("rows.csv", "data", "measure", "rows.csv"),
                (
                    "measurement-manifest.json",
                    "provenance",
                    "measure",
                    "completion-manifest.json",
                ),
                (
                    "report-manifest.json",
                    "provenance",
                    "report",
                    "completion-manifest.json",
                ),
            ]
        ],
    }
    commands = []
    local_command = study.local_command

    def record_actual_command(method, arguments, scratch):
        command = local_command(method, arguments, scratch)
        commands.append((method, command))
        return command

    monkeypatch.setattr(study, "local_command", record_actual_command)
    accepted = study.submit(value, tmp_path / "study")
    assert study.submit(value, tmp_path / "study")["id"] == accepted["id"]
    for _ in range(len(steps) + 1):
        completed = asyncio.run(study.advance(accepted["id"]))
        assert completed["state"] not in {"failed", "needs_attention"}, completed
    assert completed["state"] == "completed", completed
    assert completed["completed_steps"] == [step["id"] for step in steps]
    assert [method for method, _ in commands] == ["evo2-continuation", "report"]
    runtime_directory = Path(study.__file__).parent
    assert commands[0][1][1] == str(runtime_directory / "sequence-analysis.py")
    assert commands[0][1][2::2] == ["--plan", "--output-dir"]
    assert commands[1][1][1] == str(runtime_directory / "report-assembly.py")

    outputs = completed["steps"]["measure"]["files"]
    contract = describe_workflow(["evo2-continuation"])["phases"]["evo2-continuation"]
    assert set(contract["always_on_success"]) <= set(outputs)
    assert set(outputs) == known_output_files(measure)
    metrics = json.loads(Path(outputs["metrics.json"]["path"]).read_bytes())
    resolved = json.loads(Path(outputs["helper-input.json"]["path"]).read_bytes())
    assert metrics["case_count"] == 2 and metrics["pair_count"] == 1
    assert metrics["pairs"][0]["hamming_distance"] == 4
    assert metrics["inference_submitted"] is False
    assert metrics["scientific_claims_validated"] is False
    assert metrics["plan_sha256"] == digest(
        Path(outputs["helper-input.json"]["path"]).read_bytes()
    )
    sources = {row["role"]: row for row in metrics["sources"]}
    for index, (request, result, operation) in enumerate(expected):
        case, measured = cases[index], metrics["cases"][index]
        assert (
            measured["request"] == request
            and measured["new_sequence"] == result["sequence"]
        )
        assert measured["sequence_mode"] == "suffix"
        assert measured["sampled_probs"] is None and measured["logits"] is None
        assert measured["operation"]["id"] == operation["structuredContent"]["id"]
        assert (
            measured["operation"]["runtime"]
            == operation["structuredContent"]["runtime"]
        )
        assert measured["operation"]["accepted_to_completed_seconds"] == 7
        for argument, role in [
            ("input_file", "request"),
            ("result_file", "result"),
            ("operation_file", "operation"),
        ]:
            ref = case[argument]
            prepared = completed["steps"][ref["step"]]["files"][ref["file"]]
            assert resolved["cases"][index][argument] == prepared["path"]
            assert sources[case["id"] + ":" + role]["sha256"] == prepared["sha256"]
    assert metrics["cases"][0]["suffix"]["gc_fraction_all_positions"] == 0.75
    assert metrics["cases"][1]["suffix"]["gc_fraction_all_positions"] == 0
    assert metrics["cases"][0]["model_elapsed_seconds"] == "2.951319835"
    assert metrics["cases"][1]["model_elapsed_seconds"] == "1.2345"
    with Path(outputs["rows.csv"]["path"]).open() as stream:
        csv_rows = list(csv.DictReader(stream))
    assert [row["operation_id"] for row in csv_rows] == [
        item[2]["structuredContent"]["id"] for item in expected
    ]

    report_outputs = completed["steps"]["report"]["files"]
    report = Path(report_outputs["report.md"]["path"]).read_text()
    assert "Cases measured: 2; explicitly comparable pairs: 1." in report
    assert "not reference likelihood" in report and "2.951319835" in report
    assert (
        Path(report_outputs["sources/000.md"]["path"]).read_bytes()
        == Path(outputs["report.md"]["path"]).read_bytes()
    )
    assert (
        Path(report_outputs["sources/001.csv"]["path"]).read_bytes()
        == Path(outputs["rows.csv"]["path"]).read_bytes()
    )
    for files in [outputs, report_outputs]:
        completion = json.loads(
            Path(files["completion-manifest.json"]["path"]).read_bytes()
        )
        assert (
            completion["state"] == "complete" and not completion["inference_submitted"]
        )
        for artifact in completion["artifacts"]:
            raw = Path(files[artifact["path"]]["path"]).read_bytes()
            assert (
                len(raw) == artifact["size_bytes"] and digest(raw) == artifact["sha256"]
            )
    publication = json.loads(Path(completed["manifest"]["path"]).read_bytes())
    assert publication["operations"] == []  # Reused envelopes are not new calls.
    assert publication["scientific_validity_claim"] is False
    assert len(publication["artifacts"]) == 5
    for artifact in publication["artifacts"]:
        raw = Path(artifact["path"]).read_bytes()
        assert len(raw) == artifact["size_bytes"] and digest(raw) == artifact["sha256"]
    assert reference.read_bytes() == original_reference
    before = Path(completed["manifest"]["path"]).read_bytes()
    assert asyncio.run(study.advance(accepted["id"]))["state"] == "completed"
    assert Path(completed["manifest"]["path"]).read_bytes() == before
    assert len(commands) == 2
