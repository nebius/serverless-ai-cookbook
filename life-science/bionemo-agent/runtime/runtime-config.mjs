import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { CROSS_BACKEND_TOOL_NAMES, DIRECT_ONLY_TOOL_NAMES } from "../openclaw-plugin/src/catalog.mjs";

export const DEFAULT_MCP_URL = "https://api.cerebrium.ai/v4/p-12ff482a/clawbio-models-mcp-public/mcp";
export const NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b";
export const NEBIUS_MODEL = "deepseek-ai/DeepSeek-V4-Pro";
export const OPENAI_MODEL = "gpt-5.6";
export const ANTHROPIC_MODEL = "claude-sonnet-5";
// Keep all eight evaluated candidates here so known failures remain blocked
// even when an operator supplies their exact id through AGENT_MODEL.
export const TOKEN_FACTORY_QUALIFICATION = Object.freeze([
  Object.freeze({ id: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", alias: "Nemotron 3 Nano", qualified: false, reason: "truncated the optimized-ligand notebook after successful compute and omitted the OpenFold3 result, artifact links, and limitations" }),
  Object.freeze({ id: "nvidia/Nemotron-3_5-Lightning", alias: "Nemotron 3.5 Lightning", qualified: false, reason: "emitted string sentinels for nullable structured fields and attempted false consent acknowledgements" }),
  Object.freeze({ id: "nvidia/nemotron-3-super-120b-a12b", alias: "Nemotron 3 Super", qualified: false, reason: "made two structured calls to nonexistent MCP tool names before its third successful catalog call" }),
  Object.freeze({ id: "nvidia/Nemotron-3-Ultra-550b-a55b", alias: "Nemotron 3 Ultra", qualified: false, reason: "returned an unrelated workflow instead of the requested exact response in clean endpoint acceptance" }),
  Object.freeze({ id: "openai/gpt-oss-120b", alias: "GPT-OSS 120B", qualified: false, reason: "attempted model submissions without every required user acknowledgement" }),
  Object.freeze({ id: "Qwen/Qwen3-32B", alias: "Qwen3 32B", qualified: false, reason: "emitted visible provider-side reasoning tags and did not meet the presentation gate" }),
  Object.freeze({ id: "zai-org/GLM-5.1", alias: "GLM 5.1", qualified: false, reason: "failed the deployed OpenClaw MCP catalog turn with no structured tool call or final response" }),
  Object.freeze({ id: NEBIUS_MODEL, alias: "DeepSeek V4 Pro", contextWindow: 1048576, maxTokens: 8192 }),
]);

export const TOKEN_FACTORY_MODELS = Object.freeze(
  TOKEN_FACTORY_QUALIFICATION.filter(({ qualified }) => qualified !== false),
);
export const TOKEN_FACTORY_REJECTED_MODELS = Object.freeze(
  TOKEN_FACTORY_QUALIFICATION.filter(({ qualified }) => qualified === false),
);

export function parseBoolean(value, fallback = false) {
  if (value === undefined || value === "") return fallback;
  if (["1", "true", "yes", "on"].includes(String(value).toLowerCase())) return true;
  if (["0", "false", "no", "off"].includes(String(value).toLowerCase())) return false;
  throw new Error(`Invalid boolean value: ${value}`);
}

export function validatedRemoteUrl(value, env = process.env) {
  const url = new URL(value || DEFAULT_MCP_URL);
  if (url.username || url.password || url.search || url.hash) throw new Error("MCP URL must not contain credentials, a query, or a fragment");
  const insecureAllowed = parseBoolean(env.BIONEMO_ALLOW_INSECURE_MCP, false);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && insecureAllowed)) {
    throw new Error("MCP URL must use HTTPS (or explicitly set BIONEMO_ALLOW_INSECURE_MCP=true for a trusted private endpoint)");
  }
  return url.toString();
}

