import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import plugin, { __test as pluginInternals } from "../openclaw-plugin/index.mjs";
import manifest from "../openclaw-plugin/openclaw.plugin.json" with { type: "json" };
import { CROSS_BACKEND_TOOL_NAMES, DIRECT_ONLY_TOOL_NAMES, EXACT_TOOL_NAMES, TOOLKIT_COMMIT } from "../openclaw-plugin/src/catalog.mjs";
import { createUiHandlers, __test as uiInternals } from "../openclaw-plugin/src/ui.mjs";
import { __test as launcher } from "../runtime/launcher.mjs";
import { capabilities, configureOpenClaw, DEFAULT_MCP_URL, TOKEN_FACTORY_MODELS } from "../runtime/runtime-config.mjs";
import { prepareClients } from "../runtime/prepare-clients.mjs";
import { MCP_TURN_ID_FIELD } from "../runtime/mcp-submission-policy.mjs";

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

const PRESENTATION_AGENT_RUN_ID = "agent-run-presentation-11111111";
const PRESENTATION_WORKFLOW_RUN_ID = "11111111-1111-4111-8111-111111111111";
const PRESENTATION_FIRST_VIEWER = `[View structure in 3D](</bionemo/view/${PRESENTATION_WORKFLOW_RUN_ID}/01-top.pdb?access=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa>)`;
const PRESENTATION_SECOND_VIEWER = `[View structure in 3D](</bionemo/view/${PRESENTATION_WORKFLOW_RUN_ID}/02-complex.cif?access=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb>)`;

function presentationWorkflowResult() {
  return {
    runId: PRESENTATION_WORKFLOW_RUN_ID,
    summary: { status: "completed" },
    steps: [],
    artifacts: [
      { name: "01-top.pdb", bytes: 10, downloadPath: `/workspace/agent/artifacts/${PRESENTATION_WORKFLOW_RUN_ID}/01-top.pdb`, viewerMarkdown: PRESENTATION_FIRST_VIEWER },
      { name: "02-complex.cif", bytes: 20, downloadPath: `/workspace/agent/artifacts/${PRESENTATION_WORKFLOW_RUN_ID}/02-complex.cif`, viewerMarkdown: PRESENTATION_SECOND_VIEWER },
    ],
  };
}

test("plugin registers exactly the manifest-declared 17 tools", async () => {
  const api = fakeApi();
  plugin.register(api);
  assert.deepEqual(api.captured.tools.map((tool) => tool.name), EXACT_TOOL_NAMES);
  assert.deepEqual(manifest.contracts.tools, EXACT_TOOL_NAMES);
  assert.equal(api.captured.tools.every((tool) => tool.parameters.additionalProperties === false), true);
  assert.deepEqual(api.captured.hooks.map(({ event }) => event), ["before_tool_call", "before_agent_finalize", "agent_end", "before_prompt_build"]);
  const promptHook = api.captured.hooks.find(({ event }) => event === "before_prompt_build");
  const systemContext = (await promptHook.handler()).prependSystemContext;
  assert.match(systemContext, /MEDIA:<downloadPath>/u);
  assert.match(systemContext, /When clawbio_\* MCP tools are available/u);
  assert.match(systemContext, /For every artifact that has viewerMarkdown/u);
  assert.match(systemContext, /same-origin path beginning with \/; preserve it verbatim/u);
  assert.doesNotMatch(systemContext, /viewerUrl, use that exact absolute URL/u);
  assert.match(systemContext, /submission tool may be called only once per user request/u);
  assert.match(systemContext, /poll only clawbio_job_status for that exact ID, at most four times/u);
  assert.match(systemContext, /never resubmit or call jobs-list\/model-fetch discovery/u);
});

