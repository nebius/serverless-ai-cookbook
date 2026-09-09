"""Local tests for the packed scientific-agent skills.

Validates frontmatter, tool references, and the example payloads against the
deployed adapter contracts (imported from the operator solutions source).
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


def load_server(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
FS2 = Path("/home/tux/nebius-solutions-library-inference/k8s-inference")
EVIDENCE = Path("/home/tux/fs2-skill-adaptation/evidence")

OLD_TOOLS = re.compile(r"`bionemo_[a-z_]+`|`protein_viewer`|`clawbio_model_fetch`")


def skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path}: missing frontmatter"
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, text


def test_frontmatter_and_names():
    for directory in skill_dirs():
        meta, _ = frontmatter(directory / "SKILL.md")
        assert meta.get("name") == directory.name, directory
        assert meta.get("description"), directory
        assert meta.get("license"), directory


def test_no_dead_tool_references():
    for directory in skill_dirs():
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        assert not OLD_TOOLS.search(text), f"{directory.name}: dead tool reference"


def test_tool_names_against_live_snapshot():
    tools = {tool["name"] for tool in json.loads((EVIDENCE / "mcp-tools.json").read_text())}
    # The retained evidence predates typed-MCP source 5de025fe. This core schema
    # tool was accepted in that release and is required by the replacement skill.
    tools.add("get_model_schema")
    for directory in skill_dirs():
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        for name in re.findall(r"`([a-z][a-z0-9_]{3,60})`", text):
            if name.startswith(("submit_", "infer_", "get_", "list_", "invoke_", "begin_", "put_", "finalize_", "download_", "read_", "acknowledge_", "cancel_")):
                assert name in tools, f"{directory.name}: unknown gateway tool {name}"


def _extract_example(path):
    """Return the flat typed-tool example from a skill file."""
    text = path.read_text(encoding="utf-8")
    block = re.search(r"```json\n(.*?)\n```", text, re.S)
    assert block, f"{path}: no json example"
    return json.loads(block.group(1))


def test_boltz2_example_matches_adapter():
    module = load_server(FS2 / "models" / "bionemo" / "boltz2" / "server.py", "boltz2_server")

    payload = _extract_example(SKILLS / "boltz2" / "SKILL.md")
    request = module.PredictRequest.model_validate(payload)
    assert request.polymers[0].molecule_type == "protein"
    with pytest.raises(ValidationError):
        module.PredictRequest.model_validate({**payload, "ligands": []})
    with pytest.raises(ValidationError):
        broken = json.loads(json.dumps(payload))
        broken["polymers"][0]["molecule_type"] = "dna"
        module.PredictRequest.model_validate(broken)


def test_openfold2_example_matches_adapter():
    module = load_server(FS2 / "models" / "structure" / "openfold2-upstream" / "server.py", "openfold2_server")

    payload = _extract_example(SKILLS / "openfold2" / "SKILL.md")
    assert module.parse_request(payload) == ("skill-smoke-openfold2", "MKTAYIAKQRQISFVK")
    with pytest.raises(ValueError):
        module.parse_request({**payload, "templates": "x"})
    with pytest.raises(ValueError):
        module.parse_request({**payload, "selected_models": [2]})


def test_diffdock_and_proteinmpnn_bounds():
    diffdock = _extract_example(SKILLS / "diffdock" / "SKILL.md")
    assert 1 <= diffdock["num_poses"] <= 4 and "ATOM" in diffdock["protein"]
    assert len(diffdock["ligand"]) <= 4096
    pmnn = _extract_example(SKILLS / "proteinmpnn" / "SKILL.md")
    assert 1 <= pmnn["num_seq_per_target"] <= 8 and "ATOM" in pmnn["input_pdb"]


def test_genmol_molmim_msa_examples():
    genmol = _extract_example(SKILLS / "genmol" / "SKILL.md")
    assert 1 <= genmol["num_molecules"] <= 16
    molmim = _extract_example(SKILLS / "molmim" / "SKILL.md")
    assert len(molmim["smi"]) <= 512
    msa = _extract_example(SKILLS / "msa-search" / "SKILL.md")
    assert 6 <= len(msa["sequence"]) <= 4096
    assert "pdb70" in msa["databases"][0] and "a3m" in msa["output_alignment_formats"]


def test_gateway_skill_covers_contract():
    text = (SKILLS / "scientific-gateway" / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "get_model_schema",
        "invoke_model",
        "submit_scientific_run",
        "model_input_validation",
        "get_operation_result",
        "get_scientific_result",
        "begin_scientific_artifact_upload",
        "acknowledge",
        "idempotency",
    ):
        assert required in text, required
    assert "intentionally generic" not in text