export function normalizedEnvironment(env = process.env) {
  const output = { ...env };
  if (!output.BIONEMO_MCP_API_KEY && output.CLAWBIO_API_KEY) output.BIONEMO_MCP_API_KEY = output.CLAWBIO_API_KEY;
  if (!output.NVIDIA_API_KEY && output.NGC_API_KEY) output.NVIDIA_API_KEY = output.NGC_API_KEY;
  output.BIONEMO_MCP_URL = validatedRemoteUrl(output.BIONEMO_MCP_URL || DEFAULT_MCP_URL, output);
  return output;
}

export function capabilities(env = process.env) {
  const normalized = normalizedEnvironment(env);
  const explicitProvider = String(normalized.AGENT_PROVIDER || "auto").toLowerCase();
  if (!["auto", "nvidia", "nebius", "openai", "anthropic", "claude", "setup"].includes(explicitProvider)) throw new Error("AGENT_PROVIDER must be auto, nvidia, nebius, openai, anthropic (or claude), or setup");
  let reasoningProvider = explicitProvider === "claude" ? "anthropic" : explicitProvider;
  if (reasoningProvider === "auto") reasoningProvider = normalized.NVIDIA_API_KEY ? "nvidia" : normalized.NEBIUS_API_KEY ? "nebius" : normalized.OPENAI_API_KEY ? "openai" : normalized.ANTHROPIC_API_KEY ? "anthropic" : "setup";
  if (reasoningProvider === "nvidia" && !normalized.NVIDIA_API_KEY) reasoningProvider = "setup";
  if (reasoningProvider === "nebius" && !normalized.NEBIUS_API_KEY) reasoningProvider = "setup";
  if (reasoningProvider === "openai" && !normalized.OPENAI_API_KEY) reasoningProvider = "setup";
  if (reasoningProvider === "anthropic" && !normalized.ANTHROPIC_API_KEY) reasoningProvider = "setup";

  const requestedBackend = String(normalized.BIONEMO_BACKEND || "auto").toLowerCase();
  if (!["auto", "mcp", "nvidia"].includes(requestedBackend)) throw new Error("BIONEMO_BACKEND must be auto, mcp, or nvidia");
  let modelBackend = requestedBackend;
  if (modelBackend === "auto") modelBackend = normalized.BIONEMO_MCP_API_KEY ? "mcp" : normalized.NVIDIA_API_KEY ? "nvidia" : "unavailable";
  if (modelBackend === "mcp" && !normalized.BIONEMO_MCP_API_KEY) modelBackend = "unavailable";
  if (modelBackend === "nvidia" && !normalized.NVIDIA_API_KEY) modelBackend = "unavailable";

  return {
    env: normalized,
    reasoningProvider,
    modelBackend,
    reasoning: reasoningProvider !== "setup",
    nvidia: Boolean(normalized.NVIDIA_API_KEY),
    nebius: Boolean(normalized.NEBIUS_API_KEY),
    openai: Boolean(normalized.OPENAI_API_KEY),
    anthropic: Boolean(normalized.ANTHROPIC_API_KEY),
    mcp: Boolean(normalized.BIONEMO_MCP_API_KEY),
    tavily: Boolean(normalized.BIONEMO_TAVILY_API_KEY || normalized.TAVILY_API_KEY),
    mcpUrl: normalized.BIONEMO_MCP_URL,
  };
}

