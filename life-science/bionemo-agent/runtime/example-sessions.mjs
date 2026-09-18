import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { NOTEBOOK_CATALOG, notebookViewPath } from "../openclaw-plugin/src/notebooks.mjs";

export const PINNED_OPENCLAW_SESSION_RUNTIME = Object.freeze({
  createPrefix: "session-create-service-",
  createHash: "efccd04ff0834d1e4aaf6ae6c2014e4e804475b0fd3f3dd74e6288c6da8e4e74",
  gatewayPrefix: "gateway-chat-",
  gatewayHash: "51ff1f38254a3ef322c5d658df7e5f96f76d969f04e778e7b21333d8765a9f4f",
  managerPrefix: "session-manager-BC-U4J87",
  managerHash: "d06b4ccb169263554ab112edd7feed1af85d1a5029e0b27e9de1e59f51de9e57",
});

export const EXAMPLE_SESSIONS = Object.freeze(NOTEBOOK_CATALOG.map((entry) => Object.freeze({
  key: entry.sessionKey,
  agentId: "bionemo",
  label: entry.sessionLabel,
  title: entry.title,
  description: entry.description,
  steps: entry.steps,
  notebookPath: notebookViewPath(entry.slug),
  prompt: entry.prompt,
  slug: entry.slug,
})));

