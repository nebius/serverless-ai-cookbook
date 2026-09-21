"""The launch and observation wait contracts must not be interchangeable."""

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "execution_guidance", ROOT / "execution-mcp.py"
)
EXECUTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXECUTION)
TOOLS = {tool["name"]: tool for tool in EXECUTION.TOOLS}


def test_unchanged_launch_and_observation_schema_bounds():
    launch = TOOLS["execute_command"]["inputSchema"]["properties"]["wait_seconds"]
    observe = TOOLS["read_execution"]["inputSchema"]["properties"]["wait_seconds"]
    assert (launch["minimum"], launch["maximum"], launch["default"]) == (0, 10, 5)
    assert (observe["minimum"], observe["maximum"], observe["default"]) == (0, 30, 15)
    assert launch["maximum"] == EXECUTION.EXECUTE_WAIT_MAX_SECONDS
    assert launch["default"] == EXECUTION.EXECUTE_WAIT_DEFAULT_SECONDS
    assert "0 to 10" in launch["description"] and "default 5" in launch["description"]
    assert "0 to 10" in TOOLS["execute_command"]["description"]
    assert (
        "Do not copy read_execution wait_seconds=30"
        in TOOLS["execute_command"]["description"]
    )
    assert "--operation-wait-seconds" in TOOLS["execute_command"]["description"]
    assert "must never be moved" in TOOLS["execute_command"]["description"]
    with pytest.raises(ValidationError):
        Draft202012Validator(TOOLS["execute_command"]["inputSchema"]).validate(
            {"command": "true", "wait_seconds": 30}
        )
    Draft202012Validator(TOOLS["read_execution"]["inputSchema"]).validate(
        {"job_id": str(uuid.uuid4()), "wait_seconds": 30}
    )


@pytest.mark.parametrize("value", [11, 30, -1, True, "5", 2.5])
def test_invalid_launch_wait_is_rejected_before_any_job(tmp_path, monkeypatch, value):
    jobs = tmp_path / "jobs"
    monkeypatch.setattr(EXECUTION, "ROOT", jobs)
    monkeypatch.setattr(EXECUTION, "WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        EXECUTION.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("must not start a process"),
    )
    with pytest.raises(ValueError, match="0 to 10"):
        EXECUTION.execute({"command": "true", "wait_seconds": value})
    assert not jobs.exists()


@pytest.mark.parametrize(
    "extra,expected", [({}, 5), ({"wait_seconds": 0}, 0), ({"wait_seconds": 10}, 10)]
)
def test_launch_default_and_bound_match_actual_handler(
    tmp_path, monkeypatch, extra, expected
):
    monkeypatch.setattr(EXECUTION, "ROOT", tmp_path / "jobs")
    monkeypatch.setattr(EXECUTION, "WORKSPACE", str(tmp_path))
    monkeypatch.setattr(EXECUTION.subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.setattr(EXECUTION, "read_job", lambda args: args)
    observed = EXECUTION.execute({"command": "true", **extra})
    assert observed["wait_seconds"] == expected
    assert len(list((tmp_path / "jobs").glob("*/request.json"))) == 1


def test_pending_response_names_observation_not_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(EXECUTION, "ROOT", tmp_path)
    job = str(uuid.uuid4())
    directory = tmp_path / job
    directory.mkdir()
    (directory / "request.json").write_text(
        json.dumps({"command": "existing scientific work"})
    )
    response = EXECUTION.read_job({"job_id": job, "wait_seconds": 0})
    followup = response["next_observation"]
    assert followup["tool_name"] == "read_execution"
    assert followup["registered_tool_name"] == "read_execution_mcp_environment-execution"
    assert followup["arguments"] == {"job_id": job, "wait_seconds": 30, "offset": 0}
    Draft202012Validator(TOOLS[followup["tool_name"]]["inputSchema"]).validate(
        followup["arguments"]
    )
    assert "Call read_execution" in response["observation_guidance"]
    assert not (directory / "status.json").exists()


def test_actual_packaged_and_seeded_instructions_distinguish_tools():
    repository = ROOT.parents[1]
    instructions_path = (
        repository / "life-science/bionemo-librechat/scientific-agent-instructions.md"
    )
    instructions = instructions_path.read_text()
    assert (
        "`execute_command_mcp_environment-execution` launches work: `wait_seconds` is 0 to 10 seconds, default 5"
        in instructions
    )
    assert (
        "`read_execution_mcp_environment-execution` observes a saved job: `wait_seconds` is 0 to 30 seconds, default 15"
        in instructions
    )
    assert "Never pass `wait_seconds=30` to `execute_command_mcp_environment-execution`" in instructions
    assert "Never remove a CLI `--operation-wait-seconds`" in instructions
    assert "keep the exact shell command and idempotency key unchanged" in instructions
    assert (
        "COPY life-science/bionemo-librechat/scientific-agent-instructions.md /app/scientific-agent-instructions.md"
        in (ROOT / "Dockerfile").read_text()
    )
    seed = (ROOT / "seed-workbench.js").read_text()
    assert "'/app/scientific-agent-instructions.md'" in seed
    assert "execute_command_mcp_environment-execution" in seed
    assert "read_execution_mcp_environment-execution" in seed
    rendered = (ROOT / "render-config.mjs").read_text()
    assert "a command's --operation-wait-seconds" in rendered
