import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import plugin from "../openclaw-plugin/index.mjs";
import manifest from "../openclaw-plugin/openclaw.plugin.json" with { type: "json" };
import { EXACT_TOOL_NAMES, TOOLKIT_COMMIT } from "../openclaw-plugin/src/catalog.mjs";
import { createUiHandlers, __test as uiInternals } from "../openclaw-plugin/src/ui.mjs";
import { __test as launcher } from "../runtime/launcher.mjs";
import { capabilities, configureOpenClaw, DEFAULT_MCP_URL, TOKEN_FACTORY_MODELS } from "../runtime/runtime-config.mjs";
import { prepareClients } from "../runtime/prepare-clients.mjs";

function fakeApi() {
  const captured = { tools: [], routes: [], controls: [], hooks: [] };
  return {
    captured,
    logger: { info() {}, error() {} },
    registerTool(value) { captured.tools.push(value); },
    registerHttpRoute(value) { captured.routes.push(value); },
    on(event, handler) { captured.hooks.push({ event, handler }); },
    session: { controls: { registerControlUiDescriptor(value) { captured.controls.push(value); } } },
  };
}

test("plugin registers exactly the manifest-declared 13 tools", async () => {
  const api = fakeApi();
  plugin.register(api);
  assert.deepEqual(api.captured.tools.map((tool) => tool.name), EXACT_TOOL_NAMES);
  assert.deepEqual(manifest.contracts.tools, EXACT_TOOL_NAMES);
  assert.equal(api.captured.tools.every((tool) => tool.parameters.additionalProperties === false), true);
  assert.equal(api.captured.hooks.length, 1);
  const systemContext = (await api.captured.hooks[0].handler()).prependSystemContext;
  assert.match(systemContext, /MEDIA:<downloadPath>/u);
  assert.match(systemContext, /When clawbio_\* MCP tools are available/u);
});

test("model-facing OpenFold2 schema exposes only the reliable sequence argument", () => {
  const api = fakeApi();
  plugin.register(api);
  const tool = api.captured.tools.find((item) => item.name === "bionemo_openfold2");
  assert.deepEqual(tool.parameters.required, ["sequence"]);
  assert.deepEqual(Object.keys(tool.parameters.properties), ["sequence"]);
});

test("dashboard data and artifacts are gateway-authenticated while readiness is public", () => {
  const api = fakeApi();
  plugin.register(api);
  const route = (pathname) => api.captured.routes.find((item) => item.path === pathname);
  assert.equal(route("/plugins/bionemo/api").auth, "gateway");
  assert.equal(route("/plugins/bionemo").auth, "plugin");
  assert.equal(route("/plugins/bionemo/readiness").auth, "plugin");
  assert.equal(api.captured.controls[0].path, "/plugins/bionemo");
  assert.deepEqual(api.captured.controls[0].requiredScopes, ["operator.read"]);
});

