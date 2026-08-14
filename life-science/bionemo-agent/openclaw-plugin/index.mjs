import path from "node:path";
import { ArtifactStore, VIEWER_ROUTE_PREFIX } from "./src/artifacts.mjs";
import { NimClient } from "./src/client.mjs";
import { CROSS_BACKEND_TOOL_NAMES, PUBLIC_CATALOG, SKILLS, TOOLKIT_COMMIT, WORKFLOWS } from "./src/catalog.mjs";
import { publicError } from "./src/errors.mjs";
import { NOTEBOOK_ROUTE_PREFIX } from "./src/notebooks.mjs";
import { CerebriumMcpModelClient, TavilySearchClient, selectedResearchBackend } from "./src/research-demo-clients.mjs";
import { resolveSkillInput, resolveWorkflowInput } from "./src/samples.mjs";
import { createUiHandlers } from "./src/ui.mjs";
import { JSON_SCHEMAS, VALIDATORS, normalizeDirectSkillInput } from "./src/validation.mjs";
import { ResearchDrugDemoRunner, WorkflowRunner } from "./src/workflows.mjs";
import { MCP_TURN_ID_FIELD, submissionToolBaseName, validMcpTurnId } from "../runtime/mcp-submission-policy.mjs";

export const PLUGIN_VERSION = "3.3.2";
export const NVIDIA_BATCH_INTER_REQUEST_DELAY_MS = 5_000;

function summaryForSkill(skillId, input) {
  const summary = { requestBytes: Buffer.byteLength(JSON.stringify(input), "utf8") };
  if (typeof input.sequence === "string") summary.sequenceLength = input.sequence.length;
  if (typeof input.input_pdb === "string") summary.pdbBytes = Buffer.byteLength(input.input_pdb);
  if (typeof input.protein === "string") summary.proteinPdbBytes = Buffer.byteLength(input.protein);
  if (Array.isArray(input.polymers)) summary.polymerCount = input.polymers.length;
  if (Array.isArray(input.ligands)) summary.ligandCount = input.ligands.length;
  return summary;
}

function toolResult(value) {
  const compactArtifacts = value.artifacts.map(({ name, bytes, downloadPath, viewerUrl, viewerMarkdown }) => ({
    name,
    bytes,
    downloadPath,
    ...(viewerUrl ? { viewerUrl } : {}),
    ...(viewerMarkdown ? { viewerMarkdown } : {}),
  }));
  const compactSteps = value.steps?.map(({ label, skillId, model, backend, status, elapsedMs, remoteJobId }) => ({
    label,
    skillId,
    ...(model ? { model } : {}),
    ...(backend ? { backend } : {}),
    status,
    ...(elapsedMs !== undefined ? { elapsedMs } : {}),
    ...(remoteJobId ? { remoteJobId } : {}),
  }));
  const structured = { ...value, ...(compactSteps ? { steps: compactSteps } : {}), artifacts: compactArtifacts };
  const text = JSON.stringify({
    status: "completed",
    runId: value.runId,
    summary: value.summary,
    artifacts: compactArtifacts,
    caveat: "Research use only. Review confidence and validate experimentally; this is not clinical advice.",
  }, null, 2);
  return { content: [{ type: "text", text }], structuredContent: structured };
}

const PRESENTATION_TTL_MS = 60 * 60 * 1_000;
const FINAL_ANSWER_SIGNATURE = JSON.stringify({ v: 1, phase: "final_answer" });

function structuredToolResult(result) {
  if (result?.structuredContent && typeof result.structuredContent === "object") return result.structuredContent;
  const text = Array.isArray(result?.content)
    ? result.content.find((item) => item?.type === "text" && typeof item.text === "string")?.text
    : undefined;
  if (!text) return undefined;
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? parsed : undefined;
  }
  catch { return undefined; }
}

