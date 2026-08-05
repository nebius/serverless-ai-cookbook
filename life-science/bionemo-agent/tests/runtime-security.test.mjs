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

test("plugin registers exactly the manifest-declared 13 tools", () => {
  const api = fakeApi();
  plugin.register(api);
  assert.deepEqual(api.captured.tools.map((tool) => tool.name), EXACT_TOOL_NAMES);
  assert.deepEqual(manifest.contracts.tools, EXACT_TOOL_NAMES);
  assert.equal(api.captured.tools.every((tool) => tool.parameters.additionalProperties === false), true);
  assert.equal(api.captured.hooks.length, 1);
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
  const script = html.match(/<script nonce="[^"]+">([\s\S]+)<\/script>/u)?.[1];
  assert.ok(script);
  assert.doesNotThrow(() => new vm.Script(script));
});

test("readiness reveals only credential presence", async () => {
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
  assert.deepEqual(JSON.parse(body).configured, { nvidia: true, llm: true, gateway: true });
});

test("launcher validates secrets without printing values and parses only safe origins", () => {
  assert.equal(launcher.requireEnvironment({ NEBIUS_API_KEY: "n", NVIDIA_API_KEY: "v", AUTH_TOKEN: "a".repeat(24) }), "a".repeat(24));
  assert.equal(launcher.requireEnvironment({ NEBIUS_API_KEY: "n", NGC_API_KEY: "v", AUTH_TOKEN: "a".repeat(24) }), "a".repeat(24));
  assert.throws(() => launcher.requireEnvironment({}), /NEBIUS_API_KEY.*NVIDIA_API_KEY.*AUTH_TOKEN/u);
  assert.throws(() => launcher.requireEnvironment({ NEBIUS_API_KEY: "secret-one", NVIDIA_API_KEY: "secret-two", AUTH_TOKEN: "short" }), /at least 24/u);
  assert.equal(launcher.safeOrigin("https://example.test"), "https://example.test");
  assert.throws(() => launcher.safeOrigin("https://user:pass@example.test"), /without credentials/u);
  assert.throws(() => launcher.safeOrigin("https://example.test/path"), /without credentials/u);
  assert.match("https://bounded-name.trycloudflare.com", new RegExp(launcher.CLOUDFLARED_URL_PATTERN));
});

test("Serverless launch binds exactly one matching NVIDIA MysteryBox payload", async () => {
  const script = await readFile(new URL("../scripts/run_serverless_endpoint.sh", import.meta.url), "utf8");
  assert.match(script, /Set only one of NVIDIA_API_KEY_SECRET or NGC_API_KEY_SECRET/u);
  assert.match(script, /--env-secret "NVIDIA_API_KEY=\$NVIDIA_API_KEY_SECRET"/u);
  assert.match(script, /--env-secret "NGC_API_KEY=\$NGC_API_KEY_SECRET"/u);
  assert.equal(script.includes("--env \"NVIDIA_API_KEY="), false);
  assert.equal(script.includes("--env \"NGC_API_KEY="), false);
});

test("runtime config and exec approvals persist placeholders, never secret values", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-runtime-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const templatePath = path.join(root, "template.json");
  const configPath = path.join(root, "state", "openclaw.json");
  const stateDir = path.join(root, "state");
  await (await import("node:fs/promises")).writeFile(templatePath, JSON.stringify({ gateway: { controlUi: { allowedOrigins: [] } }, models: { providers: { tokenfactory: { apiKey: "${NEBIUS_API_KEY}" } } } }));
  await launcher.writeRuntimeFiles({ templatePath, configPath, stateDir, origins: ["https://example.test"] });
  const config = await readFile(configPath, "utf8");
  const approvals = JSON.parse(await readFile(path.join(stateDir, "exec-approvals.json"), "utf8"));
  assert.match(config, /\$\{NEBIUS_API_KEY\}/u);
  assert.equal(config.includes("secret-value"), false);
  assert.deepEqual(approvals.defaults, { security: "deny", ask: "off", askFallback: "deny", autoAllowSkills: false });
  assert.deepEqual(approvals.agents.bionemo.allowlist, []);
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
  assert.equal(config.models.providers.tokenfactory.apiKey, "${NEBIUS_API_KEY}");
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
  assert.match(config, /tokenfactory\/zai-org\/GLM-5\.1/u);
  assert.equal((await readFile(new URL("../vendor/bionemo-agent-toolkit/UPSTREAM_COMMIT", import.meta.url), "utf8")).trim(), TOOLKIT_COMMIT);
});
