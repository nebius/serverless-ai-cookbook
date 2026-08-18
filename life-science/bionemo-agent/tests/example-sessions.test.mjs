import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  NOTEBOOK_EXAMPLE_SESSIONS,
  WORKBENCH_EXAMPLE_SESSIONS,
} from "../runtime/example-session-catalog.mjs";
import {
  EXAMPLE_SESSIONS,
  buildExampleStarterText,
  pinAndVerifyExampleSessions,
  seedExampleSessions,
} from "../runtime/example-sessions.mjs";

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

test("eleven stable ready examples include four notebook workflows and seven bounded workbench tours", () => {
  assert.equal(EXAMPLE_SESSIONS.length, 11);
  assert.equal(NOTEBOOK_EXAMPLE_SESSIONS.length, 4);
  assert.equal(WORKBENCH_EXAMPLE_SESSIONS.length, 7);
  assert.equal(NOTEBOOK_EXAMPLE_SESSIONS.every(({ draftSeedGeneration }) => draftSeedGeneration === 1), true);
  assert.equal(WORKBENCH_EXAMPLE_SESSIONS.every(({ draftSeedGeneration }) => draftSeedGeneration === 2), true);
  assert.equal(new Set(EXAMPLE_SESSIONS.map(({ key }) => key)).size, 11);
  assert.equal(new Set(EXAMPLE_SESSIONS.map(({ label }) => label)).size, 11);
  assert.equal(EXAMPLE_SESSIONS.every(({ key }) => key.startsWith("agent:bionemo:dashboard:")), true);
  assert.deepEqual(EXAMPLE_SESSIONS.map(({ label }) => label), [
    "Example 1 · Research-first EGFR",
    "Example 2 · Compare protein structures",
    "Example 3 · Optimize ligand complex",
    "Example 4 · Batch-fold five proteins",
    "Example 5 · Tour the workbench",
    "Example 6 · Understand skills",
    "Example 7 · Browse ClawBio catalog",
    "Example 8 · Run ClawBio GWAS demo",
    "Example 9 · Research with Tavily",
    "Example 10 · List BioNeMo models",
    "Example 11 · Optimize a ligand directly",
  ]);
  for (const definition of NOTEBOOK_EXAMPLE_SESSIONS) {
    assert.equal(
      buildExampleStarterText(definition).includes(`](.${definition.notebookPath})`),
      true,
    );
  }
  for (const definition of WORKBENCH_EXAMPLE_SESSIONS) {
    const starter = buildExampleStarterText(definition);
    assert.equal(Object.hasOwn(definition, "notebookPath"), false);
    assert.doesNotMatch(starter, /Open the guided notebook/u);
    assert.match(starter, /source-owned starter has no executable notebook/u);
  }
  assert.deepEqual(WORKBENCH_EXAMPLE_SESSIONS.map(({ surface }) => surface), [
    "openclaw",
    "skills",
    "clawbio-readonly",
    "clawbio-demo",
    "tavily",
    "bionemo-model-inventory",
    "bionemo-molmim",
  ]);
  assert.match(
    EXAMPLE_SESSIONS.find(({ slug }) => slug === "tavily-public-research").prompt,
    /include_domains exactly to \["rcsb\.org", "uniprot\.org"\]/u,
  );
  assert.match(
    EXAMPLE_SESSIONS.find(({ slug }) => slug === "tavily-public-research").prompt,
    /No direct UniProt source was returned by this bounded search\./u,
  );
});