const WORKFLOW_RUN_ID = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/u;
const VIEWER_CAPABILITY = /^[A-Za-z0-9_-]{32}$/u;
const STRUCTURE_FILE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(?:pdb|cif|mmcif)$/iu;
const CROSS_BACKEND_TOOL_NAME_SET = new Set(CROSS_BACKEND_TOOL_NAMES);
const TAVILY_SEARCH_TOOL_NAME = "tavily_web__tavily_search";
const TAVILY_SEARCH_SERVER = "tavily_web";
const TAVILY_SEARCH_OPERATION = "tavily_search";
const MAX_TAVILY_SOURCES = 5;
const MAX_TAVILY_TITLE_LENGTH = 300;
const MAX_TAVILY_URL_LENGTH = 2_048;

function validatedPresentationArtifact(item, runId, { artifactRoot, publicBaseUrl }) {
  if (!item || typeof item !== "object" || typeof item.name !== "string" || !STRUCTURE_FILE.test(item.name)) return undefined;
  const expectedDownloadPath = path.join(artifactRoot, runId, item.name);
  if (item.downloadPath !== expectedDownloadPath || typeof item.viewerMarkdown !== "string") return undefined;
  const markdown = item.viewerMarkdown.match(/^\[View structure in 3D\]\(<([^\s<>]+)>\)$/u);
  if (!markdown) return undefined;
  const viewerValue = markdown[1];
  let viewer;
  try { viewer = new URL(viewerValue, "https://bionemo.same-origin.invalid"); }
  catch { return undefined; }
  const expectedPath = `${VIEWER_ROUTE_PREFIX}/${runId}/${encodeURIComponent(item.name)}`;
  if (viewer.pathname !== expectedPath || viewer.hash || viewer.username || viewer.password) return undefined;
  const searchEntries = [...viewer.searchParams.entries()];
  if (searchEntries.length !== 1 || searchEntries[0][0] !== "access" || !VIEWER_CAPABILITY.test(searchEntries[0][1])) return undefined;
  if (viewerValue.startsWith("/")) {
    if (viewer.origin !== "https://bionemo.same-origin.invalid") return undefined;
  } else {
    if (!publicBaseUrl || viewer.origin !== publicBaseUrl) return undefined;
    const expectedAbsolute = new URL(`${expectedPath}?access=${encodeURIComponent(searchEntries[0][1])}`, `${publicBaseUrl}/`).toString();
    if (viewerValue !== expectedAbsolute) return undefined;
  }
  return item;
}

function artifactPresentation(result, options = {}) {
  const structured = structuredToolResult(result);
  const artifacts = Array.isArray(structured?.artifacts) ? structured.artifacts : [];
  const runId = typeof structured?.runId === "string" && WORKFLOW_RUN_ID.test(structured.runId) ? structured.runId : undefined;
  if (!runId) return undefined;
  const artifactRoot = path.resolve(options.artifactRoot || "/workspace/agent/artifacts");
  const publicBaseUrl = typeof options.publicBaseUrl === "string" ? options.publicBaseUrl : "";
  const structures = artifacts
    .map((item) => validatedPresentationArtifact(item, runId, { artifactRoot, publicBaseUrl }))
    .filter(Boolean);
  if (!structures.length) return undefined;
  return {
    viewerMarkdown: [...new Set(structures.map((item) => item.viewerMarkdown))],
    mediaLine: `MEDIA:${structures[0].downloadPath}`,
  };
}

function normalizedMessageRole(message) {
  return typeof message?.role === "string" ? message.role.toLowerCase().replace(/[^a-z]/gu, "") : "";
}

function messageToolName(value) {
  if (!value || typeof value !== "object") return undefined;
  for (const candidate of [value.toolName, value.tool_name, value.name, value.function?.name]) {
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  }
  return undefined;
}

function messageToolCallId(value, { includeId = false } = {}) {
  if (!value || typeof value !== "object") return undefined;
  const candidates = [value.toolCallId, value.tool_call_id, value.callId, value.call_id];
  if (includeId) candidates.push(value.id);
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  }
  return undefined;
}

