"""Exact public-schema regression plus generic no-network native selection.

The captured catalog contains no caller records or payloads. The synthetic
artifact below preserves the real transfer request's field types, not its
identity or content. Installed tests import the actual runtime via study.
"""

import asyncio
import copy
import importlib.util
import json
import types
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

import scientific_study as study

SPEC = importlib.util.spec_from_file_location(
    "native_contract_selection_client", Path(study.__file__).with_name("invoke-native.py")
)
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)
PUBLIC_FIXTURE = Path(__file__).with_name("test-fixtures") / "cosmos3-native-public-contracts-20260919.json"


@pytest.fixture
def catalog():
    return json.loads(PUBLIC_FIXTURE.read_bytes())


@pytest.fixture
def transfer():
    return {
        "prompt": "Recorded robot scene with cooler lighting.",
        "negative_prompt": "Geometry distortions.",
        "input_reference": {
            "artifact_id": "00000000-0000-4000-8000-000000000001",
            "sha256": "a" * 64, "size_bytes": 520934,
            "media_type": "video/mp4", "compression": "none",
        },
        "controls": [{"control_type": "edge", "control_weight": 1.0, "edge_threshold": "medium"}],
        "fps": 25, "guidance_scale": 7, "num_frames": 64,
        "num_inference_steps": 35, "seed": 20260919, "size": "640x480",
        "idempotency_key": "synthetic-selection-only", "wait_seconds": 0,
    }


def test_retained_public_catalog_reproduces_wrong_first_contract(catalog, transfer):
    assert len(catalog["contracts"]) == 6
    first = catalog["contracts"][0]
    assert first["tool_name"] == "cosmos3_nano_generate_media_native"
    errors = list(Draft202012Validator(first["input_schema"]).iter_errors(transfer))
    assert any(error.validator == "required" and "mode" in error.message for error in errors)
    dedicated = next(row for row in catalog["contracts"] if row["tool_name"] == "cosmos3_nano_transfer_video")
    Draft202012Validator(dedicated["input_schema"]).validate(transfer)
    assert "mode" not in transfer


@pytest.mark.parametrize("explicit", [None, "cosmos3_nano_transfer_video"])
def test_exact_transfer_shape_selects_dedicated_without_inventing_mode(catalog, transfer, explicit):
    before = copy.deepcopy((catalog, transfer))
    selected = client.select_contract(catalog, transfer, tool_name=explicit)
    assert selected["tool_name"] == "cosmos3_nano_transfer_video"
    assert (catalog, transfer) == before


def test_generic_explicit_contract_still_requires_mode(catalog, transfer):
    with pytest.raises((ValueError, ValidationError)):
        client.select_contract(catalog, transfer, tool_name="cosmos3_nano_generate_media_native")
    transfer["mode"] = "transfer-video"
    selected = client.select_contract(catalog, transfer, tool_name="cosmos3_nano_generate_media_native")
    assert selected["tool_name"] == "cosmos3_nano_generate_media_native"


def contract(name, required, protocol="native"):
    return {"tool_name": name, "protocol": protocol, "input_schema": {
        "type": "object", "properties": {key: {"type": "integer"} for key in required},
        "required": list(required), "additionalProperties": False,
    }}


@pytest.mark.parametrize("reverse", [False, True])
def test_selection_is_generic_and_not_catalog_order(reverse):
    contracts = [contract("model_alpha", ["x"]), contract("model_beta", ["y"])]
    if reverse:
        contracts.reverse()
    assert client.select_contract({"contracts": contracts}, {"y": 3})["tool_name"] == "model_beta"


def test_multiple_matching_native_contracts_are_ambiguous():
    schema = {"contracts": [contract("alpha", ["x"]), contract("beta", ["x"])]}
    with pytest.raises(ValueError):
        client.select_contract(schema, {"x": 3})
    assert client.select_contract(schema, {"x": 3}, tool_name="beta")["tool_name"] == "beta"


def test_exact_name_does_not_fall_back_to_another_matching_tool():
    schema = {"contracts": [contract("alpha", ["x"]), contract("beta", ["y"])]}
    with pytest.raises((ValueError, ValidationError)):
        client.select_contract(schema, {"x": 3}, tool_name="beta")
    with pytest.raises(ValueError):
        client.select_contract(schema, {"x": 3}, tool_name="missing")


def test_other_protocol_is_not_a_native_candidate():
    schema = {"contracts": [contract("not_native", ["x"], "scientific-batch"), contract("native", ["y"])]}
    with pytest.raises((ValueError, ValidationError)):
        client.select_contract(schema, {"x": 3})
    with pytest.raises(ValueError):
        client.select_contract(schema, {"x": 3}, tool_name="not_native")


