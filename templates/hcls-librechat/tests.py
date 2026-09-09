from pathlib import Path
import json
import os
import re
import subprocess

import pytest


ROOT = Path(__file__).parent
INSTRUCTIONS = ROOT.parents[1] / "life-science/bionemo-librechat/scientific-agent-instructions.md"


def render_config(tmp_path, **overrides):
    env = {key: value for key, value in os.environ.items()
           if key not in {"SCIENTIFIC_MODELS_API_KEY", "NEBIUS_API_KEY"}}
    env.update(SCIENTIFIC_AGENT_INSTRUCTIONS_PATH=str(INSTRUCTIONS),
               SCIENTIFIC_DISCOVER_CHAT_MODELS="false", **overrides)
    output = tmp_path / "librechat.yaml"
    result = subprocess.run(["node", str(ROOT / "render-config.mjs"), str(output)],
                            env=env, check=True, capture_output=True, text=True)
    return json.loads(output.read_text()), output.read_text() + result.stdout


def test_no_credentials_are_baked_into_the_image_context() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "Dockerfile", ROOT / "entrypoint.sh", ROOT / "render-config.mjs")
    )
    assert "Bearer <" not in combined
    assert "NEBIUS_API_KEY=" not in combined
    assert "AUTH_TOKEN=" not in combined


def test_serverless_and_librechat_auth_are_separated() -> None:
    deploy = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "--auth none" in deploy
    assert '--env-secret "SCIENTIFIC_MODELS_API_KEY=' in deploy
    assert '--env-secret "NEBIUS_API_KEY=' in deploy
    assert '--env-secret "TAVILY_API_KEY=' in deploy
    assert 'GROMACS' not in deploy


def test_footer_is_powered_by_nvidia() -> None:
    footer = (ROOT / "PoweredByFooter.tsx").read_text(encoding="utf-8")
    assert "Powered by" in footer
    assert "NVIDIA" in footer
    assert "const localize = useLocalize()" in footer
    # The upstream default attribution must not be rendered.
    assert "com_ui_latest_footer" not in footer
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "PoweredByFooter.tsx /app/client/src/components/Chat/Footer.tsx" in dockerfile


@pytest.mark.parametrize("shared_key", [False, True])
def test_rendered_gateway_authentication(tmp_path, shared_key) -> None:
    config, output = render_config(tmp_path, **({"SCIENTIFIC_MODELS_API_KEY": "synthetic-test-credential"} if shared_key else {}))
    assert set(config["mcpServers"]) == {"bionemo-models", "tavily"}
    gateway = config["mcpServers"]["bionemo-models"]
    assert gateway["type"] == "streamable-http"
    assert gateway["url"] == "${SCIENTIFIC_MODELS_MCP_URL}"
    assert gateway["requiresOAuth"] is False
    assert gateway["startup"] is shared_key
    assert "synthetic-test-credential" not in output
    if shared_key:
        assert gateway["headers"]["Authorization"] == "Bearer ${SCIENTIFIC_MODELS_API_KEY}"
        assert "customUserVars" not in gateway
    else:
        assert gateway["headers"]["Authorization"] == "Bearer {{SCIENTIFIC_MODELS_API_KEY}}"
        assert gateway["customUserVars"]["SCIENTIFIC_MODELS_API_KEY"]["sensitive"] is True
    assert config["interface"]["skills"]["use"] is True
    assert "skills" in config["endpoints"]["agents"]["capabilities"]
    assert "deferred_tools" in config["endpoints"]["agents"]["capabilities"]


def test_model_tools_are_deferred_without_changing_other_options() -> None:
    script = r"""
const assert = require('node:assert/strict');
const options = require(process.argv[1]);
const input = {tools: ['get_model_schema_mcp_bionemo-models', 'infer_openfold2_native_mcp_bionemo-models', 'tavily_search_mcp_tavily'],
  tool_options: {'infer_openfold2_native_mcp_bionemo-models': {describe_intent: true}}};
const result = options(input);
assert.equal(result['infer_openfold2_native_mcp_bionemo-models'].defer_loading, true);
assert.equal(result['infer_openfold2_native_mcp_bionemo-models'].describe_intent, true);
assert.equal(result['get_model_schema_mcp_bionemo-models'], undefined);
assert.equal(result['tavily_search_mcp_tavily'], undefined);
assert.equal(input.tool_options['infer_openfold2_native_mcp_bionemo-models'].defer_loading, undefined);
"""
    subprocess.run(['node', '-e', script, str(ROOT / 'scientific-tool-options.cjs')], check=True)