test("completed composed workflows register a run-scoped final presentation synchronously", async () => {
  const api = fakeApi();
  let workflowCalls = 0;
  pluginInternals.registerPlugin(api, { runtime: {
    store: {},
    async runSkill() { throw new Error("not used"); },
    async runWorkflow() {
      workflowCalls += 1;
      return presentationWorkflowResult();
    },
  } });
  const tool = api.captured.tools.find(({ name }) => name === "bionemo_research_drug_demo");
  const beforeFinalize = api.captured.hooks.find(({ event }) => event === "before_agent_finalize").handler;
  const agentEnd = api.captured.hooks.find(({ event }) => event === "agent_end").handler;
  const result = await tool.execute("tool-call-1", {
    [MCP_TURN_ID_FIELD]: PRESENTATION_AGENT_RUN_ID,
    ack_research_only: true,
  });
  assert.equal(workflowCalls, 1, "presentation must not repeat model or science execution");
  assert.equal(result.structuredContent.runId, PRESENTATION_WORKFLOW_RUN_ID);

  const unrelated = beforeFinalize({ runId: "other-agent-run-11111111", lastAssistantMessage: "Other" }, { runId: "other-agent-run-11111111" });
  assert.equal(unrelated, undefined, "state is isolated by exact agent runId, not session");
  const final = beforeFinalize({ runId: PRESENTATION_AGENT_RUN_ID, lastAssistantMessage: `Summary\n${PRESENTATION_FIRST_VIEWER}` }, { runId: PRESENTATION_AGENT_RUN_ID });
  assert.equal(final.action, "continue");
  assert.equal(final.appendFinalAssistantText.split(PRESENTATION_FIRST_VIEWER).length - 1, 0, "existing viewer is not duplicated");
  assert.equal(final.appendFinalAssistantText.split(PRESENTATION_SECOND_VIEWER).length - 1, 1);
  assert.match(final.appendFinalAssistantText, new RegExp(`MEDIA:/workspace/agent/artifacts/${PRESENTATION_WORKFLOW_RUN_ID}/01-top\\.pdb`, "u"));
  const repeatedFinalize = beforeFinalize({ runId: PRESENTATION_AGENT_RUN_ID, lastAssistantMessage: "later" }, { runId: PRESENTATION_AGENT_RUN_ID });
  assert.match(repeatedFinalize.appendFinalAssistantText, /Workflow artifacts/u, "state remains available until terminal agent_end cleanup");
  agentEnd({ runId: PRESENTATION_AGENT_RUN_ID }, { runId: PRESENTATION_AGENT_RUN_ID });
  assert.equal(workflowCalls, 1);

  assert.equal(pluginInternals.artifactPresentation({ structuredContent: { runId: "11111111-1111-4111-8111-111111111111", artifacts: [{ viewerMarkdown: "unsafe", downloadPath: "/tmp/x" }] } }), undefined);
  for (const artifact of [
    { name: "result.json", downloadPath: `/workspace/agent/artifacts/${PRESENTATION_WORKFLOW_RUN_ID}/result.json`, viewerMarkdown: `[View structure in 3D](</bionemo/view/${PRESENTATION_WORKFLOW_RUN_ID}/result.json?access=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa>)` },
    { name: "01-top.pdb", downloadPath: `/workspace/agent/artifacts/${PRESENTATION_WORKFLOW_RUN_ID}/other.pdb`, viewerMarkdown: PRESENTATION_FIRST_VIEWER },
    { name: "01-top.pdb", downloadPath: `/workspace/agent/artifacts/${PRESENTATION_WORKFLOW_RUN_ID}/01-top.pdb`, viewerMarkdown: `[View structure in 3D](<https://evil.example/bionemo/view/${PRESENTATION_WORKFLOW_RUN_ID}/01-top.pdb?access=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa>)` },
  ]) assert.equal(pluginInternals.artifactPresentation({ structuredContent: { runId: PRESENTATION_WORKFLOW_RUN_ID, artifacts: [artifact] } }), undefined);
});