test("dashboard CSP is nonce-based and token never enters URL or persistent storage", () => {
  const html = uiInternals.dashboardHtml("test-nonce");
  assert.match(html, /nonce="test-nonce"/u);
  assert.equal(html.includes("localStorage"), false);
  assert.equal(html.includes("sessionStorage"), false);
  assert.equal(html.includes("?token="), false);
  assert.equal(html.includes('style="'), false);
  assert.match(html, /Authorization:'Bearer '\+bearer/u);
  assert.match(html, /setInterval\(refresh,5000\)/u);
  assert.match(html, /run\.steps/u);
  assert.match(html, /View 3D/u);
  assert.match(html, /3dmol\.min\.js/u);
  assert.match(html, /addModel\(structure/u);
  const script = html.match(/<script nonce="[^"]+">([\s\S]+)<\/script>/u)?.[1];
  assert.ok(script);
  assert.doesNotThrow(() => new vm.Script(script));
});

test("readiness reveals only capability presence", async () => {
  const store = { async initialize() {} };
  const handlers = createUiHandlers({ store, env: { NVIDIA_API_KEY: "nvidia-secret", NEBIUS_API_KEY: "nebius-secret", OPENCLAW_GATEWAY_TOKEN: "gateway-secret" }, runtimeVersion: "test" });
  const chunks = [];
  const res = { writeHead(status, headers) { this.status = status; this.headers = headers; }, end(value) { if (value) chunks.push(value); } };
  await handlers.readiness({}, res);
  const body = Buffer.concat(chunks).toString("utf8");
  assert.equal(res.status, 200);
  assert.equal(body.includes("nvidia-secret"), false);
  assert.equal(body.includes("nebius-secret"), false);
  assert.equal(body.includes("gateway-secret"), false);
  assert.deepEqual(JSON.parse(body).configured, { reasoning: true, reasoningProvider: "nvidia", modelBackend: "nvidia", nvidia: true, nebius: true, openai: false, anthropic: false, mcp: false, tavily: false, gateway: true });
});

test("readiness stays healthy in keyless setup-required mode", async () => {
  const handlers = createUiHandlers({ store: { async initialize() {} }, env: { OPENCLAW_GATEWAY_TOKEN: "gateway-secret" }, runtimeVersion: "test" });
  const chunks = [];
  const res = { writeHead(status) { this.status = status; }, end(value) { if (value) chunks.push(value); } };
  await handlers.readiness({}, res);
  assert.equal(res.status, 200);
  assert.equal(JSON.parse(Buffer.concat(chunks)).status, "setup_required");
});

test("launcher validates secrets without printing values and parses only safe origins", () => {
  assert.equal(launcher.requireEnvironment({ NEBIUS_API_KEY: "n", NVIDIA_API_KEY: "v", AUTH_TOKEN: "a".repeat(24) }), "a".repeat(24));
  assert.equal(launcher.requireEnvironment({ NEBIUS_API_KEY: "n", NGC_API_KEY: "v", AUTH_TOKEN: "a".repeat(24) }), "a".repeat(24));
  assert.throws(() => launcher.requireEnvironment({}), /AUTH_TOKEN/u);
  assert.throws(() => launcher.requireEnvironment({ NEBIUS_API_KEY: "secret-one", NVIDIA_API_KEY: "secret-two", AUTH_TOKEN: "short" }), /at least 24/u);
  assert.equal(launcher.safeOrigin("https://example.test"), "https://example.test");
  assert.throws(() => launcher.safeOrigin("https://user:pass@example.test"), /without credentials/u);
  assert.throws(() => launcher.safeOrigin("https://example.test/path"), /without credentials/u);
  assert.match("https://bounded-name.trycloudflare.com", new RegExp(launcher.CLOUDFLARED_URL_PATTERN));
});

test("launcher validates an explicitly supplied native Nebius managed HTTPS origin", () => {
  const managed = "https://port18789-vmeqjejf06sn58z.tunnel.applications.eu-north1.nebius.cloud";
  assert.equal(launcher.exposureMode({}), "cloudflare");
  assert.equal(launcher.exposureMode({ BIONEMO_ENABLE_HTTPS_TUNNEL: "false" }), "local");
  assert.equal(launcher.exposureMode({ BIONEMO_ENABLE_HTTPS_TUNNEL: "false", BIONEMO_PUBLIC_ORIGIN: "https://proxy.example" }), "external");
  assert.equal(launcher.exposureMode({ BIONEMO_HTTPS_MODE: "nebius" }), "nebius");
  assert.throws(() => launcher.exposureMode({ BIONEMO_HTTPS_MODE: "external" }), /requires BIONEMO_PUBLIC_ORIGIN/u);
  assert.throws(() => launcher.exposureMode({ BIONEMO_HTTPS_MODE: "wildcard" }), /cloudflare, nebius, external, or local/u);
  assert.equal(launcher.nebiusManagedOrigin(managed, 18789), managed);
  assert.throws(() => launcher.nebiusManagedOrigin("http://port18789-vmeqjejf06sn58z.tunnel.applications.eu-north1.nebius.cloud", 18789), /must match/u);
  assert.throws(() => launcher.nebiusManagedOrigin("https://port8000-vmeqjejf06sn58z.tunnel.applications.eu-north1.nebius.cloud", 18789), /must match/u);
  assert.throws(() => launcher.nebiusManagedOrigin("https://port18789-vmeqjejf06sn58z.tunnel.applications.eu-north1.nebius.cloud.evil.test", 18789), /must match/u);
});

test("dynamic native Nebius mode accepts its post-create browser origin without Host fallback", async (t) => {
  const managed = "https://port18789-vmeqjejf06sn58z.tunnel.applications.eu-north1.nebius.cloud";
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-nebius-origin-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const templatePath = path.join(root, "template.json");
  const configPath = path.join(root, "state", "openclaw.json");
  const stateDir = path.join(root, "state");
  await (await import("node:fs/promises")).copyFile(new URL("../config/openclaw.template.json", import.meta.url), templatePath);
  await launcher.writeRuntimeFiles({ templatePath, configPath, stateDir, origins: ["http://127.0.0.1:18789"], env: { BIONEMO_HTTPS_MODE: "nebius" } });
  const dynamic = JSON.parse(await readFile(configPath, "utf8"));
  assert.equal(dynamic.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback, false);
  assert.deepEqual(dynamic.gateway.controlUi.allowedOrigins, ["*"]);

  await launcher.writeRuntimeFiles({ templatePath, configPath, stateDir, origins: [managed], env: { BIONEMO_HTTPS_MODE: "nebius", BIONEMO_PUBLIC_ORIGIN: managed } });
  const explicit = JSON.parse(await readFile(configPath, "utf8"));
  assert.equal(explicit.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback, false);
  assert.deepEqual(explicit.gateway.controlUi.allowedOrigins, [managed]);
});

test("Serverless launch binds exactly one matching NVIDIA MysteryBox payload", async () => {
  const script = await readFile(new URL("../scripts/run_serverless_endpoint.sh", import.meta.url), "utf8");
  assert.match(script, /Set only one of NVIDIA_API_KEY_SECRET or NGC_API_KEY_SECRET/u);
  assert.match(script, /--env-secret "NVIDIA_API_KEY=\$NVIDIA_API_KEY_SECRET"/u);
  assert.match(script, /--env-secret "NGC_API_KEY=\$NGC_API_KEY_SECRET"/u);
  assert.equal(script.includes("--env \"NVIDIA_API_KEY="), false);
  assert.equal(script.includes("--env \"NGC_API_KEY="), false);
  assert.match(script, /BIONEMO_MCP_API_KEY_SECRET/u);
  assert.match(script, /TAVILY_API_KEY_SECRET/u);
  assert.match(script, /OPENAI_API_KEY_SECRET/u);
  assert.match(script, /ANTHROPIC_API_KEY_SECRET/u);
  assert.match(script, /BIONEMO_REQUIRE_DEVICE_PAIRING/u);
  assert.match(script, /BIONEMO_HTTPS_MODE/u);
  assert.match(script, /HTTPS_MODE="\$\{BIONEMO_HTTPS_MODE:-nebius\}"/u);
  assert.match(script, /CREATE_CMD\+=\(--public --auth token --token-secret "\$AUTH_TOKEN_SECRET"/u);
  assert.match(script, /Native Nebius browser mode requires BIONEMO_REQUIRE_DEVICE_PAIRING=false/u);
  assert.match(script, /no Cloudflare tunnel, no\s+public VM IP, and no Serverless bearer-auth layer/u);
  assert.equal((script.match(/--public/g) || []).length, 1);
  assert.equal((script.match(/--auth token/g) || []).length, 1);
  assert.equal(script.includes(": \"${NEBIUS_API_KEY_SECRET:?"), false);
});

test("runtime config and exec approvals persist placeholders, never secret values", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-runtime-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const templatePath = path.join(root, "template.json");
  const configPath = path.join(root, "state", "openclaw.json");
  const stateDir = path.join(root, "state");
  await (await import("node:fs/promises")).copyFile(new URL("../config/openclaw.template.json", import.meta.url), templatePath);
  await launcher.writeRuntimeFiles({ templatePath, configPath, stateDir, origins: ["https://example.test"], env: { NVIDIA_API_KEY: "secret-value", BIONEMO_MCP_API_KEY: "mcp-secret" } });
  const config = await readFile(configPath, "utf8");
  const parsedConfig = JSON.parse(config);
  const approvals = JSON.parse(await readFile(path.join(stateDir, "exec-approvals.json"), "utf8"));
  assert.match(config, /\$\{NVIDIA_API_KEY\}/u);
  assert.match(config, /\$\{BIONEMO_MCP_API_KEY\}/u);
  assert.equal(config.includes("secret-value"), false);
  assert.equal(config.includes("mcp-secret"), false);
  assert.equal(parsedConfig.gateway.controlUi.dangerouslyDisableDeviceAuth, true);
  assert.equal(parsedConfig.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback, false);
  assert.deepEqual(approvals.defaults, { security: "deny", ask: "off", askFallback: "deny", autoAllowSkills: false });
  assert.deepEqual(approvals.agents.bionemo.allowlist, []);
});

test("private deployments can require one-time Control UI device pairing", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-device-pairing-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const templatePath = path.join(root, "template.json");
  const configPath = path.join(root, "state", "openclaw.json");
  const stateDir = path.join(root, "state");
  await (await import("node:fs/promises")).copyFile(new URL("../config/openclaw.template.json", import.meta.url), templatePath);
  await launcher.writeRuntimeFiles({ templatePath, configPath, stateDir, origins: ["https://private.example"], env: { BIONEMO_REQUIRE_DEVICE_PAIRING: "true" } });
  const config = JSON.parse(await readFile(configPath, "utf8"));
  assert.equal(config.gateway.controlUi.dangerouslyDisableDeviceAuth, false);
});

