import { createHash, randomUUID } from "node:crypto";
import { lstat, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { EXAMPLE_SESSION_CATALOG } from "./example-session-catalog.mjs";

export const PINNED_OPENCLAW_SESSION_RUNTIME = Object.freeze({
  createPrefix: "session-create-service-",
  createHash: "efccd04ff0834d1e4aaf6ae6c2014e4e804475b0fd3f3dd74e6288c6da8e4e74",
  gatewayPrefix: "gateway-chat-",
  gatewayHash: "51ff1f38254a3ef322c5d658df7e5f96f76d969f04e778e7b21333d8765a9f4f",
  managerPrefix: "session-manager-BC-U4J87",
  managerHash: "d06b4ccb169263554ab112edd7feed1af85d1a5029e0b27e9de1e59f51de9e57",
});

export const EXAMPLE_SESSIONS = EXAMPLE_SESSION_CATALOG;

const LEGACY_STARTER_SHA256 = Object.freeze({
  "egfr-research-drug-demo": "d118986d5b39c9704b0190734637bec484d2067568cf01a362c821d0fc9e6900",
  "compare-protein-structures": "7b1d970f1f9e3469a0b3c5a26cf3967ef6145021431686f0469858f5842c2102",
  "optimize-ligand-complex": "81ad58d1590a96ce2bc0bc5cf0a503f9be2ed25510ec312931689c9e02b96e2d",
  "bulk-openfold2-five-proteins": "b64afa9146142f2152a963509a0e9b66e655fff390614476fe65a6186d56f8f9",
  "openclaw-workbench-tour": "12eaa570d82114f9b80bdd6b30496563a88fab971bf71660ef7ae84f422a2846",
  "openclaw-skill-guidance": "fd2a7a83d2d2a9002e79deaa3b34829fc84a97e3406fe766c8cc17ccf1be7709",
  "clawbio-readonly-catalog": "8ee925c6e8f95acd6c672ceda67af0aadedcf2de786e4a65437976ee23c81e1d",
  "clawbio-gwas-demo": "e1ae102389b1d1817c8125cdd88f7351f1620085189aa569eb445c4f7e66fa7c",
  "tavily-public-research": "700557d592d2154151f84df11161cc382ab6c0d45c4e4cc62c4aaff836b81fbf",
  "bionemo-model-inventory": "8697fb7f67c154331ee50d29252827f40a281d3292f4a174dcd295181888c3a0",
  "molmim-direct-mcp": "79e3d0e2ee286d61a51654a783cadabfccf6b9442f22cf08d317976a1b271938",
});

function exactKeys(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function exactStaticStarterEntry(manager, definition, replacementText) {
  const legacyDigest = LEGACY_STARTER_SHA256[definition.slug];
  if (!legacyDigest) return undefined;
  const entries = manager.getEntries();
  if (!Array.isArray(entries) || entries.length !== 1) return undefined;
  const [entry] = entries;
  if (!exactKeys(entry, ["id", "message", "parentId", "timestamp", "type"])
    || entry.type !== "message" || entry.parentId !== null
    || typeof entry.id !== "string" || !entry.id
    || typeof entry.timestamp !== "string" || !entry.timestamp
    || !exactKeys(entry.message, ["content", "role"])
    || entry.message.role !== "user" || !Array.isArray(entry.message.content)
    || entry.message.content.length !== 1
    || !exactKeys(entry.message.content[0], ["text", "type"])
    || entry.message.content[0].type !== "text"
    || typeof entry.message.content[0].text !== "string") return undefined;
  const text = entry.message.content[0].text;
  if (text === replacementText
    || createHash("sha256").update(text, "utf8").digest("hex") !== legacyDigest) return undefined;

  return entry;
}

async function migrateLegacyStaticStarter({ manager, definition, starter }) {
  const matched = exactStaticStarterEntry(manager, definition, starter.content[0].text);
  if (!matched || typeof manager.getSessionFile !== "function") return false;
  const sessionFile = manager.getSessionFile();
  if (typeof sessionFile !== "string" || !sessionFile) return false;
  const beforeStat = await lstat(sessionFile);
  if (!beforeStat.isFile() || beforeStat.isSymbolicLink() || (beforeStat.mode & 0o777) !== 0o600) return false;
  const before = await readFile(sessionFile, "utf8");
  if (!before.endsWith("\n")) return false;
  const lines = before.slice(0, -1).split("\n");
  if (lines.length !== 2 || lines[1] !== JSON.stringify(matched)) return false;
  let header;
  let entry;
  try {
    header = JSON.parse(lines[0]);
    entry = JSON.parse(lines[1]);
  } catch {
    return false;
  }
  if (!exactKeys(header, ["cwd", "id", "timestamp", "type", "version"])
    || header.type !== "session" || header.version !== 3
    || header.id !== manager.getSessionId()
    || typeof header.cwd !== "string" || typeof header.timestamp !== "string") return false;
  entry.message.content[0].text = starter.content[0].text;
  const replacement = `${lines[0]}\n${JSON.stringify(entry)}\n`;

  const temporary = `${sessionFile}.bionemo-starter-${process.pid}-${randomUUID()}.tmp`;
  await writeFile(temporary, replacement, { encoding: "utf8", flag: "wx", mode: 0o600 });
  try {
    const afterStat = await lstat(sessionFile);
    if (!afterStat.isFile() || afterStat.isSymbolicLink()
      || afterStat.dev !== beforeStat.dev || afterStat.ino !== beforeStat.ino
      || afterStat.size !== beforeStat.size || afterStat.mtimeMs !== beforeStat.mtimeMs
      || await readFile(sessionFile, "utf8") !== before
      || await readFile(temporary, "utf8") !== replacement) return false;
    await rename(temporary, sessionFile);
    return true;
  } finally {
    await rm(temporary, { force: true });
  }
}

export function buildExampleStarterText(definition) {
  const steps = definition.steps.map((step, index) => `${index + 1}. ${step}`).join("\n");
  const companion = definition.notebookPath
    ? `Notebook: [Open the guided notebook](.${definition.notebookPath})`
    : "This example opens directly in chat. Its question stays unsent until you choose to send it.";
  return `# EXAMPLE — READY TO TRY

This example is pre-filled but has not been sent. No model, scientific job, or external request has run. Review or edit the question, then send it when you are ready.

## ${definition.title}

${definition.description}

## What you’ll explore

${steps}

${companion}

## Example question

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
    } else {
      await migrateLegacyStaticStarter({ manager, definition, starter });
    }
    // Every nonempty transcript belongs to the user unless its sole entry is
    // an exact source-owned starter from the immediately preceding image.
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