def test_tavily_missing_key_and_invalid_tool_are_explicit() -> None:
    env = {key: value for key, value in os.environ.items() if key != 'TAVILY_API_KEY'}
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'unknown'}},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'tavily_search', 'arguments': {'query': 'synthetic'}}},
    ]
    result = subprocess.run(['node', str(ROOT / 'tavily-mcp.mjs')], env=env,
        input='\n'.join(map(json.dumps, requests)) + '\n', capture_output=True, text=True, check=True)
    replies = {item['id']: item for item in map(json.loads, result.stdout.splitlines())}
    assert replies[1]['result']['tools'][0]['name'] == 'tavily_search'
    assert replies[2]['error']['code'] == -32602
    assert replies[3]['result']['isError'] is True
    assert 'not configured' in replies[3]['result']['content'][0]['text']


def test_saved_agents_receive_gateway_instructions_and_skills() -> None:
    # Execute the actual seeder against an in-memory Mongo stand-in. No network.
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const saved = [];
class MongoClient {
  async connect() {}
  db() { return { collection: (name) => ({
    async updateOne(filter, update) { if (name === 'agents') saved.push(update.$set); },
    async findOne() { return { _id: 'test-id' }; },
  }) }; }
  async close() { process.stdout.write(JSON.stringify(saved)); }
}
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  require: (name) => name === 'mongodb' ? { MongoClient, ObjectId: class {} } : require(name),
  process: { env: { SCIENTIFIC_AGENT_INSTRUCTIONS_PATH: process.argv[2] },
    stdout: { write() {} }, stderr: process.stderr },
});
"""
    instructions = ROOT.parents[1] / "life-science/bionemo-librechat/scientific-agent-instructions.md"
    result = subprocess.run(["node", "-e", script, str(ROOT / "seed-workbench.js"), str(instructions)],
                            check=True, capture_output=True, text=True)
    agents = json.loads(result.stdout)
    assert len(agents) == 6
    for agent in agents:
        assert agent["skills_enabled"] is True
        assert instructions.read_text().strip() in agent["instructions"]
        assert set(agent["mcpServerNames"]) == {"bionemo-models", "tavily"}
        assert "tavily_search_mcp_tavily" in agent["tools"]


def test_chat_choices_keep_scientific_capabilities_and_exclude_native_models(tmp_path) -> None:
    config, _ = render_config(tmp_path)
    specs = config["modelSpecs"]["list"]
    assert {item["group"] for item in specs} == {"Nebius Token Factory", "OpenAI", "Claude"}
    assert len([item for item in specs if item["group"] == "Nebius Token Factory"]) > 2
    assert len([item for item in specs if item["default"]]) == 1
    assert len({item["name"] for item in specs}) == len(specs)
    for item in specs:
        assert item["skills"] is True
        assert item["mcpServers"] == ["bionemo-models", "tavily"]
        assert INSTRUCTIONS.read_text().strip() in item["preset"]["promptPrefix"]
        assert item["preset"]["model"] not in {"evo2-40b", "boltz2", "openfold2", "sdxl", "nv-segment-ct"}
        assert "agent_id" not in item["preset"]
    assert config["interface"]["modelSelect"] is False  # curated specs remain selectable
    assert [item["name"] for item in config["endpoints"]["custom"]] == ["Nebius Token Factory"]


def test_model_grouped_tutorials_are_seeded() -> None:
    seeder = (ROOT / "seed-workbench.js").read_text(encoding="utf-8")
    assert "agent_nebius_scientific_ai" in seeder
    assert "agent_protein_structure" in seeder
    assert "agent_molecular_design" in seeder
    assert "agent_biomedical_imaging" in seeder
    assert "agent_genomics_aging" in seeder
    assert "agent_audio_transcription_tutorial" in seeder
    assert "scientificModelsServerName" in seeder
    assert "boltz2_predict_native" in seeder
    assert "segment_ct_native" in seeder
    assert "Do not give a diagnosis" in seeder


def test_default_model_and_visible_workbench(tmp_path) -> None:
    config, _ = render_config(tmp_path)
    brand_client = (ROOT / "brand-client.mjs").read_text(encoding="utf-8")
    default = next(item for item in config["modelSpecs"]["list"] if item["default"])
    assert default["preset"]["model"] == "zai-org/GLM-5.3-Flash"
    assert "nebius-scientific-workbench" in brand_client
    for title in (
        "Find the right model", "Fold a protein", "Explore molecular design",
        "Study sequences & aging", "Investigate biomedical images", "Research the literature",
    ):
        assert title in (ROOT / "ScientificLanding.tsx").read_text(encoding="utf-8")


def test_client_branding_is_baked_into_the_wrapper() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    brand_client = (ROOT / "brand-client.mjs").read_text(encoding="utf-8")
    assert "nebius-logo.svg" in dockerfile
    assert "/app/client/dist/assets/logo.svg" in dockerfile
    assert 'APP_TITLE="Nebius Scientific AI Agent"' in dockerfile
    assert "Nebius Scientific AI Agent" in brand_client


def test_product_does_not_use_tenant_branding() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix in {".js", ".mjs", ".py", ".sh", ".md", ".svg"}
    )
    assert ("ko" + "pra") not in combined.lower()
