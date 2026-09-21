from pathlib import Path
import json
import os
import re
import subprocess

import pytest


ROOT = Path(__file__).parent
INSTRUCTIONS = ROOT.parents[1] / "life-science/bionemo-librechat/scientific-agent-instructions.md"


def render_config(tmp_path, catalog=None, **overrides):
    env = {key: value for key, value in os.environ.items()
           if key not in {"SCIENTIFIC_MODELS_API_KEY", "NEBIUS_API_KEY"}}
    env.update(SCIENTIFIC_AGENT_INSTRUCTIONS_PATH=str(INSTRUCTIONS),
               SCIENTIFIC_DISCOVER_CHAT_MODELS="false")
    env.update(overrides)
    output = tmp_path / "librechat.yaml"
    command = ["node", str(ROOT / "render-config.mjs"), str(output)]
    if catalog is not None:
        env.update(NEBIUS_API_KEY='synthetic-provider-test-key', SCIENTIFIC_DISCOVER_CHAT_MODELS='true')
        code = 'globalThis.fetch = async () => ({ok: true, json: async () => (' + json.dumps(catalog) + ')});' \
            + 'process.argv[2] = process.argv[1]; await import(' + json.dumps((ROOT / 'render-config.mjs').as_uri()) + ');'
        command = ['node', '--input-type=module', '-e', code, str(output)]
    result = subprocess.run(command,
                            env=env, check=True, capture_output=True, text=True)
    return json.loads(output.read_text()), output.read_text() + result.stdout


def test_explicit_chat_model_is_admitted_only_after_live_catalog_verification(tmp_path):
    model = 'provider/new-planning-model'
    config, _ = render_config(tmp_path, catalog={'data': [{'id': model}]}, SCIENTIFIC_CHAT_MODEL=model)
    provider = next(item for item in config['endpoints']['custom'] if item['name'] == 'Nebius Token Factory')
    assert model in provider['models']['default']
    assert provider['models']['default'] == [model]
    assert config['endpoints']['agents']['recursionLimit'] == 50
    assert config['endpoints']['agents']['maxRecursionLimit'] == 50
    assert config['endpoints']['agents']['maxRecursionLimit'] == 50


@pytest.mark.parametrize('catalog', [None, {'data': [{'id': 'Qwen/Qwen3-235B-A22B-Instruct-2507'}]}])
def test_unverified_explicit_chat_model_never_silently_falls_back(tmp_path, catalog):
    with pytest.raises(subprocess.CalledProcessError):
        render_config(tmp_path, catalog=catalog, SCIENTIFIC_CHAT_MODEL='provider/unavailable-model')