test("presentation state clears on workflow failure, agent abort, and TTL expiry", async () => {
  let clock = 10;
  const scheduled = [];
  const registry = pluginInternals.createPresentationRegistry({
    now: () => clock,
    ttlMs: 5,
    setTimeoutImpl(handler) { scheduled.push(handler); return { unref() {} }; },
    clearTimeoutImpl() {},
  });
  registry.set(PRESENTATION_AGENT_RUN_ID, { viewerMarkdown: [PRESENTATION_FIRST_VIEWER] });
  assert.ok(registry.get(PRESENTATION_AGENT_RUN_ID));
  clock = 16;
  assert.equal(registry.get(PRESENTATION_AGENT_RUN_ID), undefined);
  assert.equal(registry.size(), 0);
  scheduled[0]();

  const api = fakeApi();
  pluginInternals.registerPlugin(api, { runtime: {
    store: {},
    async runSkill() { throw new Error("not used"); },
    async runWorkflow() { throw new Error("workflow failed"); },
  }, presentationRegistry: registry });
  const tool = api.captured.tools.find(({ name }) => name === "bionemo_research_drug_demo");
  registry.set(PRESENTATION_AGENT_RUN_ID, { viewerMarkdown: [PRESENTATION_FIRST_VIEWER] });
  await assert.rejects(() => tool.execute("tool-call-2", { [MCP_TURN_ID_FIELD]: PRESENTATION_AGENT_RUN_ID }), /workflow failed/u);
  assert.equal(registry.get(PRESENTATION_AGENT_RUN_ID), undefined);
  registry.set(PRESENTATION_AGENT_RUN_ID, { viewerMarkdown: [PRESENTATION_FIRST_VIEWER] });
  api.captured.hooks.find(({ event }) => event === "agent_end").handler({ runId: PRESENTATION_AGENT_RUN_ID, success: false }, { runId: PRESENTATION_AGENT_RUN_ID });
  assert.equal(registry.get(PRESENTATION_AGENT_RUN_ID), undefined);
});

test("phase-aware message helper never appends an invisible unphased sibling", () => {
  const presentation = pluginInternals.artifactPresentation({ structuredContent: presentationWorkflowResult() });
  const commentarySignature = JSON.stringify({ v: 1, id: "commentary-item", phase: "commentary" });
  const finalSignature = JSON.stringify({ v: 1, id: "final-item", phase: "final_answer" });
  const message = {
    role: "assistant",
    stopReason: "stop",
    content: [
      { type: "text", text: "working", textSignature: commentarySignature },
      { type: "text", text: "Summary", textSignature: finalSignature },
    ],
  };
  const patched = pluginInternals.appendArtifactPresentation(message, presentation);
  assert.equal(patched.content[0].textSignature, commentarySignature);
  assert.equal(patched.content[1].textSignature, finalSignature);
  assert.equal(pluginInternals.textBlockPhase(patched.content.at(-1)), "final_answer");
  assert.equal(pluginInternals.visibleAssistantText(patched).includes(PRESENTATION_FIRST_VIEWER), true);
  assert.equal(pluginInternals.appendArtifactPresentation({ ...message, stopReason: "aborted" }, presentation), undefined);
  assert.equal(pluginInternals.appendArtifactPresentation({ ...message, stopReason: "error" }, presentation), undefined);
  assert.equal(pluginInternals.appendArtifactPresentation({ ...message, stopReason: "length" }, presentation), undefined);
  assert.equal(pluginInternals.appendArtifactPresentation({ ...message, phase: "commentary" }, presentation), undefined);
  const mentionedMedia = pluginInternals.artifactPresentationAppendText(`Do not emit ${presentation.mediaLine} inline.`, presentation);
  assert.ok(mentionedMedia.split("\n").includes(presentation.mediaLine), "an inline MEDIA mention cannot suppress the required own-line directive");
});