function currentTurnArtifactPresentation(messages, options = {}) {
  if (!Array.isArray(messages)) return { observed: false };
  let lastUserIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (normalizedMessageRole(messages[index]) === "user") {
      lastUserIndex = index;
      break;
    }
  }
  if (lastUserIndex < 0) return { observed: false };
  const currentTurn = messages.slice(lastUserIndex + 1);
  const wrapperResults = currentTurn.filter((message) => {
    const role = normalizedMessageRole(message);
    return (role === "toolresult" || role === "tool" || role === "function")
      && CROSS_BACKEND_TOOL_NAME_SET.has(messageToolName(message));
  });
  if (!wrapperResults.length) return { observed: false };
  if (wrapperResults.length !== 1) return { observed: true };
  const result = wrapperResults[0];
  if (result.isError !== false || (result.error !== undefined && result.error !== null && result.error !== false && result.error !== "")) {
    return { observed: true };
  }

  const wrapperCalls = [];
  for (const message of currentTurn) {
    if (normalizedMessageRole(message) !== "assistant" || !Array.isArray(message.content)) continue;
    for (const block of message.content) {
      const type = typeof block?.type === "string" ? block.type.toLowerCase().replace(/[^a-z]/gu, "") : "";
      if (!["toolcall", "tooluse", "functioncall"].includes(type)) continue;
      if (CROSS_BACKEND_TOOL_NAME_SET.has(messageToolName(block))) wrapperCalls.push(block);
    }
  }
  if (wrapperCalls.length > 1) return { observed: true };
  if (wrapperCalls.length === 1) {
    if (messageToolName(wrapperCalls[0]) !== messageToolName(result)) return { observed: true };
    const callId = messageToolCallId(wrapperCalls[0], { includeId: true });
    const resultCallId = messageToolCallId(result);
    if (callId && resultCallId && callId !== resultCallId) return { observed: true };
  }

  const structured = structuredToolResult(result);
  if (!structured || (typeof structured.status === "string" && structured.status !== "completed")) return { observed: true };
  return { observed: true, presentation: artifactPresentation(result, options) };
}

function normalizedTavilySource(item) {
  if (!item || typeof item !== "object" || typeof item.title !== "string" || typeof item.url !== "string") return undefined;
  const title = item.title.replace(/[\u0000-\u001f\u007f]/gu, " ").replace(/\s+/gu, " ").trim();
  const rawUrl = item.url.trim();
  if (!title || title.length > MAX_TAVILY_TITLE_LENGTH || !rawUrl || rawUrl.length > MAX_TAVILY_URL_LENGTH) return undefined;
  if (!/^https?:\/\//iu.test(rawUrl)) return undefined;
  let url;
  try { url = new URL(rawUrl); }
  catch { return undefined; }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return undefined;
  return { title, url: url.toString() };
}

function currentTurnTavilySources(messages) {
  if (!Array.isArray(messages)) return { observed: false };
  let lastUserIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (normalizedMessageRole(messages[index]) === "user") {
      lastUserIndex = index;
      break;
    }
  }
  if (lastUserIndex < 0) return { observed: false };
  const currentTurn = messages.slice(lastUserIndex + 1);
  const searchResults = currentTurn.filter((message) => {
    const role = normalizedMessageRole(message);
    return (role === "toolresult" || role === "tool" || role === "function")
      && messageToolName(message) === TAVILY_SEARCH_TOOL_NAME;
  });
  if (!searchResults.length) return { observed: false };
  if (searchResults.length !== 1) return { observed: true };
  const result = searchResults[0];
  if (result.isError !== false || (result.error !== undefined && result.error !== null && result.error !== false && result.error !== "")) {
    return { observed: true };
  }

  const searchCalls = [];
  for (const message of currentTurn) {
    if (normalizedMessageRole(message) !== "assistant" || !Array.isArray(message.content)) continue;
    for (const block of message.content) {
      const type = typeof block?.type === "string" ? block.type.toLowerCase().replace(/[^a-z]/gu, "") : "";
      if (!["toolcall", "tooluse", "functioncall"].includes(type)) continue;
      if (messageToolName(block) === TAVILY_SEARCH_TOOL_NAME) searchCalls.push(block);
    }
  }
  if (searchCalls.length > 1) return { observed: true };
  if (searchCalls.length === 1) {
    const callId = messageToolCallId(searchCalls[0], { includeId: true });
    const resultCallId = messageToolCallId(result);
    if (callId && resultCallId && callId !== resultCallId) return { observed: true };
  }

  const details = result.details;
  if (!details || typeof details !== "object"
    || details.mcpServer !== TAVILY_SEARCH_SERVER || details.mcpTool !== TAVILY_SEARCH_OPERATION) return { observed: true };
  if (result.structuredContent !== undefined) return { observed: true };
  const structured = details.structuredContent;
  if (!structured || typeof structured !== "object" || !Array.isArray(structured.results)
    || structured.results.length < 1 || structured.results.length > MAX_TAVILY_SOURCES) return { observed: true };
  const sources = structured.results.map(normalizedTavilySource);
  if (sources.some((source) => !source)) return { observed: true };
  const userMessage = messages[lastUserIndex];
  const queryText = typeof userMessage?.content === "string"
    ? userMessage.content
    : Array.isArray(userMessage?.content)
      ? userMessage.content.filter((item) => item?.type === "text" && typeof item.text === "string").map((item) => item.text).join("\n")
      : "";
  return { observed: true, sources, queryText };
}