def test_previously_curated_model_is_not_accepted_when_live_catalog_removes_it(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        render_config(tmp_path, catalog={'data': [{'id': 'provider/new-model'}]},
                      SCIENTIFIC_CHAT_MODEL='Qwen/Qwen3-235B-A22B-Instruct-2507')


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


@pytest.mark.parametrize("override", [None, "example.invalid/customer:qualified-runtime"])
def test_deployment_selects_tested_skills_image_and_preserves_explicit_override(override):
    env = {
        "PATH": os.environ["PATH"],
        "NEBIUS_PROJECT_ID": "project-test",
        "NEBIUS_SUBNET_ID": "subnet-test",
        "SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR": "test-gateway-selector",
        "TOKEN_FACTORY_SECRET_SELECTOR": "test-provider-selector",
        "TAVILY_SECRET_SELECTOR": "test-search-selector",
        "SCIENTIFIC_STUDY_OWNER_MODE": "first-instance",
        "SEED_DEFAULT_USER_EMAIL": "test@example.invalid",
        "TEAM_BUCKET_NAME": "test-bucket",
        "TEAM_ID": "test-tenant",
        "S3_CREDENTIAL_SECRET_SELECTOR": "test-storage-selector",
        "USER_PASSWORD_SECRET_SELECTOR": "test-password-selector",
    }
    if override:
        env["IMAGE"] = override
    # Export a shell mock: never call the real provider or create infrastructure.
    result = subprocess.run(
        ["bash", "-c", 'nebius() { printf "%s\\n" "$@"; }; export -f nebius; bash "$1"',
         "deployment-test", str(ROOT / "scripts/deploy.sh")],
        env=env, check=True, capture_output=True, text=True,
    )
    args = result.stdout.splitlines()
    assert args[:3] == ["ai", "endpoint", "create"]
    assert args[args.index("--image") + 1] == (
        override or "cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:skills-20260920-v1"
    )


def test_personal_installation_can_use_public_chat_without_event_capacity(tmp_path):
    config, _ = render_config(tmp_path, SCIENTIFIC_DEDICATED_CHAT_ENABLED="false")
    defaults = [item for item in config["modelSpecs"]["list"] if item["default"]]
    assert len(defaults) == 1
    assert defaults[0]["preset"] == {"endpoint": "agents", "agent_id": "agent_nebius_scientific_ai"}
    assert not any("Dedicated" in item["group"] for item in config["modelSpecs"]["list"])
    assert not any("Dedicated" in item["name"] for item in config["endpoints"]["custom"])
    assert "Nebius Token Factory Dedicated" not in config["endpoints"]["agents"]["allowedProviders"]


def test_personal_serverless_mount_keeps_database_off_object_storage():
    deploy = (ROOT / "scripts/deploy.sh").read_text()
    assert 'S3_AWS_PROFILE="${S3_AWS_PROFILE:-default}"' in deploy
    assert 's3://${TEAM_BUCKET_NAME}:/workspace:rw:${S3_AWS_PROFILE}@${S3_CREDENTIAL_SECRET_SELECTOR}' in deploy
    assert '--env "ALLOW_REGISTRATION=false"' in deploy
    assert '--env-secret "SEED_DEFAULT_USER_PASSWORD=$USER_PASSWORD_SECRET_SELECTOR"' in deploy
    assert ':/data' not in deploy


def test_footer_is_powered_by_nvidia() -> None:
    footer = (ROOT / "PoweredByFooter.tsx").read_text(encoding="utf-8")
    assert "Powered by" in footer
    assert "NVIDIA" in footer
    assert 'alt="Nebius"' in footer
    assert "fill: '#000000'" in footer
    assert "fill: 'rgb(118,185,0)'" in footer
    assert "const localize = useLocalize()" in footer
    # The upstream default attribution must not be rendered.
    assert "com_ui_latest_footer" not in footer
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "PoweredByFooter.tsx /app/client/src/components/Chat/Footer.tsx" in dockerfile


@pytest.mark.parametrize("shared_key", [False, True])
def test_rendered_gateway_authentication(tmp_path, shared_key) -> None:
    config, output = render_config(tmp_path, **({"SCIENTIFIC_MODELS_API_KEY": "synthetic-test-credential"} if shared_key else {}))
    assert set(config["mcpServers"]) == {"scientific-ai-apps", "tavily", "structure-viewer", "environment-execution", "scientific-demos"}
    demos = config["mcpServers"]["scientific-demos"]
    assert demos["startup"] is False
    assert demos["env"]["SCIENTIFIC_MODELS_API_KEY"] == "{{SCIENTIFIC_MODELS_API_KEY}}"
    assert demos["env"]["LIBRECHAT_USER_ID"] == "{{LIBRECHAT_USER_ID}}"
    assert demos["customUserVars"]["SCIENTIFIC_MODELS_API_KEY"]["sensitive"] is True
    gateway = config["mcpServers"]["scientific-ai-apps"]
    assert gateway["title"] == "Scientific AI Apps"
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
const input = {tools: ['get_model_schema_mcp_scientific-ai-apps', 'infer_openfold2_native_mcp_scientific-ai-apps', 'tavily_search_mcp_tavily'],
  tool_options: {'infer_openfold2_native_mcp_scientific-ai-apps': {describe_intent: true}}};
const result = options(input);
assert.equal(result['infer_openfold2_native_mcp_scientific-ai-apps'].defer_loading, true);
assert.equal(result['infer_openfold2_native_mcp_scientific-ai-apps'].describe_intent, true);
assert.equal(result['get_model_schema_mcp_scientific-ai-apps'], undefined);
assert.equal(result['list_models_mcp_scientific-ai-apps'].defer_loading, true);
assert.equal(result['get_operation_result_mcp_scientific-ai-apps'].defer_loading, true);
assert.equal(result['tavily_search_mcp_tavily'].defer_loading, true);
assert.equal(input.tool_options['infer_openfold2_native_mcp_scientific-ai-apps'].defer_loading, undefined);
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
  require: (name) => name === 'mongodb' ? { MongoClient, ObjectId: class {} }
    : name === 'librechat-data-provider' ? { Constants: { mcp_all: 'mcp_all' } } : require(name),
  process: { env: { SCIENTIFIC_AGENT_INSTRUCTIONS_PATH: process.argv[2] },
    stdout: { write() {} }, stderr: process.stderr },
});
"""
    instructions = ROOT.parents[1] / "life-science/bionemo-librechat/scientific-agent-instructions.md"
    result = subprocess.run(["node", "-e", script, str(ROOT / "seed-workbench.js"), str(instructions)],
                            check=True, capture_output=True, text=True)
    agents = json.loads(result.stdout)
    assert len(agents) == 6
    # Tool existence and service tests do not prove the customer agent can see
    # its schema. Compare the actual seeded general-agent allowlist with the
    # authoritative MCP definitions so newly added workflow tools cannot be
    # silently omitted again.
    definitions = subprocess.run([
        'node', '-e', 'process.stdout.write(JSON.stringify(require(process.argv[1]).tools.map(t => t.name)))',
        str(ROOT / 'demos/mcp.cjs'),
    ], check=True, capture_output=True, text=True)
    demo_tools = {name + '_mcp_scientific-demos' for name in json.loads(definitions.stdout)}
    general = next(agent for agent in agents if agent['id'] == 'agent_nebius_scientific_ai')
    assert demo_tools <= set(general['tools'])
    for agent in agents:
        assert agent["skills_enabled"] is True
        assert agent["model_parameters"]["max_tokens"] == 16384
        assert instructions.read_text().strip() in agent["instructions"]
        assert set(agent["mcpServerNames"]) == {"scientific-ai-apps", "scientific-demos", "tavily", "structure-viewer", "environment-execution"}
        assert "tavily_search_mcp_tavily" in agent["tools"]
        assert "workbench_track_operation_mcp_scientific-demos" in agent["tools"]
        assert "run_scientific_workflow_mcp_environment-execution" in agent["tools"]
        assert "workbench_analyze_aging_mcp_scientific-demos" in agent["tools"]
        assert "workbench_compare_docking_batch_mcp_scientific-demos" in agent["tools"]
        assert "workbench_assemble_report_mcp_scientific-demos" in agent["tools"]
    assert "Immediately save every returned operation ID with workbench_track_operation" not in general['instructions']
    assert "track the returned ID with `workbench_track_operation`" not in general['instructions']
    assert "Runs automatically discovers" in general['instructions']
    assert "Do not launch parallel CLI processes" in general['instructions']
    assert "prefer `run_scientific_workflow_mcp_environment-execution` with its typed `study` (scientific-workflow/v2)" in general['instructions']
    assert "Do not rewrite existing numerical tables in an ad hoc Python renderer" in general['instructions']
    assert "analysis into another" not in general['instructions']
    assert "workspace_url" in general['instructions']


def test_genmol_skill_distinguishes_tokens_from_atom_measurements() -> None:
    skill = (ROOT.parents[1] / 'skills/scientific-ai/genmol/SKILL.md').read_text()
    assert 'floored midpoint' in skill
    assert 'no guaranteed minimum15 heavy atoms' in skill
    assert '**measurements only**' in skill
    assert 'batch `bindcraft`/`boltzgen`' not in skill


def test_chat_choices_keep_scientific_capabilities_and_exclude_native_models(tmp_path) -> None:
    config, _ = render_config(tmp_path)
    specs = config["modelSpecs"]["list"]
    assert {item["group"] for item in specs} == {
        "Scientific workspace", "Public Token Factory", "OpenAI", "Claude", "Research workflows"}
    assert len([item for item in specs if item["group"] == "Dedicated Token Factory"]) == 0
    assert len([item for item in specs if item["group"] == "Public Token Factory"]) > 2
    assert len([item for item in specs if item["default"]]) == 1
    assert len({item["name"] for item in specs}) == len(specs)
    for item in specs:
        if item["group"] == "Research workflows":
            assert item["preset"]["endpoint"] == "agents"
            assert item["preset"]["agent_id"] in {"agent_clinical_report", "agent_mindeval_workshop"}
            assert item["mcpServers"] == ["scientific-demos"]
            continue
        if item["group"] == "Scientific workspace":
            assert item["preset"] == {"endpoint": "agents", "agent_id": "agent_nebius_scientific_ai"}
            assert item["default"] is True
            assert item["mcpServers"] == ["scientific-ai-apps", "scientific-demos", "tavily", "structure-viewer", "environment-execution"]
            continue
        assert item["skills"] is True
        assert item["mcpServers"] == ["scientific-ai-apps", "scientific-demos", "tavily", "structure-viewer", "environment-execution"]
        assert INSTRUCTIONS.read_text().strip() in item["preset"]["promptPrefix"]
        assert item["preset"]["model"] not in {"evo2-40b", "boltz2", "openfold2", "sdxl", "nv-segment-ct"}
        assert "agent_id" not in item["preset"]
    assert any(
        item["group"] == "Public Token Factory"
        and item["preset"]["model"] == "Qwen/Qwen3-30B-A3B-Instruct-2507"
        for item in specs
    )
    assert any(
        item["group"] == "Public Token Factory"
        and item["preset"]["model"] == "Qwen/Qwen3-235B-A22B-Instruct-2507"
        for item in specs
    )
    assert config["interface"]["modelSelect"] is False  # curated specs remain selectable
    assert [item["name"] for item in config["endpoints"]["custom"]] == ["Nebius Token Factory"]
    token_configs = {
        endpoint["name"]: endpoint["tokenConfig"]
        for endpoint in config["endpoints"]["custom"]
    }
    for item in specs:
        if item["group"] not in {"Dedicated Token Factory", "Public Token Factory"}:
            continue
        endpoint = item["preset"]["endpoint"]
        model = item["preset"]["model"]
        assert token_configs[endpoint][model]["context"] >= 65536


def test_model_grouped_tutorials_are_seeded() -> None:
    seeder = (ROOT / "seed-workbench.js").read_text(encoding="utf-8")
    assert "agent_nebius_scientific_ai" in seeder
    assert "agent_protein_structure" in seeder
    assert "agent_molecular_design" in seeder
    assert "agent_biomedical_imaging" in seeder
    assert "agent_genomics_aging" in seeder
    assert "agent_audio_transcription_tutorial" in seeder
    assert "scientificAppsServerName" in seeder
    assert "boltz2_predict_native" in seeder
    assert "segment_ct_native" in seeder
    assert "Do not give a diagnosis" in seeder


def test_default_model_and_visible_workbench(tmp_path) -> None:
    config, _ = render_config(tmp_path)
    brand_client = (ROOT / "brand-client.mjs").read_text(encoding="utf-8")
    default = next(item for item in config["modelSpecs"]["list"] if item["default"])
    assert default["preset"] == {"endpoint": "agents", "agent_id": "agent_nebius_scientific_ai"}
    assert "nebius-scientific-workbench" in brand_client
    for title in (
        "Reproduce a published result", "Predict and compare structures", "Design and rank candidates",
        "Analyze sequences and aging clocks", "Work with speech and medical data", "Augment robotics data",
    ):
        assert title in (ROOT / "ScientificLanding.tsx").read_text(encoding="utf-8")


def test_team_bucket_context_is_injected(tmp_path) -> None:
    config, _ = render_config(tmp_path, TEAM_ID="research-lab",
                              TEAM_BUCKET_NAME="fs2-research-lab-example")
    public = next(item for item in config["modelSpecs"]["list"] if item["group"] == "Public Token Factory")
    prompt = public["preset"]["promptPrefix"]
    assert "research-lab's dedicated scientific workspace" in prompt
    assert "fs2-research-lab-example is mounted read-write at /workspace" in prompt
    custom = config["endpoints"]["custom"]
    assert len(custom) == 1
    assert custom[0]["baseURL"] == "https://api.tokenfactory.nebius.com/v1"


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