test("static OpenClaw policy denies every general-purpose capability", async () => {
  const config = JSON.parse(await readFile(new URL("../config/openclaw.template.json", import.meta.url), "utf8"));
  assert.equal(config.tools.profile, "minimal");
  assert.deepEqual(config.tools.alsoAllow, EXACT_TOOL_NAMES);
  for (const group of ["group:runtime", "group:fs", "group:web", "group:ui", "group:automation", "group:nodes", "group:agents", "group:sessions"]) {
    assert.ok(config.tools.deny.includes(group), group);
  }
  assert.equal(config.tools.exec.mode, "deny");
  assert.equal(config.tools.elevated.enabled, false);
  assert.equal(config.gateway.terminal.enabled, false);
  assert.equal(config.gateway.auth.mode, "token");
  assert.equal(config.gateway.auth.token, "${OPENCLAW_GATEWAY_TOKEN}");
  assert.deepEqual(config.gateway.tools.deny, ["*"]);
  assert.deepEqual(config.plugins.allow, ["bionemo-agent-toolkit"]);
  assert.deepEqual(config.models.providers, {});
  assert.equal(config.agents.defaults.model.primary, "setup/setup-required");
  assert.equal(config.update.checkOnStart, false);
  assert.equal(config.update.auto.enabled, false);
});

