import { createHash } from "node:crypto";
import { InputError, redactText } from "./errors.mjs";
import { LIMITS } from "./validation.mjs";

export const TAVILY_SEARCH_URL = "https://api.tavily.com/search";
export const DEFAULT_CEREBRIUM_MCP_URL = "https://api.cerebrium.ai/v4/p-12ff482a/clawbio-models-mcp-public/mcp";
export const TAVILY_EGFR_QUERY = "EGFR gefitinib resistance mechanism medicinal chemistry current public research evidence";
export const RESEARCH_DEMO_USER_AGENT = "nebius-bionemo-agent/3.3.0";
export const TAVILY_PRIMARY_DOMAINS = Object.freeze([
  "pubmed.ncbi.nlm.nih.gov",
  "pmc.ncbi.nlm.nih.gov",
  "fda.gov",
  "ebi.ac.uk",
  "uniprot.org",
]);

const MCP_PROTOCOL_VERSION = "2025-06-18";
const MCP_BODY_LIMIT = 1_000_000;
const TAVILY_BODY_LIMIT = 1_000_000;
const FETCH_CHUNK_BYTES = 32_768;
const IDEMPOTENCY_KEY = /^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$/u;
const JOB_ID = /^[0-9a-f]{32}$/u;
const TERMINAL_STATES = new Set(["succeeded", "failed"]);

const MCP_MODELS = Object.freeze({
  openfold2: Object.freeze({
    tool: "clawbio_openfold2_predict",
    acknowledgements: Object.freeze({ research_only: true, non_clinical: true }),
  }),
  molmim: Object.freeze({
    tool: "clawbio_molmim_optimize",
    acknowledgements: Object.freeze({ research_only: true, no_safety_or_therapeutic_claims: true }),
  }),
  openfold3: Object.freeze({
    tool: "clawbio_openfold3_predict",
    acknowledgements: Object.freeze({ research_only: true, non_clinical: true }),
  }),
});

function codedError(message, { code = "vendor_error", status = 502, retryable = false } = {}) {
  return Object.assign(new Error(redactText(message)), { code, status, retryable });
}

function requireSecret(value, label, code) {
  if (typeof value !== "string" || value.length < 1) {
    throw codedError(`${label} is not configured through the endpoint secret environment.`, { code, status: 500 });
  }
  return value;
}

async function readBodyLimited(response, limit) {
  const advertised = Number(response.headers?.get?.("content-length") || 0);
  if (advertised > limit) throw codedError(`Remote response exceeds ${limit} bytes.`, { code: "response_too_large" });
  if (!response.body?.getReader) {
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length > limit) throw codedError(`Remote response exceeds ${limit} bytes.`, { code: "response_too_large" });
    return buffer.toString("utf8");
  }
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel("response limit exceeded");
        throw codedError(`Remote response exceeds ${limit} bytes.`, { code: "response_too_large" });
      }
      chunks.push(Buffer.from(value));
    }
  } finally {
    reader.releaseLock();
  }
  return Buffer.concat(chunks, total).toString("utf8");
}

function timeoutSignal(timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

function safeHttpUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) return null;
    const host = url.hostname.toLowerCase();
    if (!TAVILY_PRIMARY_DOMAINS.some((domain) => host === domain || host.endsWith(`.${domain}`))) return null;
    url.hash = "";
    const normalized = url.toString();
    return normalized.length <= 2_048 ? normalized : null;
  } catch {
    return null;
  }
}

function sanitizedTavilyResult(item) {
  if (!item || typeof item !== "object") return null;
  const url = safeHttpUrl(item.url);
  if (!url) return null;
  return {
    title: String(item.title || "Untitled source").slice(0, 300),
    url,
    content: String(item.content || "").slice(0, 2_000),
    score: Number.isFinite(item.score) ? item.score : null,
    trust: "untrusted_search_snippet",
    metadataTrust: "untrusted_metadata",
  };
}

