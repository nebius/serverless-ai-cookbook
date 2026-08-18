import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
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

const LEGACY_FIRST_DEFINITION = Object.freeze({
  title: "Research-first EGFR drug discovery demo",
  description: "Optional Tavily evidence gathering followed by a bounded, cross-backend structure and molecule workflow.",
  steps: Object.freeze([
    "Optionally research current public EGFR/gefitinib evidence with Tavily",
    "Characterize the fixed public EGFR kinase sequence with OpenFold2",
    "Optimize two gefitinib-derived candidates with MolMIM",
    "Model the selected candidate with the same EGFR sequence using OpenFold3",
    "Review citations, confidence summaries, artifacts, and limitations",
  ]),
  notebookPath: "/plugins/bionemo/notebooks/egfr-research-drug-demo",
  prompt: "Run the backend-neutral research-first EGFR demo. Call bionemo_research_drug_demo exactly once with use_tavily=true, ack_research_only=true, ack_non_clinical=true, ack_non_commercial=true, ack_aup_accepted=true, and ack_no_safety_or_therapeutic_claims=true. I explicitly accept those five research-only acknowledgements. Do not call its Tavily, OpenFold2, MolMIM, or OpenFold3 steps separately. Report whether optional Tavily research ran, cite its sources if present, summarize every model step and confidence value, include every artifact viewerMarkdown link verbatim, and state the scientific limitations.",
});

function buildLegacyStarterText(definition) {
  const steps = definition.steps.map((step, index) => `${index + 1}. ${step}`).join("\n");
  return `# STATIC STARTER — NOT EXECUTED

This is a local template baked into the BioNeMo image. No model, tool, MCP call, remote job, or result has been run or produced. The fenced prompt below is inert reference text; execute it only after you explicitly send it in a later user turn.

## ${definition.title}

${definition.description}

## Workflow steps

${steps}

Notebook: [Open the guided notebook](.${definition.notebookPath})

## Exact reviewed prompt

\`\`\`text
${definition.prompt}
\`\`\``;
}

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