test("all pins and model identity are immutable in the shipped configuration", async () => {
  const dockerfile = await readFile(new URL("../Dockerfile", import.meta.url), "utf8");
  const config = await readFile(new URL("../config/openclaw.template.json", import.meta.url), "utf8");
  assert.match(dockerfile, /openclaw:2026\.7\.1-2@sha256:8789721d/u);
  assert.match(dockerfile, /CLOUDFLARED_VERSION="2026\.7\.3"/u);
  assert.match(dockerfile, new RegExp(TOOLKIT_COMMIT));
  assert.match(dockerfile, /libgnutls30=3\.7\.9-2\+deb12u7/u);
  assert.match(dockerfile, /\/usr\/local\/lib\/node_modules\/npm/u);
  assert.match(dockerfile, /CODEX_VERSION="0\.147\.0"/u);
  assert.match(dockerfile, /CLAUDE_CODE_VERSION="2\.1\.228"/u);
  assert.match(config, /setup\/setup-required/u);
  assert.equal((await readFile(new URL("../vendor/bionemo-agent-toolkit/UPSTREAM_COMMIT", import.meta.url), "utf8")).trim(), TOOLKIT_COMMIT);
});

test("credential resolution supports all reasoning providers, MCP override, and keyless modes", () => {
  const nvidia = capabilities({ NVIDIA_API_KEY: "n" });
  assert.deepEqual([nvidia.reasoningProvider, nvidia.modelBackend, nvidia.nvidia, nvidia.nebius], ["nvidia", "nvidia", true, false]);
  const nebius = capabilities({ NEBIUS_API_KEY: "n" });
  assert.deepEqual([nebius.reasoningProvider, nebius.modelBackend, nebius.nvidia, nebius.nebius], ["nebius", "unavailable", false, true]);
  const mcp = capabilities({ NEBIUS_API_KEY: "n", BIONEMO_MCP_API_KEY: "m", BIONEMO_MCP_URL: "https://private.example/mcp" });
  assert.equal(mcp.reasoningProvider, "nebius");
  assert.equal(mcp.modelBackend, "mcp");
  assert.equal(mcp.mcpUrl, "https://private.example/mcp");
  assert.equal(capabilities({ OPENAI_API_KEY: "o" }).reasoningProvider, "openai");
  assert.equal(capabilities({ ANTHROPIC_API_KEY: "a" }).reasoningProvider, "anthropic");
  const keyless = capabilities({});
  assert.equal(keyless.reasoningProvider, "setup");
  assert.equal(keyless.modelBackend, "unavailable");
  assert.equal(keyless.mcpUrl, DEFAULT_MCP_URL);
});