def test_explicit_openai_chat_contract_is_selected_only_when_requested():
    schema = {"contracts": [
        contract("native_tool", ["x"]),
        contract("analyze_image_openai_chat", ["messages"], "openai-chat"),
    ]}
    arguments = {"messages": 3}
    with pytest.raises((ValueError, ValidationError)):
        client.select_contract(schema, arguments, tool_name="analyze_image_openai_chat")
    selected = client.select_contract(
        schema, arguments, tool_name="analyze_image_openai_chat", protocol="openai-chat"
    )
    assert selected["protocol"] == "openai-chat"
    assert selected["tool_name"] == "analyze_image_openai_chat"


@pytest.mark.parametrize("contracts", [[], [contract("invalid", ["x"])]])
def test_absent_or_nonmatching_contracts_refuse(contracts):
    with pytest.raises((ValueError, ValidationError)):
        client.select_contract({"contracts": contracts}, {"unknown": 3})


def test_duplicate_explicit_contract_name_is_not_silently_first():
    schema = {"contracts": [contract("duplicate", ["x"]), contract("duplicate", ["x"])]}
    with pytest.raises(ValueError):
        client.select_contract(schema, {"x": 3}, tool_name="duplicate")


@pytest.mark.parametrize("ambiguous", [False, True])
def test_invalid_or_ambiguous_run_never_submits_model(tmp_path, monkeypatch, ambiguous):
    """Exercise real run(), not just selector; discovery is a fake saved catalog."""
    monkeypatch.setenv("SCIENTIFIC_MODELS_MCP_URL", "https://no-network.invalid/mcp")
    monkeypatch.setenv("SCIENTIFIC_MODELS_API_KEY", "synthetic-contract-test")
    source = tmp_path / "input.json"
    source.write_text('{"x":3}')
    contracts = [contract("first", ["x"]), contract("second", ["x"])] if ambiguous else [contract("needs_y", ["y"])]
    # The actual wrapper supplies these lifecycle fields before validation.
    for item in contracts:
        item["input_schema"]["properties"].update({"idempotency_key": {"type": "string"}, "wait_seconds": {"type": "number"}})
    calls = []

    class Response:
        def model_dump(self, **kwargs):
            return {"structuredContent": {"contracts": contracts}}

    class MCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def call_tool(self, name, arguments):
            calls.append(name)
            assert name == "get_model_schema", "Selection failure must not reach model admission."
            return Response()

    class HTTP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(client.httpx2, "AsyncClient", lambda **kwargs: HTTP())
    monkeypatch.setattr(client, "streamable_http_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "Client", lambda transport: MCP())
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / "run", model="generic-model",
        tool=None, idempotency_key="offline-only", wait_seconds=10, recover_only=False)
    with pytest.raises((ValueError, ValidationError)):
        asyncio.run(client.run(args))
    assert calls == ["get_model_schema"]
    receipt = json.loads((args.output_dir / "receipt.json").read_bytes())
    assert not receipt.get("operation_id") and receipt["state"] != "submitting"
    assert not (args.output_dir / "submission.json").exists()