test("agent instructions require exact clickable viewer links", async () => {
  const api = fakeApi();
  plugin.register(api);
  const promptHook = api.captured.hooks.find(({ event }) => event === "before_prompt_build");
  const systemContext = (await promptHook.handler()).prependSystemContext;
  const expectedLink = "[View structure in 3D](<VALUE>)";
  assert.equal(systemContext.includes(expectedLink), true);
  assert.match(systemContext, /copy that complete viewerMarkdown field verbatim/u);
  assert.match(systemContext, /Do not reconstruct it from viewerUrl/u);
  assert.match(systemContext, /do not leave either field as plain text/u);

  const workspaceInstructions = await readFile(new URL("../workspace/AGENTS.md", import.meta.url), "utf8");
  assert.equal(workspaceInstructions.includes(`\`${expectedLink}\``), true);
  assert.match(workspaceInstructions, /copy that complete field verbatim/u);
  assert.match(workspaceInstructions, /Never reconstruct it from `viewerUrl`/u);
});

test("plugin injects trusted per-turn identity only into compute-submitting MCP tools", async () => {
  const api = fakeApi();
  plugin.register(api);
  const hook = api.captured.hooks.find(({ event }) => event === "before_tool_call").handler;
  const runId = "d9fd641b-f6ae-42c6-aeed-f18b2f770299";
  const event = {
    toolName: "clawbio_models__clawbio_esm2_embed",
    params: { sequences: ["MKTII"], ack_research_only: true, ack_non_clinical: true },
  };
  const injected = await hook(event, { runId });
  assert.equal(injected.params[MCP_TURN_ID_FIELD], runId);
  assert.deepEqual(event.params, { sequences: ["MKTII"], ack_research_only: true, ack_non_clinical: true });
  const wrapperEvent = { toolName: "bionemo_research_drug_demo", params: { ack_research_only: true } };
  const wrapperInjected = await hook(wrapperEvent, { runId });
  assert.equal(wrapperInjected.params[MCP_TURN_ID_FIELD], runId);
  assert.equal(wrapperInjected.params.ack_research_only, true);
  assert.deepEqual(wrapperEvent.params, { ack_research_only: true });
  for (const toolName of CROSS_BACKEND_TOOL_NAMES.slice(1)) {
    const composed = await hook({ toolName, params: { ack_research_only: true } }, { runId });
    assert.equal(composed.params[MCP_TURN_ID_FIELD], runId);
  }

  assert.equal(await hook({ toolName: "clawbio_models__clawbio_job_status", params: { job_id: "job" } }, { runId }), undefined);
  assert.equal(await hook({ toolName: "bionemo_openfold2", params: { sequence: "MKTII" } }, { runId }), undefined);
  const missing = await hook(event, {});
  assert.equal(missing.block, true);
  assert.match(missing.blockReason, /trusted per-turn identity is unavailable/u);
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
  assert.equal(route("/bionemo/view").auth, "plugin");
  assert.equal(route("/bionemo/view").match, "prefix");
  assert.equal(route("/plugins/bionemo/view"), undefined);
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

test("Serverless launch binds one backend-specific MysteryBox payload", async () => {
  const script = await readFile(new URL("../scripts/run_serverless_endpoint.sh", import.meta.url), "utf8");
  assert.match(script, /MODEL_CREDENTIALS_SECRET/u);
  assert.match(script, /--env-secret "NVIDIA_API_KEY=\$MODEL_CREDENTIALS_SECRET"/u);
  assert.match(script, /--env-secret "NEBIUS_API_KEY=\$MODEL_CREDENTIALS_SECRET"/u);
  assert.match(script, /--env-secret "BIONEMO_MCP_API_KEY=\$MODEL_CREDENTIALS_SECRET"/u);
  assert.equal(script.includes("--env \"NVIDIA_API_KEY="), false);
  assert.equal(script.includes("--env \"NGC_API_KEY="), false);
  assert.match(script, /TAVILY_SECRET/u);
  assert.match(script, /BIONEMO_HTTPS_MODE/u);
  assert.match(script, /no public VM IP or second authentication layer/u);
  assert.equal((script.match(/MODEL_CREDENTIALS_SECRET/g) || []).length >= 4, true);
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
  assert.equal(parsedConfig.agents.defaults.compaction.reserveTokensFloor, 20_000);
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
  assert.equal(config.gateway.controlUi.root, "/opt/bionemo/control-ui");
  assert.equal(config.gateway.auth.mode, "token");
  assert.equal(config.gateway.auth.token, "${OPENCLAW_GATEWAY_TOKEN}");
  assert.deepEqual(config.gateway.tools.deny, ["*"]);
  assert.deepEqual(config.plugins.allow, ["bionemo-agent-toolkit"]);
  assert.deepEqual(config.models.providers, {});
  assert.equal(config.agents.defaults.model.primary, "setup/setup-required");
  assert.equal(config.agents.defaults.compaction.reserveTokensFloor, 20_000);
  assert.equal(config.update.checkOnStart, false);
  assert.equal(config.update.auto.enabled, false);
});

test("all pins and model identity are immutable in the shipped configuration", async () => {
  const dockerfile = await readFile(new URL("../Dockerfile", import.meta.url), "utf8");
  const config = await readFile(new URL("../config/openclaw.template.json", import.meta.url), "utf8");
  const packageManifest = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
  const pluginPackageManifest = JSON.parse(await readFile(new URL("../openclaw-plugin/package.json", import.meta.url), "utf8"));
  const pluginManifest = JSON.parse(await readFile(new URL("../openclaw-plugin/openclaw.plugin.json", import.meta.url), "utf8"));
  const templateConfig = JSON.parse(config);
  const readme = await readFile(new URL("../README.md", import.meta.url), "utf8");
  assert.match(dockerfile, /openclaw:2026\.7\.1-2@sha256:8789721d/u);
  assert.match(dockerfile, /org\.opencontainers\.image\.version="3\.3\.2"/u);
  assert.match(dockerfile, /CLOUDFLARED_VERSION="2026\.7\.3"/u);
  assert.match(dockerfile, new RegExp(TOOLKIT_COMMIT));
  assert.match(dockerfile, /libgnutls30=3\.7\.9-2\+deb12u7/u);
  assert.match(dockerfile, /\/usr\/local\/lib\/node_modules\/npm/u);
  assert.match(dockerfile, /CODEX_VERSION="0\.147\.0"/u);
  assert.match(dockerfile, /CLAUDE_CODE_VERSION="2\.1\.228"/u);
  assert.match(dockerfile, /chmod -R a-w \/workspace\/agent\/notebooks/u);
  assert.match(dockerfile, /BIONEMO_NOTEBOOK_ROOT=\/workspace\/agent\/notebooks/u);
  assert.match(config, /setup\/setup-required/u);
  assert.equal(templateConfig.plugins.entries["bionemo-agent-toolkit"].hooks.allowConversationAccess, true, "before_agent_finalize and agent_end require explicit conversation access in pinned OpenClaw");
  assert.deepEqual([packageManifest.version, pluginPackageManifest.version, pluginManifest.version], ["3.3.2", "3.3.2", "3.3.2"]);
  assert.match(readme, /^# BioNeMo Agent Workbench 3\.3\.2 on Nebius Serverless$/mu);
  assert.match(uiInternals.dashboardHtml("test-nonce"), /BioNeMo Agent Workbench 3\.3\.2/u);
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

test("NVIDIA defaults to the tool-reliable Super profile", () => {
  const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  configureOpenClaw(config, { AGENT_PROVIDER: "nvidia", NVIDIA_API_KEY: "do-not-persist" });
  const [superModel] = config.models.providers.nvidia.models;
  assert.equal(config.agents.defaults.model.primary, "nvidia/nvidia/nemotron-3-super-120b-a12b");
  assert.equal(superModel.id, "nvidia/nemotron-3-super-120b-a12b");
  assert.equal(superModel.contextWindow, 1_000_000);
  assert.equal(superModel.maxTokens, 8_192);
  assert.deepEqual(superModel.compat, { maxTokensField: "max_tokens", requiresStringContent: true });
  assert.equal(superModel.params, undefined);
  assert.equal(config.models.providers.nvidia.timeoutSeconds, 240);
  assert.equal(config.models.providers.tokenfactory.timeoutSeconds, undefined);
  assert.deepEqual(config.agents.defaults.models["nvidia/nvidia/nemotron-3-super-120b-a12b"].params, {
    chat_template_kwargs: { enable_thinking: false, force_nonempty_content: true },
  });
  assert.equal(JSON.stringify(config).includes("do-not-persist"), false);

  const custom = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  configureOpenClaw(custom, { AGENT_PROVIDER: "nvidia", NVIDIA_API_KEY: "do-not-persist", AGENT_MODEL: "example/custom" });
  assert.equal(custom.models.providers.nvidia.models[0].contextWindow, 262_144);
  assert.equal(custom.models.providers.nvidia.models[0].maxTokens, 8_192);
  assert.equal(custom.models.providers.nvidia.models[0].compat, undefined);
  assert.deepEqual(custom.agents.defaults.models["nvidia/example/custom"], {});
});

test("OpenClaw enables only configured remote MCP servers and keeps credential placeholders", () => {
  const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  const state = configureOpenClaw(config, { NVIDIA_API_KEY: "n", BIONEMO_MCP_API_KEY: "m", TAVILY_API_KEY: "t" });
  assert.equal(state.reasoningProvider, "nvidia");
  assert.deepEqual(Object.keys(config.mcp.servers), ["clawbio_models", "tavily_web"]);
  assert.equal(config.mcp.servers.clawbio_models.headers.Authorization, "Bearer ${BIONEMO_MCP_API_KEY}");
  assert.equal(config.mcp.servers.tavily_web.headers.Authorization, "Bearer ${BIONEMO_TAVILY_API_KEY}");
  assert.equal(config.mcp.servers.tavily, undefined);
  assert.equal(capabilities({ BIONEMO_TAVILY_API_KEY: "private-alias" }).tavily, true);
  assert.ok(config.tools.alsoAllow.includes("bundle-mcp"));
  assert.equal(config.tools.deny.includes("bundle-mcp"), false);
  assert.equal(config.tools.alsoAllow.includes("bionemo_research_drug_demo"), true);
  assert.equal(config.tools.deny.includes("bionemo_research_drug_demo"), false);
  assert.equal(CROSS_BACKEND_TOOL_NAMES.every((name) => config.tools.alsoAllow.includes(name) && !config.tools.deny.includes(name)), true);
  assert.equal(config.tools.alsoAllow.some((name) => DIRECT_ONLY_TOOL_NAMES.includes(name)), false);
  assert.equal(DIRECT_ONLY_TOOL_NAMES.every((name) => config.tools.deny.includes(name)), true);
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

test("gateway child hides OpenClaw's reserved Tavily auto-install trigger", () => {
  const child = launcher.gatewayChildEnvironment({
    AUTH_TOKEN: "do-not-forward",
    TAVILY_API_KEY: "tavily-secret",
    NVIDIA_API_KEY: "nvidia-secret",
  }, "gateway-secret", {
    port: 18789,
    stateDir: "/workspace/state",
    configPath: "/workspace/state/openclaw.json",
  });
  assert.equal(child.AUTH_TOKEN, undefined);
  assert.equal(child.TAVILY_API_KEY, undefined);
  assert.equal(child.BIONEMO_TAVILY_API_KEY, "tavily-secret");
  assert.equal(child.OPENCLAW_GATEWAY_TOKEN, "gateway-secret");
  assert.equal(child.NVIDIA_API_KEY, "nvidia-secret");
});

test("launcher keeps the flattened adapter URL distinct from the private native MCP workflow upstream", async (t) => {
  const runtimeEnv = {
    BIONEMO_MCP_API_KEY: "not-persisted",
    BIONEMO_MCP_URL: "https://native.example/mcp",
  };
  const processEnv = {};
  launcher.configureMcpAdapterEnvironment(runtimeEnv, {
    upstreamUrl: "https://native.example/mcp",
    adapterUrl: "http://127.0.0.1:18791/mcp",
    processEnv,
  });
  assert.equal(runtimeEnv.BIONEMO_MCP_URL, "http://127.0.0.1:18791/mcp");
  assert.equal(runtimeEnv.BIONEMO_MCP_UPSTREAM_URL, "https://native.example/mcp");
  assert.deepEqual(processEnv, {
    BIONEMO_MCP_URL: "http://127.0.0.1:18791/mcp",
    BIONEMO_MCP_UPSTREAM_URL: "https://native.example/mcp",
    BIONEMO_ALLOW_INSECURE_MCP: "true",
  });

  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-distinct-mcp-urls-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const templatePath = path.join(root, "template.json");
  const configPath = path.join(root, "state", "openclaw.json");
  const stateDir = path.join(root, "state");
  runtimeEnv.HOME = path.join(root, "home");
  runtimeEnv.BIONEMO_CLIENT_WORKSPACE = path.join(root, "workspace");
  await (await import("node:fs/promises")).copyFile(new URL("../config/openclaw.template.json", import.meta.url), templatePath);
  await launcher.writeRuntimeFiles({ templatePath, configPath, stateDir, origins: ["https://example.test"], env: runtimeEnv });
  const persisted = await readFile(configPath, "utf8");
  assert.match(persisted, /http:\/\/127\.0\.0\.1:18791\/mcp/u);
  assert.equal(persisted.includes("https://native.example/mcp"), false);
  assert.equal(persisted.includes("not-persisted"), false);
  await prepareClients(runtimeEnv);
  const codex = await readFile(path.join(runtimeEnv.HOME, ".codex", "config.toml"), "utf8");
  const claude = await readFile(path.join(runtimeEnv.BIONEMO_CLIENT_WORKSPACE, ".mcp.json"), "utf8");
  assert.match(codex, /http:\/\/127\.0\.0\.1:18791\/mcp/u);
  assert.match(claude, /http:\/\/127\.0\.0\.1:18791\/mcp/u);
  assert.equal(codex.includes("https://native.example/mcp"), false);
  assert.equal(claude.includes("https://native.example/mcp"), false);
  assert.throws(
    () => launcher.configureMcpAdapterEnvironment({}, { upstreamUrl: "https://user:secret@native.example/mcp", adapterUrl: "http://127.0.0.1:18791/mcp", processEnv: {} }),
    /credentials/u,
  );
});

test("an explicit NVIDIA BioNeMo backend does not also expose the incompatible MCP contracts", () => {
  const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [...EXACT_TOOL_NAMES], deny: ["bundle-mcp"] } };
  const state = configureOpenClaw(config, {
    BIONEMO_BACKEND: "nvidia",
    NVIDIA_API_KEY: "n",
    BIONEMO_MCP_API_KEY: "m",
  });
  assert.equal(state.modelBackend, "nvidia");
  assert.deepEqual(config.mcp.servers, {});
  assert.deepEqual(config.tools.alsoAllow, EXACT_TOOL_NAMES);
  assert.equal(config.tools.deny.includes("bundle-mcp"), true);
});

test("Token Factory models retain aliases, credential placeholders, and AGENT_MODEL overrides", () => {
  const configured = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  configureOpenClaw(configured, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "do-not-persist", AGENT_MODEL: "DEEPSEEK-AI/deepseek-v4-pro" });
  assert.equal(configured.agents.defaults.model.primary, "tokenfactory/deepseek-ai/DeepSeek-V4-Pro");
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
  assert.match(codex, /\[mcp_servers\.tavily_web\]/u);
  assert.match(claude, /\$\{BIONEMO_MCP_API_KEY\}/u);
  assert.match(claude, /"tavily_web"/u);
  assert.doesNotMatch(claude, /"tavily"\s*:/u);
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