test("OpenClaw enables only configured remote MCP servers and keeps credential placeholders", () => {
  const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  const state = configureOpenClaw(config, { NVIDIA_API_KEY: "n", BIONEMO_MCP_API_KEY: "m", TAVILY_API_KEY: "t" });
  assert.equal(state.reasoningProvider, "nvidia");
  assert.deepEqual(Object.keys(config.mcp.servers), ["clawbio_models", "tavily"]);
  assert.equal(config.mcp.servers.clawbio_models.headers.Authorization, "Bearer ${BIONEMO_MCP_API_KEY}");
  assert.equal(config.mcp.servers.tavily.headers.Authorization, "Bearer ${TAVILY_API_KEY}");
  assert.ok(config.tools.alsoAllow.includes("bundle-mcp"));
  assert.equal(config.tools.deny.includes("bundle-mcp"), false);
  assert.deepEqual(Object.keys(config.models.providers), ["nvidia", "tokenfactory", "openai", "claude", "setup"]);
  assert.match(config.models.providers.openai.models[0].name, /requires API key/u);
  assert.match(config.models.providers.claude.models[0].name, /Anthropic Claude.*requires API key/u);
  assert.equal(config.models.providers.openai.baseUrl, "http://127.0.0.1:18790/v1");
  assert.equal(config.models.providers.claude.baseUrl, "http://127.0.0.1:18790/v1");
  assert.deepEqual(config.models.providers.openai.models[0].agentRuntime, { id: "openclaw" });
  assert.equal(config.models.providers.tokenfactory.baseUrl, "http://127.0.0.1:18790/v1");
  assert.equal(config.models.providers.tokenfactory.apiKey, "setup-required");
  assert.equal(config.models.providers.tokenfactory.api, "openai-completions");
  assert.equal(config.models.providers.tokenfactory.models.every((model) => model.name.endsWith(" (requires API key)") && model.reasoning === false && model.maxTokens === 1024), true);
  assert.deepEqual(config.models.providers.tokenfactory.models.map(({ id, contextWindow }) => ({ id, contextWindow })), TOKEN_FACTORY_MODELS.map(({ id, contextWindow }) => ({ id, contextWindow })));
  const allowedModels = config.agents.defaults.models;
  assert.deepEqual([...new Set(Object.keys(allowedModels).map((key) => key.slice(0, key.indexOf("/"))))], ["nvidia", "tokenfactory", "openai", "claude"]);
  assert.deepEqual(Object.keys(allowedModels).filter((key) => key.startsWith("tokenfactory/")), TOKEN_FACTORY_MODELS.map(({ id }) => `tokenfactory/${id}`));
  assert.deepEqual(Object.values(allowedModels).filter(({ alias }) => alias).map(({ alias }) => alias), TOKEN_FACTORY_MODELS.map(({ alias }) => alias));
});