def test_explicit_transfer_run_and_sticky_replay_identity(tmp_path, monkeypatch, catalog, transfer):
    """Fake successful transport proves actual dispatch/replay, not model quality."""
    monkeypatch.setenv("SCIENTIFIC_MODELS_MCP_URL", "https://no-network.invalid/mcp")
    monkeypatch.setenv("SCIENTIFIC_MODELS_API_KEY", "synthetic-contract-test")
    payload = {key: value for key, value in transfer.items() if key not in {"wait_seconds", "idempotency_key"}}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload))
    calls = []
    dedicated = "cosmos3_nano_transfer_video"

    class Response:
        def __init__(self, value):
            self.value = value

        def model_dump(self, **kwargs):
            return {"structuredContent": self.value}

    class MCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def call_tool(self, name, arguments):
            calls.append((name, copy.deepcopy(arguments)))
            if name == "get_model_schema":
                assert arguments == {"model_id": "cosmos3-nano", "protocol": "native", "tool_name": dedicated}
                return Response(catalog)
            if name == dedicated:
                assert arguments == transfer and "mode" not in arguments
                return Response({"id": "synthetic-operation", "status": "running"})
            if name == "get_operation":
                return Response({"id": "synthetic-operation", "status": "succeeded", "result_available": True})
            if name == "get_operation_result":
                return Response({"operation": {"id": "synthetic-operation"}, "result": {"synthetic_transport_only": True}})
            pytest.fail("Unexpected generic dispatch or additional admission: " + name)

    class HTTP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(client.httpx2, "AsyncClient", lambda **kwargs: HTTP())
    monkeypatch.setattr(client, "streamable_http_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "Client", lambda transport: MCP())
    args = types.SimpleNamespace(input=source, output_dir=tmp_path / "run", model="cosmos3-nano",
        tool=dedicated, idempotency_key=transfer["idempotency_key"], wait_seconds=10, recover_only=False)
    completed = asyncio.run(client.run(args))
    assert completed["state"] == "succeeded" and completed["tool"] == dedicated
    assert completed["identity"]["tool_name"] == dedicated
    assert [name for name, _ in calls] == ["get_model_schema", dedicated, "get_operation", "get_operation_result"]
    saved = (args.output_dir / "receipt.json").read_bytes()

    def forbidden_network(**kwargs):
        pytest.fail("A successful replay or mismatched identity must not open network transport.")

    monkeypatch.setattr(client.httpx2, "AsyncClient", forbidden_network)
    assert asyncio.run(client.run(args)) == completed
    assert (args.output_dir / "receipt.json").read_bytes() == saved
    args.tool = "cosmos3_nano_generate_media_native"
    with pytest.raises(ValueError, match="different inputs"):
        asyncio.run(client.run(args))
    assert (args.output_dir / "receipt.json").read_bytes() == saved


def test_openai_chat_run_binds_protocol_in_schema_query_and_receipt(tmp_path, monkeypatch):
    """Artifact references stay structured while the named chat tool owns admission."""
    monkeypatch.setenv("SCIENTIFIC_MODELS_MCP_URL", "https://no-network.invalid/mcp")
    monkeypatch.setenv("SCIENTIFIC_MODELS_API_KEY", "synthetic-contract-test")
    artifact = {
        "artifact_id": "00000000-0000-4000-8000-000000000001",
        "sha256": "a" * 64,
        "size_bytes": 42,
        "media_type": "image/png",
        "compression": "none",
    }
    payload = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "Describe the research image."},
        {"type": "image_url", "image_url": {"url": artifact}},
    ]}], "max_completion_tokens": 64}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload))
    tool = "analyze_image_openai_chat"
    schema = {
        "type": "object",
        "required": ["messages", "idempotency_key", "wait_seconds"],
        "properties": {
            "messages": {"type": "array"},
            "max_completion_tokens": {"type": "integer"},
            "idempotency_key": {"type": "string"},
            "wait_seconds": {"type": "number"},
        },
        "additionalProperties": False,
    }
    calls = []

    class Response:
        def __init__(self, value): self.value = value
        def model_dump(self, **kwargs): return {"structuredContent": self.value}

    class MCP:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def call_tool(self, name, arguments):
            calls.append((name, copy.deepcopy(arguments)))
            if name == "get_model_schema":
                assert arguments == {"model_id": "nv-reason-cxr-3b", "protocol": "openai-chat", "tool_name": tool}
                return Response({"contracts": [{"protocol": "openai-chat", "tool_name": tool, "input_schema": schema}]})
            if name == tool:
                assert arguments == payload | {"idempotency_key": "cxr-file-backed", "wait_seconds": 0}
                assert isinstance(arguments["messages"][0]["content"][1]["image_url"]["url"], dict)
                return Response({"id": "cxr-operation", "status": "running"})
            if name == "get_operation":
                return Response({"id": "cxr-operation", "status": "succeeded", "result_available": True})
            if name == "get_operation_result":
                return Response({"operation": {"id": "cxr-operation"}, "result": {"choices": []}})
            pytest.fail("Unexpected tool: " + name)

    class HTTP:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None

    monkeypatch.setattr(client.httpx2, "AsyncClient", lambda **kwargs: HTTP())
    monkeypatch.setattr(client, "streamable_http_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "Client", lambda transport: MCP())
    args = types.SimpleNamespace(
        input=source, output_dir=tmp_path / "run", model="nv-reason-cxr-3b",
        protocol="openai-chat", tool=tool, idempotency_key="cxr-file-backed",
        wait_seconds=10, recover_only=False,
    )
    completed = asyncio.run(client.run(args))
    assert completed["state"] == "succeeded"
    assert completed["identity"]["protocol"] == "openai-chat"
    assert [name for name, _ in calls] == ["get_model_schema", tool, "get_operation", "get_operation_result"]