test("eleven stable ready examples read like relatable user requests", () => {
  assert.equal(EXAMPLE_SESSIONS.length, 11);
  assert.equal(NOTEBOOK_EXAMPLE_SESSIONS.length, 4);
  assert.equal(WORKBENCH_EXAMPLE_SESSIONS.length, 7);
  assert.equal(NOTEBOOK_EXAMPLE_SESSIONS.every(({ draftSeedGeneration }) => draftSeedGeneration === 1), true);
  assert.equal(WORKBENCH_EXAMPLE_SESSIONS.every(({ draftSeedGeneration }) => draftSeedGeneration === 2), true);
  assert.equal(new Set(EXAMPLE_SESSIONS.map(({ key }) => key)).size, 11);
  assert.equal(new Set(EXAMPLE_SESSIONS.map(({ label }) => label)).size, 11);
  assert.equal(EXAMPLE_SESSIONS.every(({ key }) => key.startsWith("agent:bionemo:dashboard:")), true);
  assert.deepEqual(EXAMPLE_SESSIONS.map(({ label }) => label), [
    "Example 1 · Explore EGFR and gefitinib",
    "Example 2 · Compare crambin predictions",
    "Example 3 · Improve a gefitinib-like ligand",
    "Example 4 · Fold five public proteins",
    "Example 5 · Discover the workbench",
    "Example 6 · Understand agent skills",
    "Example 7 · Find a GWAS workflow",
    "Example 8 · Try a GWAS lookup",
    "Example 9 · Compare PDB and UniProt",
    "Example 10 · Check available models",
    "Example 11 · Explore gefitinib analogs",
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
    assert.match(starter, /opens directly in chat/u);
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
  const prompts = EXAMPLE_SESSIONS.map(({ prompt }) => prompt);
  assert.equal(new Set(prompts).size, 11);
  for (const definition of EXAMPLE_SESSIONS) {
    const visibleCopy = [definition.label, definition.title, definition.description, ...definition.steps, definition.prompt].join("\n");
    assert.doesNotMatch(visibleCopy, /\b(?:bionemo_|bionemo_models__|clawbio__|tavily_web__)/u);
    assert.doesNotMatch(visibleCopy, /\b(?:ack_[a-z_]+|input_file|viewerMarkdown|demo_runnable_in_image)\b/u);
    assert.doesNotMatch(visibleCopy, /\bcall\s+[a-z0-9_*]+\s+exactly\s+once\b/iu);
    assert.doesNotMatch(visibleCopy, /Do not call/u);
    assert.ok(definition.prompt.length >= 180, `${definition.slug} should provide enough user context`);
  }
});

test("example questions express outcomes while hidden routing remains out of the copy", () => {
  const [tour, skills, catalog, demo, tavily, inventory, molmim] = WORKBENCH_EXAMPLE_SESSIONS;
  assert.match(tour.prompt, /I’m new to this BioNeMo research workspace/u);
  assert.match(tour.prompt, /what I can do here/u);
  assert.match(tour.prompt, /don’t start a scientific job/u);

  assert.match(skills.prompt, /^How do the packaged skills/u);
  assert.match(skills.prompt, /learning about a capability is different from running it/u);
  assert.match(skills.prompt, /don’t run anything yet/u);

  assert.match(catalog.prompt, /public dbSNP variant such as rs3798220/u);
  assert.match(catalog.prompt, /what reports, tables, figures, and reproducibility files/u);
  assert.match(catalog.prompt, /don’t run the lookup/u);

  assert.match(demo.prompt, /generate the bundled offline variant report/u);
  assert.match(demo.prompt, /GWAS, PheWAS, eQTL, and fine-mapping/u);
  assert.match(demo.prompt, /do not interpret it as diagnosis/u);

  assert.match(tavily.prompt, /only `rcsb\.org` and `uniprot\.org`/u);
  assert.match(tavily.prompt, /up to five current, authoritative public pages/u);
  assert.match(tavily.prompt, /title and URL of every page/u);

  assert.match(inventory.prompt, /^Which BioNeMo models are available right now\?/u);
  assert.match(inventory.prompt, /public ID, display name, family, and readiness/u);
  assert.match(inventory.prompt, /whether checking the inventory launches any scientific computation/u);

  assert.match(molmim.prompt, /^Starting from gefitinib SMILES/u);
  assert.match(molmim.prompt, /two similar candidate molecules optimized for QED/u);
  assert.match(molmim.prompt, /at least 0\.7 similarity/u);

  const crambin = EXAMPLE_SESSIONS.find(({ slug }) => slug === "compare-protein-structures");
  assert.match(crambin.prompt, /^Please compare OpenFold2 and OpenFold3 predictions/u);
  assert.match(crambin.prompt, /point out the important similarities and differences/u);
  assert.match(crambin.prompt, /TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN/u);
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
    assert.match(state.entries[0].message.content[0].text, /^# EXAMPLE — READY TO TRY\n/u);
    assert.match(state.entries[0].message.content[0].text, /## Example question\n/u);
  }
});

test("native seeding migrates only an exact prior image-owned starter", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-example-seed-migrate-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const configPath = path.join(root, "openclaw.json");
  await writeFile(configPath, JSON.stringify(minimalConfig(path.join(root, "workspace"))));

  const legacyText = buildLegacyStarterText(LEGACY_FIRST_DEFINITION);
  assert.equal(
    createHash("sha256").update(legacyText, "utf8").digest("hex"),
    "d118986d5b39c9704b0190734637bec484d2067568cf01a362c821d0fc9e6900",
  );
  const first = EXAMPLE_SESSIONS[0];
  const states = new Map();
  for (const [index, definition] of EXAMPLE_SESSIONS.entries()) {
    const sessionId = `migration-${index + 1}`;
    const sessionFile = path.join(root, `${sessionId}.jsonl`);
    const text = definition.key === first.key ? legacyText : `Preserved user work ${index + 1}`;
    const entry = {
      type: "message",
      id: `message-${index + 1}`,
      parentId: null,
      timestamp: "2026-08-18T12:00:00.000Z",
      message: { role: "user", content: [{ type: "text", text }] },
    };
    const header = {
      type: "session",
      version: 3,
      id: sessionId,
      timestamp: "2026-08-18T12:00:00.000Z",
      cwd: "/workspace/agent",
    };
    await writeFile(sessionFile, `${JSON.stringify(header)}\n${JSON.stringify(entry)}\n`, { mode: 0o600 });
    states.set(definition.key, { sessionId, sessionFile, entry });
  }
  class FakeSessionManager {
    static open(sessionFile) {
      const state = [...states.values()].find((candidate) => candidate.sessionFile === sessionFile);
      assert.ok(state);
      return {
        getSessionId: () => state.sessionId,
        getSessionFile: () => state.sessionFile,
        getEntries: () => [structuredClone(state.entry)],
        appendMessage: () => assert.fail("migration must not append a second entry"),
        rewriteFile: () => assert.fail("migration must use its exact atomic replacement"),
      };
    }
  }
  const createSession = async ({ key }) => {
    const state = states.get(key);
    return { ok: true, key, entry: { sessionId: state.sessionId, sessionFile: state.sessionFile } };
  };

  await seedExampleSessions({ configPath, createSession, SessionManager: FakeSessionManager });
  const migrated = (await readFile(states.get(first.key).sessionFile, "utf8")).trimEnd().split("\n").map(JSON.parse);
  assert.equal(migrated.length, 2);
  assert.equal(migrated[0].id, states.get(first.key).sessionId);
  assert.equal(migrated[1].id, states.get(first.key).entry.id);
  assert.equal(migrated[1].timestamp, states.get(first.key).entry.timestamp);
  assert.equal(migrated[1].message.content[0].text, buildExampleStarterText(first));
  for (const definition of EXAMPLE_SESSIONS.slice(1)) {
    const body = await readFile(states.get(definition.key).sessionFile, "utf8");
    assert.match(body, new RegExp(`Preserved user work ${EXAMPLE_SESSIONS.indexOf(definition) + 1}`, "u"));
  }

  const afterFirstPass = await readFile(states.get(first.key).sessionFile, "utf8");
  states.get(first.key).entry = migrated[1];
  await seedExampleSessions({ configPath, createSession, SessionManager: FakeSessionManager });
  assert.equal(await readFile(states.get(first.key).sessionFile, "utf8"), afterFirstPass);
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
    assert.match(lines[1].message.content[0].text, /^# EXAMPLE — READY TO TRY\n/u);
    assert.equal(lines.some(({ message }) => message?.role === "assistant" || message?.role === "tool"), false);
    assert.equal(Object.hasOwn(lines[1].message, "model"), false);
    assert.equal(Object.hasOwn(lines[1].message, "toolCall"), false);
    assert.equal(Object.hasOwn(lines[1].message, "toolResult"), false);
    assert.equal((await stat(entry.sessionFile)).mode & 0o777, 0o600);
  }

  const exactLegacyEntry = store[EXAMPLE_SESSIONS[0].key];
  const editedEntry = store[EXAMPLE_SESSIONS[1].key];
  const exactLegacyLines = (await readFile(exactLegacyEntry.sessionFile, "utf8")).trimEnd().split("\n").map(JSON.parse);
  const editedLines = (await readFile(editedEntry.sessionFile, "utf8")).trimEnd().split("\n").map(JSON.parse);
  const exactLegacyMessageId = exactLegacyLines[1].id;
  exactLegacyLines[1].message.content[0].text = buildLegacyStarterText(LEGACY_FIRST_DEFINITION);
  editedLines[1].message.content[0].text = `${buildLegacyStarterText(LEGACY_FIRST_DEFINITION)}\nUser edit`;
  await writeFile(exactLegacyEntry.sessionFile, `${exactLegacyLines.map((line) => JSON.stringify(line)).join("\n")}\n`, { mode: 0o600 });
  await writeFile(editedEntry.sessionFile, `${editedLines.map((line) => JSON.stringify(line)).join("\n")}\n`, { mode: 0o600 });

  const migratedRun = await execFileAsync("docker", [
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
  const migratedResult = JSON.parse(migratedRun.stdout);
  assert.deepEqual(migratedResult.first, migratedResult.second);
  const migratedLegacyLines = (await readFile(exactLegacyEntry.sessionFile, "utf8")).trimEnd().split("\n").map(JSON.parse);
  assert.equal(migratedLegacyLines[1].id, exactLegacyMessageId, "migration preserves the native message identity");
  assert.equal(migratedLegacyLines[1].message.content[0].text, buildExampleStarterText(EXAMPLE_SESSIONS[0]));
  const preservedEdit = await readFile(editedEntry.sessionFile, "utf8");
  assert.match(preservedEdit, /User edit/u);
  assert.doesNotMatch(preservedEdit, new RegExp(buildExampleStarterText(EXAMPLE_SESSIONS[1]).slice(0, 40), "u"));
});
