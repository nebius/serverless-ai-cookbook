import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

export const DEFAULT_MCP_URL = "https://api.cerebrium.ai/v4/p-12ff482a/clawbio-models-mcp-public/mcp";
export const NVIDIA_MODEL = "nvidia/nemotron-3-nano-30b-a3b";
export const NEBIUS_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B";
export const OPENAI_MODEL = "gpt-5.6";
export const ANTHROPIC_MODEL = "claude-sonnet-5";

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
  if (!["auto", "nvidia", "nebius", "openai", "anthropic", "setup"].includes(explicitProvider)) throw new Error("AGENT_PROVIDER must be auto, nvidia, nebius, openai, anthropic, or setup");
  let reasoningProvider = explicitProvider;
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
    tavily: Boolean(normalized.TAVILY_API_KEY),
    mcpUrl: normalized.BIONEMO_MCP_URL,
  };
}

export function configureOpenClaw(config, env = process.env, setupPort = 18790) {
  const state = capabilities(env);
  config.models = { mode: "merge", providers: {} };
  const setupBaseUrl = `http://127.0.0.1:${setupPort}/v1`;
  const modelId = (provider, fallback) => state.reasoningProvider === provider && state.env.AGENT_MODEL ? state.env.AGENT_MODEL : fallback;
  const compatibleProvider = ({ configured, baseUrl, apiKey, api, model, name, contextWindow = 262144 }) => ({
    baseUrl: configured ? baseUrl : setupBaseUrl,
    apiKey: configured ? apiKey : "setup-required",
    api: configured ? api : "openai-completions",
    authHeader: true,
    models: [{ id: model, name: `${name}${configured ? "" : " (requires API key)"}`, reasoning: configured, input: ["text"], contextWindow, maxTokens: configured ? 8192 : 1024 }],
  });
  const nvidiaModel = modelId("nvidia", NVIDIA_MODEL);
  const nebiusModel = modelId("nebius", NEBIUS_MODEL);
  const openaiModel = modelId("openai", OPENAI_MODEL);
  const anthropicModel = modelId("anthropic", ANTHROPIC_MODEL);
  config.models.providers.nvidia = compatibleProvider({ configured: state.nvidia, baseUrl: state.reasoningProvider === "nvidia" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://integrate.api.nvidia.com/v1", apiKey: "${NVIDIA_API_KEY}", api: "openai-completions", model: nvidiaModel, name: `${nvidiaModel} via NVIDIA Build` });
  config.models.providers.tokenfactory = compatibleProvider({ configured: state.nebius, baseUrl: state.reasoningProvider === "nebius" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://api.tokenfactory.nebius.com/v1", apiKey: "${NEBIUS_API_KEY}", api: "openai-completions", model: nebiusModel, name: `${nebiusModel} via Nebius Token Factory` });
  config.models.providers.openai = compatibleProvider({ configured: state.openai, baseUrl: state.reasoningProvider === "openai" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://api.openai.com/v1", apiKey: "${OPENAI_API_KEY}", api: "openai-responses", model: openaiModel, name: `${openaiModel} via OpenAI` });
  config.models.providers.anthropic = compatibleProvider({ configured: state.anthropic, baseUrl: state.reasoningProvider === "anthropic" && state.env.AGENT_BASE_URL ? state.env.AGENT_BASE_URL : "https://api.anthropic.com", apiKey: "${ANTHROPIC_API_KEY}", api: "anthropic-messages", model: anthropicModel, name: `${anthropicModel} via Anthropic Claude`, contextWindow: 200000 });
  config.models.providers.setup = {
    baseUrl: setupBaseUrl, apiKey: "setup-required", api: "openai-completions",
    models: [{ id: "setup-required", name: "Setup required", reasoning: false, input: ["text"], contextWindow: 262144, maxTokens: 1024 }],
  };
  const primaryModels = {
    nvidia: `nvidia/${nvidiaModel}`,
    nebius: `tokenfactory/${nebiusModel}`,
    openai: `openai/${openaiModel}`,
    anthropic: `anthropic/${anthropicModel}`,
    setup: "setup/setup-required",
  };
  config.agents.defaults.model.primary = primaryModels[state.reasoningProvider];
  config.agents.defaults.models ||= {};
  config.agents.defaults.models[`openai/${openaiModel}`] = { agentRuntime: { id: "openclaw" } };

  config.mcp = { sessionIdleTtlMs: 600000, servers: {} };
  if (state.mcp) {
    config.mcp.servers.clawbio_models = {
      url: state.mcpUrl, transport: "streamable-http", timeout: 900,
      headers: { Authorization: "Bearer ${BIONEMO_MCP_API_KEY}" },
    };
  }
  if (state.tavily) {
    config.mcp.servers.tavily = {
      url: "https://mcp.tavily.com/mcp/", transport: "streamable-http", timeout: 120,
      headers: { Authorization: "Bearer ${TAVILY_API_KEY}", DEFAULT_PARAMETERS: "{\"search_depth\":\"basic\",\"max_results\":5,\"include_raw_content\":false,\"include_images\":false}" },
    };
  }
  if (state.mcp || state.tavily) {
    config.tools.deny = config.tools.deny.filter((name) => name !== "bundle-mcp");
    if (!config.tools.alsoAllow.includes("bundle-mcp")) config.tools.alsoAllow.push("bundle-mcp");
  }
  return state;
}

export async function atomicWrite(filePath, content, mode = 0o600) {
  await mkdir(path.dirname(filePath), { recursive: true, mode: 0o700 });
  const temporary = `${filePath}.tmp-${process.pid}`;
  await writeFile(temporary, content, { encoding: "utf8", mode });
  await rename(temporary, filePath);
}