export function configureOpenClaw(config, env = process.env, setupPort = 18790) {
  const state = capabilities(env);
  config.models = { mode: "merge", providers: {} };
  const setupBaseUrl = `http://127.0.0.1:${setupPort}/v1`;
  const modelId = (provider, fallback) => state.reasoningProvider === provider && state.env.AGENT_MODEL ? state.env.AGENT_MODEL : fallback;
  const compatibleProvider = ({ configured, baseUrl, apiKey, api, models, agentRuntime, timeoutSeconds }) => {
    const definitions = models.map(({ id, name = id, contextWindow = 262144, maxTokens = 8192, reasoning = true, compat }) => {
      const definition = { id, name: `${name}${configured ? "" : " (requires API key)"}`, reasoning: configured && reasoning, input: ["text"], contextWindow, maxTokens: configured ? maxTokens : 1024 };
      if (agentRuntime) definition.agentRuntime = agentRuntime;
      if (compat) definition.compat = { ...compat };
      return definition;
    });
    return {
      baseUrl: configured ? baseUrl : setupBaseUrl,
      apiKey: configured ? apiKey : "setup-required",
      api: configured ? api : "openai-completions",
      authHeader: true,
      ...(timeoutSeconds ? { timeoutSeconds } : {}),
      models: definitions,
    };
  };
  const nvidiaModel = modelId("nvidia", NVIDIA_MODEL);
  const nvidiaUsesDefault = nvidiaModel.toLowerCase() === NVIDIA_MODEL.toLowerCase();
  const requestedNebiusModel = modelId("nebius", NEBIUS_MODEL);
  const rejectedNebiusModel = TOKEN_FACTORY_REJECTED_MODELS.find(({ id }) => id.toLowerCase() === requestedNebiusModel.toLowerCase());
  if (rejectedNebiusModel) {
    throw new Error(`AGENT_MODEL ${rejectedNebiusModel.id} is not available because it failed the BioNeMo workflow qualification gate: ${rejectedNebiusModel.reason}`);
  }
  const knownNebiusModel = TOKEN_FACTORY_MODELS.find(({ id }) => id.toLowerCase() === requestedNebiusModel.toLowerCase());
  const nebiusModel = knownNebiusModel?.id || requestedNebiusModel;
  const tokenFactoryModels = knownNebiusModel
    ? TOKEN_FACTORY_MODELS
    : Object.freeze([...TOKEN_FACTORY_MODELS, Object.freeze({ id: nebiusModel, contextWindow: 262144, maxTokens: 8192 })]);
  const openaiModel = modelId("openai", OPENAI_MODEL);
  const anthropicModel = modelId("anthropic", ANTHROPIC_MODEL);
  config.models.providers.nvidia = compatibleProvider({
    configured: state.nvidia,
    baseUrl: state.reasoningProvider === "nvidia" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://integrate.api.nvidia.com/v1",
    apiKey: "${NVIDIA_API_KEY}",
    api: "openai-completions",
    // NVIDIA Build can occasionally take more than OpenClaw's 120-second
    // provider idle default to begin the post-tool narration. Keep the overall
    // agent ceiling at 30 minutes, but give this hosted provider a bounded
    // four-minute first-byte window so a completed NIM result is not discarded.
    timeoutSeconds: 240,
    models: [{
      id: nvidiaModel,
      name: `${nvidiaModel} via NVIDIA Build`,
      contextWindow: nvidiaUsesDefault ? 1_000_000 : 262_144,
      maxTokens: 8_192,
      // The pinned OpenClaw release otherwise assumes max_completion_tokens
      // for a configured non-OpenAI endpoint. NVIDIA's hosted Super route uses
      // max_tokens and expects string content across tool-result turns.
      compat: nvidiaUsesDefault
        ? { maxTokensField: "max_tokens", requiresStringContent: true }
        : undefined,
    }],
  });
  config.models.providers.tokenfactory = compatibleProvider({ configured: state.nebius, baseUrl: state.reasoningProvider === "nebius" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://api.tokenfactory.nebius.com/v1", apiKey: "${NEBIUS_API_KEY}", api: "openai-completions", models: tokenFactoryModels.map((model) => ({ ...model, name: `${model.alias || model.id} via Nebius Token Factory` })) });
  config.models.providers.openai = compatibleProvider({ configured: state.openai, baseUrl: state.reasoningProvider === "openai" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://api.openai.com/v1", apiKey: "${OPENAI_API_KEY}", api: "openai-responses", models: [{ id: openaiModel, name: `${openaiModel} via OpenAI` }], agentRuntime: { id: "openclaw" } });
  config.models.providers.claude = compatibleProvider({ configured: state.anthropic, baseUrl: state.reasoningProvider === "anthropic" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://api.anthropic.com", apiKey: "${ANTHROPIC_API_KEY}", api: "anthropic-messages", models: [{ id: anthropicModel, name: `${anthropicModel} via Anthropic Claude`, contextWindow: 200000 }] });
  config.models.providers.setup = {
    baseUrl: setupBaseUrl, apiKey: "setup-required", api: "openai-completions",
    models: [{ id: "setup-required", name: "Setup required", reasoning: false, input: ["text"], contextWindow: 262144, maxTokens: 1024 }],
  };
  const primaryModels = {
    nvidia: `nvidia/${nvidiaModel}`,
    nebius: `tokenfactory/${nebiusModel}`,
    openai: `openai/${openaiModel}`,
    anthropic: `claude/${anthropicModel}`,
    setup: "setup/setup-required",
  };
  config.agents.defaults.model.primary = primaryModels[state.reasoningProvider];
  config.agents.defaults.models = {
    // Disabling template thinking keeps normal answers visible and produced
    // structured tool_calls with Super in the release matrix; Nano emitted
    // raw tool JSON in 6/6 probes.
    [`nvidia/${nvidiaModel}`]: nvidiaUsesDefault
      ? { params: { chat_template_kwargs: { enable_thinking: false, force_nonempty_content: true } } }
      : {},
    ...Object.fromEntries(tokenFactoryModels.map(({ id, alias }) => [`tokenfactory/${id}`, alias ? { alias } : {}])),
    [`openai/${openaiModel}`]: {},
    [`claude/${anthropicModel}`]: {},
  };

  config.mcp = { sessionIdleTtlMs: 600000, servers: {} };
  const useClawBioMcp = state.modelBackend === "mcp";
  if (useClawBioMcp) {
    config.mcp.servers.clawbio_models = {
      url: state.mcpUrl, transport: "streamable-http", timeout: 900,
      headers: { Authorization: "Bearer ${BIONEMO_MCP_API_KEY}" },
    };
  }
  if (state.tavily) {
    // Avoid the reserved official-plugin id `tavily`: OpenClaw otherwise
    // attempts a runtime npm install of @openclaw/tavily-plugin. This image
    // intentionally ships without a package manager, so use the generic
    // Streamable HTTP MCP transport under a distinct stable alias.
    config.mcp.servers.tavily_web = {
      url: "https://mcp.tavily.com/mcp/", transport: "streamable-http", timeout: 120,
      headers: { Authorization: "Bearer ${BIONEMO_TAVILY_API_KEY}", DEFAULT_PARAMETERS: "{\"search_depth\":\"basic\",\"max_results\":5,\"include_raw_content\":false,\"include_images\":false}" },
    };
  }
  if (useClawBioMcp || state.tavily) {
    config.tools.deny = config.tools.deny.filter((name) => name !== "bundle-mcp");
    if (!config.tools.alsoAllow.includes("bundle-mcp")) config.tools.alsoAllow.push("bundle-mcp");
  }
  if (useClawBioMcp) {
    // Never show two incompatible contracts for the same BioNeMo operation.
    // The remote MCP adapter is the selected backend, so hide the direct NIM
    // plugin tools instead of asking the reasoning model to choose between a
    // flat direct schema and an enveloped remote schema.
    const directTools = new Set(DIRECT_ONLY_TOOL_NAMES);
    config.tools.alsoAllow = config.tools.alsoAllow.filter((name) => !directTools.has(name));
    for (const name of CROSS_BACKEND_TOOL_NAMES) {
      if (!config.tools.alsoAllow.includes(name)) config.tools.alsoAllow.push(name);
    }
    for (const name of DIRECT_ONLY_TOOL_NAMES) {
      if (!config.tools.deny.includes(name)) config.tools.deny.push(name);
    }
    config.tools.deny = config.tools.deny.filter((name) => !CROSS_BACKEND_TOOL_NAMES.includes(name));
  }
  return state;
}

export async function atomicWrite(filePath, content, mode = 0o600) {
  await mkdir(path.dirname(filePath), { recursive: true, mode: 0o700 });
  const temporary = `${filePath}.tmp-${process.pid}`;
  await writeFile(temporary, content, { encoding: "utf8", mode });
  await rename(temporary, filePath);
}