test("new workbench prompts preserve exact bounded no-run and exactly-once contracts", () => {
  const [tour, skills, catalog, demo, tavily, inventory, molmim] = WORKBENCH_EXAMPLE_SESSIONS;
  for (const definition of [tour, skills]) assert.match(definition.prompt, /Do not call any tool\./u);
  assert.match(tour.prompt, /If bionemo_models__\* tools are displayed/u);
  assert.match(tour.prompt, /complete adapted MCP compute surface for all 16 inventory services/u);
  assert.match(tour.prompt, /bionemo_models_list is the sanitized read-only inventory wrapper when displayed/u);
  assert.match(tour.prompt, /without exposing credentials, cross-job listing, host-local staging, or upstream clawbio_\* compatibility names/u);

  assert.match(catalog.prompt, /Call clawbio__list_skills exactly once with query="gwas"/u);
  assert.match(catalog.prompt, /call clawbio__describe_skill exactly once with name="gwas-lookup"/u);
  assert.match(catalog.prompt, /Do not call clawbio__run_skill/u);
  assert.match(catalog.prompt, /demo_runnable_in_image/u);

  assert.match(demo.prompt, /Call clawbio__describe_skill exactly once with name="gwas-lookup"/u);
  assert.match(demo.prompt, /call clawbio__run_skill exactly once with skill="gwas-lookup" and demo=true/u);
  assert.match(demo.prompt, /only if it returns demo_runnable_in_image=true/u);
  assert.match(demo.prompt, /do not retry or duplicate the demo/u);

  assert.match(tavily.prompt, /configured Tavily MCP search tool exactly once/u);
  assert.match(tavily.prompt, /basic search depth, at most five results/u);
  assert.match(tavily.prompt, /stop without substituting another tool or inventing citations/u);
  assert.doesNotMatch(tavily.prompt, /tavily_web__|tavily__|search__search/u);

  assert.match(inventory.prompt, /Call bionemo_models_list exactly once with no arguments/u);
  assert.match(inventory.prompt, /Do not call any other tool/u);
  assert.match(inventory.prompt, /submitted no scientific compute or model job/u);
  assert.match(inventory.prompt, /every returned service has a corresponding adapted bionemo_models__\* compute operation/u);
  assert.match(inventory.prompt, /do not retry/u);

  assert.match(molmim.prompt, /Call bionemo_molmim exactly once/u);
  assert.match(molmim.prompt, /num_molecules=2.*particles=2/u);
  assert.match(molmim.prompt, /ack_research_only=true.*ack_no_safety_or_therapeutic_claims=true/u);
  assert.match(molmim.prompt, /Do not call OpenFold3, any other bionemo_\* tool/u);

  for (const definition of WORKBENCH_EXAMPLE_SESSIONS) assert.doesNotMatch(definition.prompt, /clawbio_models__/u);
});

test("native seeding writes one explicit local user starter without starting a run", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-example-seed-unit-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const configPath = path.join(root, "openclaw.json");
  await writeFile(configPath, JSON.stringify(minimalConfig(path.join(root, "workspace"))));
  const ids = new Map();
  const calls = [];
  const transcripts = new Map();
  const createSession = async (params) => {
    calls.push(params);
    const sessionId = ids.get(params.key) || `stable-${ids.size + 1}`;
    ids.set(params.key, sessionId);
    const sessionFile = path.join(root, `${sessionId}.jsonl`);
    if (!transcripts.has(sessionFile)) transcripts.set(sessionFile, { sessionId, entries: [], rewrites: 0 });
    return { ok: true, key: params.key, entry: { sessionId, sessionFile } };
  };
  class FakeSessionManager {
    static open(sessionFile) {
      const state = transcripts.get(sessionFile);
      assert.ok(state);
      return {
        getSessionId: () => state.sessionId,
        getEntries: () => state.entries.map((entry) => structuredClone(entry)),
        appendMessage: (message) => state.entries.push({ type: "message", message: structuredClone(message) }),
        rewriteFile: () => { state.rewrites += 1; },
      };
    }
  }
  const first = await seedExampleSessions({ configPath, createSession, SessionManager: FakeSessionManager });
  const second = await seedExampleSessions({ configPath, createSession, SessionManager: FakeSessionManager });
  assert.deepEqual(first, second);
  assert.equal(calls.length, EXAMPLE_SESSIONS.length * 2);
  for (const call of calls) {
    assert.deepEqual(Object.keys(call).sort(), ["agentId", "cfg", "key", "label"]);
    assert.equal(Object.hasOwn(call, "task"), false);
    assert.equal(Object.hasOwn(call, "message"), false);
    assert.equal(Object.hasOwn(call, "model"), false);
  }
  for (const definition of EXAMPLE_SESSIONS) {
    const sessionId = ids.get(definition.key);
    const state = transcripts.get(path.join(root, `${sessionId}.jsonl`));
    assert.equal(state.rewrites, 1);
    assert.deepEqual(state.entries, [{
      type: "message",
      message: {
        role: "user",
        content: [{ type: "text", text: buildExampleStarterText(definition) }],
      },
    }]);
    assert.match(state.entries[0].message.content[0].text, /^# STATIC STARTER — NOT EXECUTED\n/u);
  }
});