export class TavilySearchClient {
  constructor({ fetchImpl = globalThis.fetch, env = process.env, timeoutMs = 30_000 } = {}) {
    if (typeof fetchImpl !== "function") throw new TypeError("fetch implementation is required");
    this.fetchImpl = fetchImpl;
    this.apiKey = env.TAVILY_API_KEY;
    this.timeoutMs = Math.max(1_000, Math.min(Number(timeoutMs) || 30_000, 120_000));
  }

  assertConfigured() {
    requireSecret(this.apiKey, "TAVILY_API_KEY", "missing_tavily_key");
  }

  isConfigured() {
    return typeof this.apiKey === "string" && this.apiKey.length > 0;
  }

  async search() {
    const key = requireSecret(this.apiKey, "TAVILY_API_KEY", "missing_tavily_key");
    const body = {
      query: TAVILY_EGFR_QUERY,
      search_depth: "basic",
      max_results: 5,
      include_answer: "basic",
      include_raw_content: false,
      include_images: false,
      include_domains: [...TAVILY_PRIMARY_DOMAINS],
    };
    const timeout = timeoutSignal(this.timeoutMs);
    let response;
    try {
      response = await this.fetchImpl(TAVILY_SEARCH_URL, {
        method: "POST",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json",
          "User-Agent": RESEARCH_DEMO_USER_AGENT,
        },
        body: JSON.stringify(body),
        redirect: "error",
        signal: timeout.signal,
      });
      const text = await readBodyLimited(response, TAVILY_BODY_LIMIT);
      if (!response.ok) {
        throw codedError(`Tavily search returned HTTP ${response.status}.`, {
          code: response.status === 401 || response.status === 403 ? "tavily_auth_or_entitlement" : "tavily_http_error",
          retryable: response.status === 429 || response.status >= 500,
        });
      }
      let parsed;
      try { parsed = JSON.parse(text); } catch {
        throw codedError("Tavily returned a non-JSON success response.", { code: "invalid_tavily_response" });
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw codedError("Tavily returned an invalid response object.", { code: "invalid_tavily_response" });
      }
      const results = (Array.isArray(parsed.results) ? parsed.results : []).slice(0, 5).map(sanitizedTavilyResult).filter(Boolean);
      if (!results.length) throw codedError("Tavily returned no citable public sources for the fixed EGFR query.", { code: "empty_tavily_results" });
      return {
        provider: "Tavily Search API",
        requestId: typeof parsed.request_id === "string" ? parsed.request_id.replace(/[^A-Za-z0-9._:-]/gu, "").slice(0, 128) || null : null,
        query: TAVILY_EGFR_QUERY,
        answer: typeof parsed.answer === "string" ? parsed.answer.slice(0, 4_000) : null,
        results,
        responseTime: Number.isFinite(parsed.response_time) ? parsed.response_time : null,
        contentNotice: "Search snippets are untrusted evidence leads; open and verify the cited primary source before relying on a claim.",
      };
    } catch (error) {
      if (error?.name === "AbortError") throw codedError("Tavily search exceeded its bounded timeout.", { code: "tavily_timeout", retryable: true });
      if (error?.code) throw error;
      throw codedError(`Tavily search network error: ${error?.name || "request failed"}.`, { code: "tavily_network_error", retryable: true });
    } finally {
      timeout.clear();
    }
  }
}

function validatedMcpUrl(value, env) {
  const url = new URL(value || DEFAULT_CEREBRIUM_MCP_URL);
  if (url.username || url.password || url.search || url.hash) throw new InputError("MCP URL must not contain credentials, a query, or a fragment");
  const allowInsecure = ["1", "true", "yes", "on"].includes(String(env.BIONEMO_ALLOW_INSECURE_MCP || "").toLowerCase());
  if (url.protocol !== "https:" && !(url.protocol === "http:" && allowInsecure)) {
    throw new InputError("MCP URL must use HTTPS unless trusted HTTP is explicitly enabled");
  }
  return url.toString();
}

