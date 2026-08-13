import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { EXAMPLE_SESSIONS, pinAndVerifyExampleSessions, seedExampleSessions } from "../runtime/example-sessions.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";

function minimalConfig(workspace) {
  return {
    gateway: {
      mode: "local",
      bind: "lan",
      auth: { mode: "token", token: "${OPENCLAW_GATEWAY_TOKEN}" },
      controlUi: { enabled: true, root: "/app/dist/control-ui", allowedOrigins: ["http://127.0.0.1:18789"] },
    },
    agents: {
      defaults: { workspace, model: { primary: "setup/setup-required", fallbacks: [] }, skipBootstrap: true },
      list: [{ id: "bionemo", default: true, name: "BioNeMo Research Agent", workspace, skills: [] }],
    },
    models: {
      mode: "merge",
      providers: {
        setup: {
          baseUrl: "http://127.0.0.1:18790/v1",
          apiKey: "setup-required-local-only",
          api: "openai-completions",
          models: [{ id: "setup-required", name: "Setup required", reasoning: false, input: ["text"], contextWindow: 32768, maxTokens: 1024 }],
        },
      },
    },
    plugins: { enabled: false, allow: [], deny: [], load: { paths: [] }, entries: {} },
  };
}

test("four stable ready examples map one-to-one to the baked notebooks", () => {
  assert.equal(EXAMPLE_SESSIONS.length, 4);
  assert.equal(new Set(EXAMPLE_SESSIONS.map(({ key }) => key)).size, 4);
  assert.equal(new Set(EXAMPLE_SESSIONS.map(({ label }) => label)).size, 4);
  assert.equal(EXAMPLE_SESSIONS.every(({ key }) => key.startsWith("agent:bionemo:dashboard:")), true);
  assert.deepEqual(EXAMPLE_SESSIONS.map(({ label }) => label), [
    "Example 1 · Research-first EGFR",
    "Example 2 · Compare protein structures",
    "Example 3 · Optimize ligand complex",
    "Example 4 · Batch-fold five proteins",
  ]);
});

test("native seeding sends no task, message, model, credential, or synthetic output", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-example-seed-unit-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const configPath = path.join(root, "openclaw.json");
  await writeFile(configPath, JSON.stringify(minimalConfig(path.join(root, "workspace"))));
  const ids = new Map();
  const calls = [];
  const createSession = async (params) => {
    calls.push(params);
    const sessionId = ids.get(params.key) || `stable-${ids.size + 1}`;
    ids.set(params.key, sessionId);
    return { ok: true, key: params.key, entry: { sessionId } };
  };
  const first = await seedExampleSessions({ configPath, createSession });
  const second = await seedExampleSessions({ configPath, createSession });
  assert.deepEqual(first, second);
  assert.equal(calls.length, 8);
  for (const call of calls) {
    assert.deepEqual(Object.keys(call).sort(), ["agentId", "cfg", "key", "label"]);
    assert.equal(Object.hasOwn(call, "task"), false);
    assert.equal(Object.hasOwn(call, "message"), false);
    assert.equal(Object.hasOwn(call, "model"), false);
  }
});

test("gateway reconciliation pins only drifted examples and verifies sessions.list metadata", async () => {
  const rows = EXAMPLE_SESSIONS.map(({ key, label }, index) => ({ key, label, pinned: index !== 0, hasActiveRun: false }));
  const patches = [];
  const instances = [];
  class FakeGatewayClient {
    static async connect(options) {
      assert.equal(options.url, "ws://127.0.0.1:18789");
      assert.equal(options.token, "x".repeat(24));
      const instance = new FakeGatewayClient();
      instances.push(instance);
      return instance;
    }
    start() { this.started = true; }
    async waitForReady() { assert.equal(this.started, true); }
    stop() { this.stopped = true; }
    async listSessions() { return { sessions: rows.map((row) => ({ ...row })) }; }
    async patchSession(patch) {
      patches.push(patch);
      const row = rows.find(({ key }) => key === patch.key);
      Object.assign(row, { label: patch.label, pinned: patch.pinned });
      return { ok: true };
    }
  }
  const result = await pinAndVerifyExampleSessions({
    port: 18789,
    token: "x".repeat(24),
    GatewayChatClient: FakeGatewayClient,
    timeoutMs: 1_000,
  });
  assert.equal(result.length, 4);
  assert.deepEqual(patches, [{
    key: EXAMPLE_SESSIONS[0].key,
    agentId: "bionemo",
    label: EXAMPLE_SESSIONS[0].label,
    pinned: true,
  }]);
  assert.equal(instances.every(({ stopped }) => stopped), true);
});

test("exact pinned OpenClaw creates four header-only sessions idempotently", { timeout: 120_000 }, async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-example-seed-pinned-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const stateDir = path.join(root, "state");
  const workspace = path.join(root, "workspace");
  const configPath = path.join(stateDir, "openclaw.json");
  await mkdir(stateDir, { recursive: true });
  await mkdir(workspace, { recursive: true });
  await writeFile(configPath, JSON.stringify(minimalConfig(workspace)), { mode: 0o600 });
  const moduleUrl = new URL("../runtime/example-sessions.mjs", import.meta.url).href;
  const script = [
    `import { seedExampleSessions } from ${JSON.stringify(moduleUrl)};`,
    `const options={configPath:${JSON.stringify(configPath)},distRoot:"/app/dist"};`,
    "const first=await seedExampleSessions(options);",
    "const second=await seedExampleSessions(options);",
    "process.stdout.write(JSON.stringify({first,second}));",
  ].join("\n");
  const recipeRoot = path.resolve(new URL("../", import.meta.url).pathname);
  const seeded = await execFileAsync("docker", [
    "run", "--rm", "--network", "none",
    "--user", `${process.getuid()}:${process.getgid()}`,
    "--volume", `${root}:${root}`,
    "--volume", `${recipeRoot}:${recipeRoot}:ro`,
    "--env", `OPENCLAW_STATE_DIR=${stateDir}`,
    "--env", `OPENCLAW_CONFIG_PATH=${configPath}`,
    "--entrypoint", "node",
    PINNED_IMAGE,
    "--input-type=module", "--eval", script,
  ]);
  const result = JSON.parse(seeded.stdout);
  assert.deepEqual(result.first, result.second);

  const storePath = path.join(stateDir, "agents", "bionemo", "sessions", "sessions.json");
  const store = JSON.parse(await readFile(storePath, "utf8"));
  assert.deepEqual(Object.keys(store).sort(), EXAMPLE_SESSIONS.map(({ key }) => key).sort());
  assert.equal((await stat(storePath)).mode & 0o777, 0o600);
  for (const definition of EXAMPLE_SESSIONS) {
    const entry = store[definition.key];
    assert.equal(entry.label, definition.label);
    const transcript = await readFile(entry.sessionFile, "utf8");
    const lines = transcript.trimEnd().split("\n").map(JSON.parse);
    assert.equal(lines.length, 1);
    assert.deepEqual({ type: lines[0].type, version: lines[0].version, id: lines[0].id }, { type: "session", version: 3, id: entry.sessionId });
    assert.equal(Object.hasOwn(lines[0], "role"), false);
    assert.equal(Object.hasOwn(lines[0], "message"), false);
    assert.equal((await stat(entry.sessionFile)).mode & 0o777, 0o600);
  }
});
