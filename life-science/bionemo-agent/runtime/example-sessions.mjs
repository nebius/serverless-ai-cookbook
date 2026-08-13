import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { NOTEBOOK_CATALOG } from "../openclaw-plugin/src/notebooks.mjs";

export const PINNED_OPENCLAW_SESSION_RUNTIME = Object.freeze({
  createPrefix: "session-create-service-",
  createHash: "efccd04ff0834d1e4aaf6ae6c2014e4e804475b0fd3f3dd74e6288c6da8e4e74",
  gatewayPrefix: "gateway-chat-",
  gatewayHash: "51ff1f38254a3ef322c5d658df7e5f96f76d969f04e778e7b21333d8765a9f4f",
});

export const EXAMPLE_SESSIONS = Object.freeze(NOTEBOOK_CATALOG.map((entry) => Object.freeze({
  key: entry.sessionKey,
  agentId: "bionemo",
  label: entry.sessionLabel,
  prompt: entry.prompt,
  slug: entry.slug,
})));

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
} = {}) {
  if (!configPath) throw new Error("configPath is required to seed BioNeMo example sessions");
  const cfg = validatedConfig(JSON.parse(await readFile(configPath, "utf8")));
  const create = createSession || await loadCreateSession(distRoot);
  const seeded = [];
  for (const definition of EXAMPLE_SESSIONS) {
    // Deliberately omit task, message, model, and all credentials. This invokes
    // OpenClaw's native session/transcript lifecycle without starting a turn.
    const result = await create({
      cfg,
      key: definition.key,
      agentId: definition.agentId,
      label: definition.label,
    });
    if (!result?.ok || result.key !== definition.key || !result.entry?.sessionId) {
      throw new Error(`Could not seed ready example session ${definition.slug}`);
    }
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

export const __test = { connectGateway, loadCreateSession, loadGatewayClient, pinnedChunk, validatedConfig };