function internalMcpUrl(url, env) {
  if (url) return validatedMcpUrl(url, env);
  if (env.BIONEMO_MCP_UPSTREAM_URL) return validatedMcpUrl(env.BIONEMO_MCP_UPSTREAM_URL, env);
  const configured = validatedMcpUrl(env.BIONEMO_MCP_URL || DEFAULT_CEREBRIUM_MCP_URL, env);
  const parsed = new URL(configured);
  const requested = String(env.BIONEMO_BACKEND || "auto").toLowerCase();
  const mcpMode = requested === "mcp" || (requested === "auto" && Boolean(env.BIONEMO_MCP_API_KEY || env.CLAWBIO_API_KEY));
  if (mcpMode && ["127.0.0.1", "localhost", "[::1]", "::1"].includes(parsed.hostname)) {
    throw new InputError("BIONEMO_MCP_UPSTREAM_URL is required for the composed workflow when BIONEMO_MCP_URL points to the flattened loopback adapter");
  }
  return configured;
}

function sseMessages(text) {
  const messages = [];
  let data = [];
  const flush = () => {
    if (!data.length) return;
    const joined = data.join("\n");
    data = [];
    if (joined === "[DONE]") return;
    try { messages.push(JSON.parse(joined)); } catch { /* handled after all events */ }
  };
  for (const line of text.split(/\r?\n/u)) {
    if (!line) { flush(); continue; }
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  flush();
  return messages;
}

function parsedRpcMessage(text, contentType) {
  let candidates;
  if (String(contentType || "").toLowerCase().includes("text/event-stream")) candidates = sseMessages(text);
  else {
    try { candidates = [JSON.parse(text)]; } catch {
      throw codedError("Cerebrium MCP returned an invalid JSON-RPC response.", { code: "invalid_mcp_response" });
    }
  }
  const message = candidates.findLast((item) => item && typeof item === "object" && (Object.hasOwn(item, "result") || Object.hasOwn(item, "error")));
  if (!message) throw codedError("Cerebrium MCP returned no JSON-RPC result.", { code: "invalid_mcp_response" });
  if (message.error) {
    const remoteCode = String(message.error?.code ?? "rpc_error").slice(0, 80);
    throw codedError(`Cerebrium MCP rejected the tool call (${remoteCode}).`, { code: "mcp_rpc_error" });
  }
  const result = message.result;
  if (!result || typeof result !== "object") throw codedError("Cerebrium MCP returned an invalid tool result.", { code: "invalid_mcp_response" });
  if (result.isError) {
    const textBlock = Array.isArray(result.content) ? result.content.find((item) => item?.type === "text" && typeof item.text === "string") : null;
    throw codedError(`Cerebrium MCP tool failed${textBlock ? `: ${textBlock.text.slice(0, 500)}` : "."}`, { code: "mcp_tool_error" });
  }
  if (result.structuredContent && typeof result.structuredContent === "object") return unwrappedStructuredContent(result.structuredContent);
  if (Array.isArray(result.content)) {
    for (const item of result.content) {
      if (item?.type !== "text" || typeof item.text !== "string") continue;
      try {
        const parsed = JSON.parse(item.text);
        if (parsed && typeof parsed === "object") return unwrappedStructuredContent(parsed);
      } catch { /* continue */ }
    }
  }
  return result;
}

function unwrappedStructuredContent(value) {
  if (!value || typeof value !== "object") return value;
  if (value.result && typeof value.result === "object" && !Array.isArray(value.result)) return value.result;
  return value;
}

function mcpRequest(skillId, payload) {
  if (skillId === "openfold2") {
    return {
      sequence: payload.sequence,
      ...(payload.input_id ? { input_id: payload.input_id } : {}),
      selected_models: [1],
      relax: false,
    };
  }
  if (skillId === "molmim") {
    return {
      smi: payload.smi,
      algorithm: payload.algorithm ?? "CMA-ES",
      num_molecules: payload.num_molecules ?? 2,
      iterations: payload.num_iterations ?? payload.iterations ?? 2,
      property_name: payload.property_name ?? "QED",
      particles: payload.particles ?? 2,
      minimize: payload.minimize ?? false,
      min_similarity: payload.min_similarity ?? 0.7,
      scaled_radius: payload.radius ?? payload.scaled_radius ?? 1,
    };
  }
  if (skillId === "openfold3") {
    return {
      inputs: payload.inputs.map((input) => ({
        input_id: input.input_id,
        output_format: input.output_format ?? "pdb",
        molecules: input.molecules.map((molecule) => ({
          type: molecule.type,
          ...(molecule.sequence ? { sequence: molecule.sequence } : {}),
          ...(molecule.smiles ? { smiles: molecule.smiles } : {}),
          ...(molecule.ccd ? { ccd_codes: molecule.ccd } : {}),
          ...(molecule.id ? { id: molecule.id } : {}),
          diffusion_samples: 1,
          ...(molecule.msa ? { msa: molecule.msa } : {}),
          ...(molecule.paired_msa ? { paired_msa: molecule.paired_msa } : {}),
        })),
      })),
    };
  }
  throw new InputError(`unsupported composed MCP model: ${skillId}`);
}

function validatedIdempotencyKey(value) {
  if (typeof value !== "string" || !IDEMPOTENCY_KEY.test(value)) {
    throw new InputError("MCP idempotency key must contain 16 to 128 safe characters");
  }
  return value;
}

function responseArtifact(status) {
  const artifacts = Array.isArray(status?.artifacts) ? status.artifacts : [];
  return artifacts.find((item) => item?.name === "response.json")
    || artifacts.find((item) => typeof item?.name === "string" && item.name.endsWith(".json") && item.media_type === "application/json")
    || null;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class CerebriumMcpModelClient {
  constructor({
    fetchImpl = globalThis.fetch,
    env = process.env,
    url,
    logger = console,
    sleepImpl = sleep,
    nowImpl = () => Date.now(),
    requestTimeoutMs = 60_000,
    jobTimeoutMs = 900_000,
    maxPolls = 600,
    pollIntervalMs = 2_000,
  } = {}) {
    if (typeof fetchImpl !== "function") throw new TypeError("fetch implementation is required");
    this.fetchImpl = fetchImpl;
    this.apiKey = env.BIONEMO_MCP_API_KEY || env.CLAWBIO_API_KEY;
    this.url = internalMcpUrl(url, env);
    this.logger = logger;
    this.sleepImpl = sleepImpl;
    this.nowImpl = nowImpl;
    this.requestTimeoutMs = Math.max(1_000, Math.min(Number(requestTimeoutMs) || 60_000, 120_000));
    this.jobTimeoutMs = Math.max(30_000, Math.min(Number(jobTimeoutMs) || 900_000, 1_200_000));
    this.maxPolls = Math.max(1, Math.min(Number(maxPolls) || 600, 1_000));
    this.pollIntervalMs = Math.max(0, Math.min(Number(pollIntervalMs) || 2_000, 10_000));
    this.rpcId = 0;
  }

  assertConfigured() {
    requireSecret(this.apiKey, "BIONEMO_MCP_API_KEY or CLAWBIO_API_KEY", "missing_mcp_key");
  }

  async tool(name, args) {
    const key = requireSecret(this.apiKey, "BIONEMO_MCP_API_KEY or CLAWBIO_API_KEY", "missing_mcp_key");
    const timeout = timeoutSignal(this.requestTimeoutMs);
    try {
      const response = await this.fetchImpl(this.url, {
        method: "POST",
        headers: {
          Accept: "application/json, text/event-stream",
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json",
          "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
          "User-Agent": RESEARCH_DEMO_USER_AGENT,
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: ++this.rpcId,
          method: "tools/call",
          params: { name, arguments: args },
        }),
        redirect: "error",
        signal: timeout.signal,
      });
      const text = await readBodyLimited(response, MCP_BODY_LIMIT);
      if (!response.ok) {
        throw codedError(`Cerebrium MCP returned HTTP ${response.status}.`, {
          code: response.status === 401 || response.status === 403 ? "mcp_auth_or_entitlement" : "mcp_http_error",
          retryable: response.status === 429 || response.status >= 500,
        });
      }
      return parsedRpcMessage(text, response.headers?.get?.("content-type"));
    } catch (error) {
      if (error?.name === "AbortError") throw codedError(`Cerebrium MCP tool ${name} exceeded its bounded request timeout.`, { code: "mcp_request_timeout", retryable: true });
      if (error?.code) throw error;
      throw codedError(`Cerebrium MCP network error while calling ${name}: ${error?.name || "request failed"}.`, { code: "mcp_network_error", retryable: true });
    } finally {
      timeout.clear();
    }
  }

  async fetchResponseJson(jobId, artifact) {
    if (!artifact || typeof artifact.artifact_id !== "string") throw codedError(`MCP job ${jobId} did not expose a response JSON artifact.`, { code: "missing_mcp_response_artifact" });
    const expectedBytes = Number(artifact.bytes);
    const expectedSha = String(artifact.sha256 || "").toLowerCase();
    if (!Number.isInteger(expectedBytes) || expectedBytes < 1 || expectedBytes > LIMITS.responseBytes) {
      throw codedError(`MCP job ${jobId} response artifact has an invalid size.`, { code: "invalid_mcp_artifact" });
    }
    if (!/^[0-9a-f]{64}$/u.test(expectedSha)) throw codedError(`MCP job ${jobId} response artifact has an invalid SHA-256.`, { code: "invalid_mcp_artifact" });

    const chunks = [];
    let offset = 0;
    while (offset < expectedBytes) {
      const fetched = await this.tool("clawbio_model_fetch", {
        job_id: jobId,
        artifact_id: artifact.artifact_id,
        representation: "base64",
        offset,
        length: FETCH_CHUNK_BYTES,
      });
      if (fetched?.artifact_id !== artifact.artifact_id || Number(fetched.offset) !== offset || Number(fetched.bytes) !== expectedBytes || String(fetched.sha256 || "").toLowerCase() !== expectedSha || fetched.encoding !== "base64") {
        throw codedError(`MCP job ${jobId} returned inconsistent artifact metadata.`, { code: "invalid_mcp_artifact" });
      }
      const encoded = String(fetched.data || "");
      if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/u.test(encoded)) {
        throw codedError(`MCP job ${jobId} returned invalid base64 artifact data.`, { code: "invalid_mcp_artifact" });
      }
      const chunk = Buffer.from(encoded, "base64");
      if (chunk.toString("base64") !== encoded) {
        throw codedError(`MCP job ${jobId} returned non-canonical base64 artifact data.`, { code: "invalid_mcp_artifact" });
      }
      if (!chunk.length || chunk.length !== Number(fetched.returned_bytes) || offset + chunk.length > expectedBytes) {
        throw codedError(`MCP job ${jobId} returned an invalid artifact chunk.`, { code: "invalid_mcp_artifact" });
      }
      chunks.push(chunk);
      const next = fetched.next_offset;
      const expectedNext = offset + chunk.length;
      if (expectedNext < expectedBytes) {
        if (Number(next) !== expectedNext) throw codedError(`MCP job ${jobId} returned a discontinuous artifact chunk.`, { code: "invalid_mcp_artifact" });
        offset = expectedNext;
      } else {
        if (next !== null && next !== undefined) throw codedError(`MCP job ${jobId} returned an invalid terminal artifact offset.`, { code: "invalid_mcp_artifact" });
        offset = expectedNext;
      }
    }
    const bytes = Buffer.concat(chunks, expectedBytes);
    if (createHash("sha256").update(bytes).digest("hex") !== expectedSha) {
      throw codedError(`MCP job ${jobId} response artifact failed SHA-256 verification.`, { code: "mcp_artifact_sha256_mismatch" });
    }
    let data;
    try { data = JSON.parse(bytes.toString("utf8")); } catch {
      throw codedError(`MCP job ${jobId} response artifact is not valid JSON.`, { code: "invalid_mcp_artifact_json" });
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw codedError(`MCP job ${jobId} response artifact is not a JSON object.`, { code: "invalid_mcp_artifact_json" });
    }
    return data;
  }

  async call(skillId, payload, { idempotencyKey, onSubmitted = async () => {} } = {}) {
    const definition = MCP_MODELS[skillId];
    if (!definition) throw new InputError(`unsupported composed MCP model: ${skillId}`);
    const key = validatedIdempotencyKey(idempotencyKey);
    const started = this.nowImpl();
    const submission = await this.tool(definition.tool, {
      request: mcpRequest(skillId, payload),
      acknowledgements: { ...definition.acknowledgements },
      idempotency_key: key,
    });
    const jobId = submission?.job_id;
    if (typeof jobId !== "string" || !JOB_ID.test(jobId)) throw codedError("Cerebrium MCP submission did not return a valid job ID.", { code: "invalid_mcp_submission" });
    await onSubmitted({ jobId, state: submission.state, idempotentReplay: Boolean(submission.idempotent_replay) });

    let delayMs = TERMINAL_STATES.has(submission.state) ? 0 : Math.max(0, Math.min(Number(submission.poll_after_ms) || this.pollIntervalMs, 10_000));
    let status;
    for (let poll = 1; poll <= this.maxPolls; poll += 1) {
      if (this.nowImpl() - started > this.jobTimeoutMs) {
        throw codedError(`MCP job ${jobId} did not reach a terminal state within the bounded polling window.`, { code: "mcp_job_timeout", retryable: true });
      }
      if (delayMs > 0) await this.sleepImpl(delayMs);
      status = await this.tool("clawbio_job_status", { job_id: jobId });
      if (status?.job_id !== jobId || typeof status.state !== "string") {
        throw codedError(`MCP job ${jobId} returned an invalid status response.`, { code: "invalid_mcp_job_status" });
      }
      if (status.state === "failed") {
        const remoteCode = String(status.error?.code || "model_job_failed").replace(/[^A-Za-z0-9._-]/gu, "_").slice(0, 80);
        throw codedError(`MCP job ${jobId} failed (${remoteCode}); it was not resubmitted.`, {
          code: `mcp_${remoteCode}`,
          retryable: Boolean(status.error?.retryable),
        });
      }
      if (status.state === "succeeded") {
        const artifact = responseArtifact(status);
        const data = await this.fetchResponseJson(jobId, artifact);
        const elapsedMs = Math.max(0, this.nowImpl() - started);
        this.logger.info?.(`BioNeMo MCP ${skillId} job ${jobId.slice(0, 8)} completed (${elapsedMs} ms)`);
        return {
          skillId,
          elapsedMs,
          requestId: jobId,
          remoteJobId: jobId,
          remoteArtifacts: status.artifacts,
          data,
        };
      }
      if (!["queued", "starting", "running"].includes(status.state)) {
        throw codedError(`MCP job ${jobId} returned unsupported state ${String(status.state).slice(0, 40)}.`, { code: "invalid_mcp_job_status" });
      }
      delayMs = this.pollIntervalMs;
    }
    throw codedError(`MCP job ${jobId} exceeded the bounded poll-count limit without resubmission.`, { code: "mcp_job_poll_limit", retryable: true });
  }
}

export function selectedResearchBackend(env = process.env) {
  const requested = String(env.BIONEMO_BACKEND || "auto").toLowerCase();
  if (!["auto", "mcp", "nvidia"].includes(requested)) throw new InputError("BIONEMO_BACKEND must be auto, mcp, or nvidia");
  if (requested === "mcp") return env.BIONEMO_MCP_API_KEY || env.CLAWBIO_API_KEY ? "mcp" : "unavailable";
  if (requested === "nvidia") return env.NVIDIA_API_KEY || env.NGC_API_KEY ? "nvidia" : "unavailable";
  if (env.BIONEMO_MCP_API_KEY || env.CLAWBIO_API_KEY) return "mcp";
  if (env.NVIDIA_API_KEY || env.NGC_API_KEY) return "nvidia";
  return "unavailable";
}

export const __test = {
  MCP_MODELS,
  mcpRequest,
  parsedRpcMessage,
  readBodyLimited,
  responseArtifact,
  sanitizedTavilyResult,
  internalMcpUrl,
  validatedIdempotencyKey,
  validatedMcpUrl,
};