export function buildExampleStarterText(definition) {
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

async function pinnedChunk(distRoot, prefix, expectedHash) {
  const names = (await readdir(distRoot)).filter((name) => name.startsWith(prefix) && name.endsWith(".js"));
  if (names.length !== 1) throw new Error(`Expected exactly one pinned OpenClaw ${prefix} chunk`);
  const filePath = path.join(distRoot, names[0]);
  const body = await readFile(filePath);
  const actualHash = createHash("sha256").update(body).digest("hex");
  if (actualHash !== expectedHash) throw new Error(`Pinned OpenClaw ${prefix} compatibility hash mismatch`);
  return filePath;
}

async function loadCreateSession(distRoot) {
  const filePath = await pinnedChunk(
    distRoot,
    PINNED_OPENCLAW_SESSION_RUNTIME.createPrefix,
    PINNED_OPENCLAW_SESSION_RUNTIME.createHash,
  );
  const runtime = await import(pathToFileURL(filePath).href);
  if (typeof runtime.n !== "function") throw new Error("Pinned OpenClaw createGatewaySession export is unavailable");
  return runtime.n;
}

async function loadGatewayClient(distRoot) {
  const filePath = await pinnedChunk(
    distRoot,
    PINNED_OPENCLAW_SESSION_RUNTIME.gatewayPrefix,
    PINNED_OPENCLAW_SESSION_RUNTIME.gatewayHash,
  );
  const runtime = await import(pathToFileURL(filePath).href);
  if (typeof runtime.GatewayChatClient !== "function") throw new Error("Pinned OpenClaw GatewayChatClient export is unavailable");
  return runtime.GatewayChatClient;
}

async function loadSessionManager(distRoot) {
  const filePath = await pinnedChunk(
    distRoot,
    PINNED_OPENCLAW_SESSION_RUNTIME.managerPrefix,
    PINNED_OPENCLAW_SESSION_RUNTIME.managerHash,
  );
  const runtime = await import(pathToFileURL(filePath).href);
  if (typeof runtime.t?.open !== "function") throw new Error("Pinned OpenClaw SessionManager export is unavailable");
  return runtime.t;
}

function validatedConfig(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("OpenClaw configuration is invalid");
  const agents = Array.isArray(value.agents?.list) ? value.agents.list : [];
  if (!agents.some((entry) => entry?.id === "bionemo")) throw new Error("OpenClaw configuration is missing the bionemo agent");
  return value;
}

export async function seedExampleSessions({
  configPath,
  distRoot = "/app/dist",
  createSession,
  SessionManager,
} = {}) {
  if (!configPath) throw new Error("configPath is required to seed BioNeMo example sessions");
  const cfg = validatedConfig(JSON.parse(await readFile(configPath, "utf8")));
  const create = createSession || await loadCreateSession(distRoot);
  const Manager = SessionManager || await loadSessionManager(distRoot);
  const seeded = [];
  for (const definition of EXAMPLE_SESSIONS) {
    // Deliberately omit task, message, model, and all credentials. This creates
    // the native session without starting a model turn or tool invocation.
    const result = await create({
      cfg,
      key: definition.key,
      agentId: definition.agentId,
      label: definition.label,
    });
    if (!result?.ok || result.key !== definition.key || !result.entry?.sessionId) {
      throw new Error(`Could not seed ready example session ${definition.slug}`);
    }
    if (typeof result.entry.sessionFile !== "string" || !result.entry.sessionFile.trim()) {
      throw new Error(`Ready example session ${definition.slug} has no native transcript`);
    }
    const manager = Manager.open(result.entry.sessionFile);
    if (manager.getSessionId() !== result.entry.sessionId) {
      throw new Error(`Ready example session ${definition.slug} transcript identity mismatch`);
    }
    const starter = {
      role: "user",
      content: [{ type: "text", text: buildExampleStarterText(definition) }],
    };
    const entries = manager.getEntries();
    if (entries.length === 0) {
      manager.appendMessage(starter);
      // Pinned SessionManager intentionally buffers a user-only session until
      // an assistant exists. Its native rewrite is the bounded, no-run flush.
      manager.rewriteFile();
    }
    // A nonempty transcript belongs to the user. Never append, overwrite, or
    // branch it during startup; exact starter sessions are naturally idempotent.
    seeded.push(Object.freeze({ key: result.key, sessionId: result.entry.sessionId }));
  }
  return Object.freeze(seeded);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function connectGateway({ GatewayChatClient, url, token, timeoutMs }) {
  const client = await GatewayChatClient.connect({ url, token });
  client.start();
  let timer;
  try {
    await Promise.race([
      client.waitForReady(),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("OpenClaw gateway connection timed out")), timeoutMs); }),
    ]);
    return client;
  } catch (error) {
    client.stop();
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function pinAndVerifyExampleSessions({
  port,
  token,
  distRoot = "/app/dist",
  GatewayChatClient,
  timeoutMs = 60_000,
  retryMs = 250,
} = {}) {
  if (!Number.isInteger(port) || port < 1 || port > 65_535) throw new Error("A valid gateway port is required");
  if (typeof token !== "string" || token.length < 24) throw new Error("A valid gateway token is required");
  const Client = GatewayChatClient || await loadGatewayClient(distRoot);
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    let client;
    try {
      client = await connectGateway({
        GatewayChatClient: Client,
        url: `ws://127.0.0.1:${port}`,
        token,
        timeoutMs: Math.min(3_000, Math.max(1, deadline - Date.now())),
      });
      const before = await client.listSessions({
        agentId: "bionemo",
        limit: 50,
        includeGlobal: true,
        includeUnknown: true,
      });
      const rows = new Map((before?.sessions || []).map((row) => [row.key, row]));
      for (const definition of EXAMPLE_SESSIONS) {
        const current = rows.get(definition.key);
        if (!current) throw new Error(`Seeded example session ${definition.slug} is missing from sessions.list`);
        if (current.label !== definition.label || current.pinned !== true) {
          const patched = await client.patchSession({
            key: definition.key,
            agentId: definition.agentId,
            label: definition.label,
            pinned: true,
          });
          if (patched?.ok !== true) throw new Error(`Could not pin ready example session ${definition.slug}`);
        }
      }
      const after = await client.listSessions({
        agentId: "bionemo",
        limit: 50,
        includeGlobal: true,
        includeUnknown: true,
      });
      const verified = new Map((after?.sessions || []).map((row) => [row.key, row]));
      for (const definition of EXAMPLE_SESSIONS) {
        const row = verified.get(definition.key);
        if (!row || row.label !== definition.label || row.pinned !== true || row.hasActiveRun === true) {
          throw new Error(`Ready example session ${definition.slug} failed sessions.list verification`);
        }
      }
      return Object.freeze(EXAMPLE_SESSIONS.map(({ key, label }) => Object.freeze({ key, label })));
    } catch (error) {
      lastError = error;
    } finally {
      client?.stop();
    }
    if (Date.now() < deadline) await delay(Math.min(retryMs, Math.max(0, deadline - Date.now())));
  }
  throw new Error(`BioNeMo ready example session reconciliation failed: ${lastError?.message || "gateway unavailable"}`);
}

export const __test = { connectGateway, loadCreateSession, loadGatewayClient, loadSessionManager, pinnedChunk, validatedConfig };