test("native seeding preserves a nonempty user transcript without inserting a starter", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-example-seed-preserve-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const configPath = path.join(root, "openclaw.json");
  await writeFile(configPath, JSON.stringify(minimalConfig(path.join(root, "workspace"))));
  const states = new Map(EXAMPLE_SESSIONS.map((definition, index) => [definition.key, {
    sessionId: `preserved-${index}`,
    sessionFile: path.join(root, `preserved-${index}.jsonl`),
    entries: [{ type: "message", message: { role: "user", content: [{ type: "text", text: "Existing user work" }] } }],
  }]));
  class FakeSessionManager {
    static open(sessionFile) {
      const state = [...states.values()].find((candidate) => candidate.sessionFile === sessionFile);
      return {
        getSessionId: () => state.sessionId,
        getEntries: () => structuredClone(state.entries),
        appendMessage: () => assert.fail("must not append to a nonempty transcript"),
        rewriteFile: () => assert.fail("must not rewrite a nonempty transcript"),
      };
    }
  }
  await seedExampleSessions({
    configPath,
    SessionManager: FakeSessionManager,
    createSession: async ({ key }) => {
      const state = states.get(key);
      return { ok: true, key, entry: { sessionId: state.sessionId, sessionFile: state.sessionFile } };
    },
  });
  assert.equal([...states.values()].every(({ entries }) => entries[0].message.content[0].text === "Existing user work"), true);
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
    async listSessions(params) {
      assert.deepEqual(params, {
        agentId: "bionemo",
        limit: 50,
        includeGlobal: true,
        includeUnknown: true,
      });
      return { sessions: rows.map((row) => ({ ...row })) };
    }
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
  assert.equal(result.length, EXAMPLE_SESSIONS.length);
  assert.deepEqual(patches, [{
    key: EXAMPLE_SESSIONS[0].key,
    agentId: "bionemo",
    label: EXAMPLE_SESSIONS[0].label,
    pinned: true,
  }]);
  assert.equal(instances.every(({ stopped }) => stopped), true);
});

test("exact pinned OpenClaw creates eleven visible local starter sessions idempotently", { timeout: 120_000 }, async (t) => {
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
    assert.equal(lines.length, 2);
    assert.deepEqual({ type: lines[0].type, version: lines[0].version, id: lines[0].id }, { type: "session", version: 3, id: entry.sessionId });
    assert.equal(Object.hasOwn(lines[0], "role"), false);
    assert.equal(Object.hasOwn(lines[0], "message"), false);
    assert.equal(lines[1].type, "message");
    assert.equal(lines[1].parentId, null);
    assert.deepEqual(lines[1].message, {
      role: "user",
      content: [{ type: "text", text: buildExampleStarterText(definition) }],
    });
    assert.match(lines[1].message.content[0].text, /^# STATIC STARTER — NOT EXECUTED\n/u);
    assert.equal(lines.some(({ message }) => message?.role === "assistant" || message?.role === "tool"), false);
    assert.equal(Object.hasOwn(lines[1].message, "model"), false);
    assert.equal(Object.hasOwn(lines[1].message, "toolCall"), false);
    assert.equal(Object.hasOwn(lines[1].message, "toolResult"), false);
    assert.equal((await stat(entry.sessionFile)).mode & 0o777, 0o600);
  }
});