test("Token Factory models retain aliases, credential placeholders, and AGENT_MODEL overrides", () => {
  const configured = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  configureOpenClaw(configured, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "do-not-persist", AGENT_MODEL: "nvidia/nemotron-3_5-lightning" });
  assert.equal(configured.agents.defaults.model.primary, "tokenfactory/nvidia/Nemotron-3_5-Lightning");
  assert.equal(configured.models.providers.tokenfactory.baseUrl, "https://api.tokenfactory.nebius.com/v1");
  assert.equal(configured.models.providers.tokenfactory.apiKey, "${NEBIUS_API_KEY}");
  assert.equal(configured.models.providers.tokenfactory.models.every((model) => !model.name.includes("requires API key") && model.reasoning === true), true);
  assert.deepEqual(configured.models.providers.tokenfactory.models.map(({ id, contextWindow, maxTokens }) => ({ id, contextWindow, maxTokens })), TOKEN_FACTORY_MODELS.map(({ id, contextWindow, maxTokens }) => ({ id, contextWindow, maxTokens })));
  assert.equal(JSON.stringify(configured).includes("do-not-persist"), false);

  const custom = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  configureOpenClaw(custom, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "another-secret", AGENT_MODEL: "example/Custom-Agent-1" });
  assert.equal(custom.agents.defaults.model.primary, "tokenfactory/example/Custom-Agent-1");
  assert.equal(custom.models.providers.tokenfactory.models.filter(({ id }) => id === "example/Custom-Agent-1").length, 1);
  assert.deepEqual(custom.agents.defaults.models["tokenfactory/example/Custom-Agent-1"], {});
  assert.equal(JSON.stringify(custom).includes("another-secret"), false);
});

test("OpenAI and Claude use environment placeholders only when authorized", () => {
  const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  configureOpenClaw(config, { AGENT_PROVIDER: "openai", OPENAI_API_KEY: "do-not-persist", ANTHROPIC_API_KEY: "also-do-not-persist" });
  const serialized = JSON.stringify(config);
  assert.equal(config.agents.defaults.model.primary, "openai/gpt-5.6");
  assert.equal(config.models.providers.openai.apiKey, "${OPENAI_API_KEY}");
  assert.equal(config.models.providers.claude.apiKey, "${ANTHROPIC_API_KEY}");
  assert.equal(serialized.includes("do-not-persist"), false);
  assert.equal(serialized.includes("also-do-not-persist"), false);
});

test("Codex and Claude configs contain placeholders and all packaged skills without auth caches", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-clients-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const workspace = path.join(root, "workspace");
  await prepareClients({ HOME: root, BIONEMO_CLIENT_WORKSPACE: workspace, BIONEMO_MCP_API_KEY: "never-write-this", TAVILY_API_KEY: "also-secret" });
  const codex = await readFile(path.join(root, ".codex", "config.toml"), "utf8");
  const claude = await readFile(path.join(workspace, ".mcp.json"), "utf8");
  assert.match(codex, /bearer_token_env_var = "BIONEMO_MCP_API_KEY"/u);
  assert.match(claude, /\$\{BIONEMO_MCP_API_KEY\}/u);
  assert.equal(codex.includes("never-write-this"), false);
  assert.equal(claude.includes("also-secret"), false);
});

test("Codex and Claude retain the BioNeMo MCP URL when credentials are absent", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-keyless-clients-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const workspace = path.join(root, "workspace");
  await prepareClients({ HOME: root, BIONEMO_CLIENT_WORKSPACE: workspace });
  const codex = await readFile(path.join(root, ".codex", "config.toml"), "utf8");
  const claude = await readFile(path.join(workspace, ".mcp.json"), "utf8");
  assert.match(codex, new RegExp(DEFAULT_MCP_URL));
  assert.match(claude, new RegExp(DEFAULT_MCP_URL));
  assert.equal(codex.includes("bearer_token_env_var"), false);
  assert.equal(claude.includes("Authorization"), false);
});