function tavilySourceLine(source) {
  const title = source.title.replace(/([\\`*_[\]{}()<>#+\-.!|])/gu, "\\$1");
  return `- ${title} — ${source.url}`;
}

function tavilySourcesAppendText(text, sources) {
  if (typeof text !== "string" || !Array.isArray(sources) || !sources.length) return undefined;
  if (sources.every(({ url }) => text.includes(url))) return undefined;
  return `Sources\n\n${sources.map(tavilySourceLine).join("\n")}`;
}

function tavilyCoverageAppendText(text, queryText, sources) {
  if (typeof text !== "string" || typeof queryText !== "string" || !Array.isArray(sources) || !sources.length) return undefined;
  const sourceHosts = sources.map(({ url }) => new URL(url).hostname.toLowerCase());
  const requirements = [
    {
      requested: /\bUniProt\b/iu.test(queryText),
      present: sourceHosts.some((host) => host === "uniprot.org" || host.endsWith(".uniprot.org")),
      sentence: "No direct UniProt source was returned by this bounded search.",
    },
    {
      requested: /\bRCSB\b|\bProtein Data Bank\b/iu.test(queryText),
      present: sourceHosts.some((host) => host === "rcsb.org" || host.endsWith(".rcsb.org")),
      sentence: "No direct RCSB source was returned by this bounded search.",
    },
  ];
  const disclosures = requirements
    .filter(({ requested, present, sentence }) => requested && !present && !text.includes(sentence))
    .map(({ sentence }) => sentence);
  return disclosures.length ? disclosures.join("\n") : undefined;
}

function textBlockPhase(block) {
  if (!block || typeof block !== "object" || typeof block.textSignature !== "string") return undefined;
  if (!block.textSignature.startsWith("{")) return undefined;
  try {
    const signature = JSON.parse(block.textSignature);
    return signature?.v === 1 && (signature.phase === "commentary" || signature.phase === "final_answer")
      ? signature.phase
      : undefined;
  }
  catch { return undefined; }
}

function visibleAssistantText(message) {
  if (typeof message?.content === "string") return message.content;
  if (!Array.isArray(message?.content)) return "";
  const textBlocks = message.content.filter((item) => item?.type === "text" && typeof item.text === "string");
  const hasExplicitPhase = textBlocks.some((item) => textBlockPhase(item));
  const visible = hasExplicitPhase
    ? textBlocks.filter((item) => textBlockPhase(item) === "final_answer")
    : message?.phase === "commentary" ? [] : textBlocks;
  return visible.map((item) => item.text).join("\n");
}

function artifactPresentationAppendText(text, presentation) {
  if (typeof text !== "string") return undefined;
  const missing = presentation.viewerMarkdown.filter((line) => !text.includes(line));
  const existingLines = new Set(text.split(/\r?\n/u).map((line) => line.trim()));
  if (presentation.mediaLine && !existingLines.has(presentation.mediaLine)) missing.push(presentation.mediaLine);
  return missing.length ? `Workflow artifacts\n\n${missing.join("\n")}` : undefined;
}

function appendArtifactPresentationText(text, presentation) {
  const appendText = artifactPresentationAppendText(text, presentation);
  if (!appendText) return text;
  return text ? `${text.trimEnd()}\n\n${appendText}` : appendText;
}

function appendArtifactPresentation(message, presentation) {
  if (message?.role !== "assistant") return undefined;
  if (message.stopReason !== "stop") return undefined;
  if (Array.isArray(message?.content) && message.content.some((item) => /tool/u.test(String(item?.type || "").toLowerCase()))) return undefined;
  if (message.phase === "commentary") return undefined;
  const currentText = visibleAssistantText(message);
  const nextText = appendArtifactPresentationText(currentText, presentation);
  if (nextText === undefined || nextText === currentText) return message;
  const suffix = nextText.slice(currentText.trimEnd().length).replace(/^\s+/u, "");
  if (typeof message.content === "string") return { ...message, content: nextText };
  const content = Array.isArray(message.content) ? [...message.content] : [];
  const hasExplicitPhase = content.some((item) => item?.type === "text" && textBlockPhase(item));
  if (hasExplicitPhase && !content.some((item) => item?.type === "text" && textBlockPhase(item) === "final_answer")) return undefined;
  content.push({
    type: "text",
    text: suffix,
    ...(hasExplicitPhase ? { textSignature: FINAL_ANSWER_SIGNATURE } : {}),
  });
  return { ...message, content };
}

function createPresentationRegistry({
  now = () => Date.now(),
  setTimeoutImpl = setTimeout,
  clearTimeoutImpl = clearTimeout,
  ttlMs = PRESENTATION_TTL_MS,
} = {}) {
  const pending = new Map();
  const clear = (runId) => {
    const entry = pending.get(runId);
    if (!entry) return false;
    clearTimeoutImpl(entry.timer);
    return pending.delete(runId);
  };
  const set = (runId, presentation) => {
    clear(runId);
    const expiresAt = now() + ttlMs;
    const entry = { presentation, expiresAt, timer: undefined };
    entry.timer = setTimeoutImpl(() => {
      if (pending.get(runId) === entry) pending.delete(runId);
    }, ttlMs);
    entry.timer?.unref?.();
    pending.set(runId, entry);
  };
  const get = (runId) => {
    const entry = pending.get(runId);
    if (!entry) return undefined;
    if (entry.expiresAt <= now()) {
      clear(runId);
      return undefined;
    }
    return entry.presentation;
  };
  return Object.freeze({ set, get, clear, size: () => pending.size });
}

export function createRuntime({ fetchImpl = globalThis.fetch, env = process.env, artifactRoot, logger = console } = {}) {
  const store = new ArtifactStore(artifactRoot || env.BIONEMO_ARTIFACT_ROOT || "/workspace/agent/artifacts");
  const client = new NimClient({ fetchImpl, env, logger });
  const researchDirectClient = new NimClient({ fetchImpl, env, logger, retries: 0 });
  const tavilyClient = new TavilySearchClient({ fetchImpl, env });
  const mcpClient = new CerebriumMcpModelClient({ fetchImpl, env, logger });
  const researchBackend = selectedResearchBackend(env);
  const researchDemoRunner = new ResearchDrugDemoRunner({
    directClient: researchDirectClient,
    mcpClient,
    tavilyClient,
    store,
    backend: researchBackend,
    batchInterRequestDelayMs: researchBackend === "nvidia" ? NVIDIA_BATCH_INTER_REQUEST_DELAY_MS : 0,
    onProgress: async () => {},
  });
  const researchDemoExecutions = new Map();
  const researchDemoExecutionTtlMs = 60 * 60 * 1_000;

  function runCrossBackendOnce(workflowId, rawInput) {
    const turnId = rawInput?.[MCP_TURN_ID_FIELD];
    if (!WORKFLOWS[workflowId]?.crossBackend) throw Object.assign(new Error(`Unsupported cross-backend workflow: ${workflowId}.`), { code: "invalid_workflow", status: 400 });
    if (!validMcpTurnId(turnId)) throw Object.assign(new Error("The composed workflow requires a trusted per-turn execution identity."), { code: "missing_turn_identity", status: 500 });
    const executionKey = `${workflowId}:${turnId}`;
    const existing = researchDemoExecutions.get(executionKey);
    if (existing) return existing.promise;
    const promise = researchDemoRunner.run(workflowId, rawInput);
    const cleanupTimer = setTimeout(() => researchDemoExecutions.delete(executionKey), researchDemoExecutionTtlMs);
    cleanupTimer.unref?.();
    researchDemoExecutions.set(executionKey, { promise, createdAt: Date.now(), cleanupTimer });
    promise.catch(() => {}).finally(() => {
      const cutoff = Date.now() - researchDemoExecutionTtlMs;
      for (const [key, entry] of researchDemoExecutions) {
        if (entry.createdAt < cutoff && key !== executionKey) {
          clearTimeout(entry.cleanupTimer);
          researchDemoExecutions.delete(key);
        }
      }
    });
    return promise;
  }

  async function runSkill(skillId, rawInput) {
    const normalizedInput = normalizeDirectSkillInput(skillId, rawInput);
    const input = VALIDATORS[skillId](await resolveSkillInput(skillId, normalizedInput));
    const run = await store.createRun({ kind: "skill", id: skillId, inputSummary: summaryForSkill(skillId, input) });
    try {
      const result = await client.call(skillId, input);
      await store.saveNimResult(run, result);
      await store.complete(run, { steps: [{ label: SKILLS[skillId].label, skillId, status: "completed", elapsedMs: result.elapsedMs }] });
      return {
        runId: run.runId,
        summary: { skill: SKILLS[skillId].label, elapsedMs: result.elapsedMs, requestId: result.requestId, responseKeys: Object.keys(result.data).slice(0, 50) },
        artifacts: store.presentArtifacts(run),
      };
    } catch (error) {
      const safe = publicError(error);
      await store.complete(run, { status: "failed", error: safe });
      throw Object.assign(new Error(`${safe.code}: ${safe.message}`), { code: safe.code, status: safe.status });
    }
  }

  const workflowRunner = new WorkflowRunner({ client, store, onProgress: async () => {} });
  async function runWorkflow(workflowId, rawInput) {
    try {
      if (WORKFLOWS[workflowId]?.crossBackend) return await runCrossBackendOnce(workflowId, rawInput);
      return await workflowRunner.run(workflowId, await resolveWorkflowInput(workflowId, rawInput));
    }
    catch (error) {
      const safe = publicError(error);
      throw Object.assign(new Error(`${safe.code}: ${safe.message}`), { code: safe.code, status: safe.status });
    }
  }
  return { store, client, researchDirectClient, tavilyClient, mcpClient, researchDemoRunner, researchDemoExecutions, runSkill, runWorkflow };
}

export function registerPlugin(api, options = {}) {
    const runtime = options.runtime || createRuntime({ logger: api.logger });
    const presentationRegistry = options.presentationRegistry || createPresentationRegistry();
    for (const definition of Object.values(SKILLS)) {
      api.registerTool({
        name: definition.tool,
        label: definition.label,
        description: `${definition.description} NVIDIA-hosted route only; research use only.`,
        parameters: JSON_SCHEMAS[definition.id],
        async execute(_toolCallId, params) { return toolResult(await runtime.runSkill(definition.id, params)); },
      });
    }
    for (const definition of Object.values(WORKFLOWS)) {
      api.registerTool({
        name: definition.tool,
        label: definition.label,
        description: definition.crossBackend
          ? `${definition.description} It selects the configured NVIDIA or Cerebrium MCP model backend${definition.id === "research_drug_demo" ? " and can optionally run bounded Tavily research first" : ""}; research use only.`
          : `${definition.description} Bounded event-sized hosted NIM calls only; research use only.`,
        parameters: JSON_SCHEMAS[definition.id],
        async execute(_toolCallId, params) {
          const agentRunId = params?.[MCP_TURN_ID_FIELD];
          try {
            const result = toolResult(await runtime.runWorkflow(definition.id, params));
            if (definition.crossBackend && validMcpTurnId(agentRunId)) {
              const presentation = artifactPresentation(result, {
                artifactRoot: runtime.store?.root,
                publicBaseUrl: runtime.store?.publicBaseUrl,
              });
              if (presentation) presentationRegistry.set(agentRunId, presentation);
              else presentationRegistry.clear(agentRunId);
            }
            return result;
          }
          catch (error) {
            if (definition.crossBackend && validMcpTurnId(agentRunId)) presentationRegistry.clear(agentRunId);
            throw error;
          }
        },
      });
    }

    const handlers = createUiHandlers({ store: runtime.store, runtimeVersion: PLUGIN_VERSION });
    api.registerHttpRoute({ path: "/plugins/bionemo/readiness", auth: "plugin", match: "exact", handler: handlers.readiness });
    api.registerHttpRoute({ path: "/plugins/bionemo/assets/3dmol.min.js", auth: "plugin", match: "exact", handler: handlers.viewerAsset });
    api.registerHttpRoute({ path: NOTEBOOK_ROUTE_PREFIX, auth: "plugin", match: "prefix", handler: handlers.notebooks });
    api.registerHttpRoute({ path: VIEWER_ROUTE_PREFIX, auth: "plugin", match: "prefix", handler: handlers.viewer });
    api.registerHttpRoute({ path: "/plugins/bionemo", auth: "plugin", match: "exact", handler: handlers.dashboard });
    api.registerHttpRoute({ path: "/plugins/bionemo/api", auth: "gateway", match: "prefix", handler: handlers.api });
    api.session.controls.registerControlUiDescriptor({
      surface: "tab",
      id: "bionemo-research",
      label: "BioNeMo",
      description: "Hosted NIM catalog, workflow progress, and authenticated artifact downloads.",
      icon: "flask-conical",
      group: "agent",
      order: 5,
      path: "/plugins/bionemo",
      requiredScopes: ["operator.read"],
    });
    api.on("before_tool_call", async (event, ctx) => {
      if (!submissionToolBaseName(event?.toolName) && !CROSS_BACKEND_TOOL_NAMES.includes(event?.toolName)) return;
      const runId = ctx?.runId || event?.runId;
      if (!validMcpTurnId(runId)) {
        return {
          block: true,
          blockReason: "BioNeMo compute submission was stopped because its trusted per-turn identity is unavailable. Start a new chat turn and try once more.",
        };
      }
      return { params: { ...event.params, [MCP_TURN_ID_FIELD]: runId } };
    });
    api.on("before_agent_finalize", (event, ctx) => {
      const agentRunId = ctx?.runId || event?.runId;
      if (!validMcpTurnId(agentRunId)) return;
      const appendSegments = [];
      const currentTurn = currentTurnArtifactPresentation(event?.messages, {
        artifactRoot: runtime.store?.root,
        publicBaseUrl: runtime.store?.publicBaseUrl,
      });
      const presentation = currentTurn.observed ? currentTurn.presentation : presentationRegistry.get(agentRunId);
      const artifactAppendText = presentation
        ? artifactPresentationAppendText(event?.lastAssistantMessage, presentation)
        : undefined;
      if (artifactAppendText) appendSegments.push(artifactAppendText);
      const tavily = currentTurnTavilySources(event?.messages);
      const coverageAppendText = tavily.sources
        ? tavilyCoverageAppendText(event?.lastAssistantMessage, tavily.queryText, tavily.sources)
        : undefined;
      if (coverageAppendText) appendSegments.push(coverageAppendText);
      const sourcesAppendText = tavily.sources
        ? tavilySourcesAppendText(event?.lastAssistantMessage, tavily.sources)
        : undefined;
      if (sourcesAppendText) appendSegments.push(sourcesAppendText);
      if (!appendSegments.length) return;
      return { action: "continue", appendFinalAssistantText: appendSegments.join("\n\n") };
    });
    api.on("agent_end", (event, ctx) => {
      const agentRunId = event?.runId || ctx?.runId;
      if (validMcpTurnId(agentRunId)) presentationRegistry.clear(agentRunId);
    });
    api.on("before_prompt_build", async () => ({
      prependSystemContext: `BioNeMo Toolkit pin ${TOOLKIT_COMMIT}. Use only the configured bionemo_* tools, the local demo-only ClawBio catalog tools, and configured Tavily MCP tools. The raw hosted-model MCP is a private backend and is not available in the OpenClaw browser. The four backend-neutral composed demo tools are bionemo_research_drug_demo, bionemo_compare_protein_structures, bionemo_optimize_ligand_complex, and bionemo_batch_fold_demo. After the user explicitly accepts every displayed const-true acknowledgement, call the selected composed tool exactly once and do not reproduce its internal model or optional Tavily calls. After that wrapper returns a successful completed result, call no other tool in the turn; immediately narrate its returned steps, artifacts, and limitations. Follow every displayed tool schema exactly. Pass direct bionemo_* arguments as one flat JSON object. For direct MolMIM calls, always pass num_molecules and keep particles greater than or equal to num_molecules. For direct ProteinMPNN calls, pass exactly one of input_pdb or input_pdb_sample. Never ask for or reveal credentials. For every artifact that has viewerMarkdown, copy that complete viewerMarkdown field verbatim into the final reply; it is already a clickable link in the exact form [View structure in 3D](<VALUE>). Do not reconstruct it from viewerUrl and do not leave either field as plain text. Its URL may be a same-origin path beginning with /; preserve it verbatim and never prepend, invent, or rewrite a host. Attach the top-ranked structure by emitting its exact absolute downloadPath as MEDIA:<downloadPath> on its own line in the final reply. Keep all work nonclinical, research-only, and explain confidence plus wet-lab validation requirements. Do not claim that this application itself runs NIM containers or can create Nebius resources.`,
    }));
    api.logger.info?.(`BioNeMo Agent Toolkit ${PLUGIN_VERSION} registered ${PUBLIC_CATALOG.skills.length} skills and ${PUBLIC_CATALOG.workflows.length} workflows`);
    return { runtime, presentationRegistry };
}

export default {
  id: "bionemo-agent-toolkit",
  name: "BioNeMo Agent Toolkit",
  description: "Bounded NVIDIA hosted-NIM adapters plus a preconfigured remote BioNeMo MCP gateway.",
  version: PLUGIN_VERSION,
  register(api) {
    return registerPlugin(api);
  },
};

export const __test = Object.freeze({
  artifactPresentation,
  artifactPresentationAppendText,
  appendArtifactPresentation,
  appendArtifactPresentationText,
  createPresentationRegistry,
  currentTurnArtifactPresentation,
  currentTurnTavilySources,
  registerPlugin,
  tavilySourceLine,
  tavilyCoverageAppendText,
  tavilySourcesAppendText,
  textBlockPhase,
  visibleAssistantText,
});
