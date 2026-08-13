import path from "node:path";
import { atomicWrite, capabilities } from "./runtime-config.mjs";

function tomlString(value) {
  return JSON.stringify(value);
}

export async function prepareClients(env = process.env) {
  const state = capabilities(env);
  const codex = [
    "# Generated at container start. Contains environment-variable names only, never credentials.",
    'cli_auth_credentials_store = "file"',
    "",
    "[mcp_servers.clawbio]",
    'command = "/opt/clawbio/bin/python"',
    'args = ["/opt/bionemo/runtime/clawbio-mcp.py"]',
    'cwd = "/workspace/agent/artifacts/clawbio"',
    "tool_timeout_sec = 300",
    "",
    "[mcp_servers.bionemo_models]",
    `url = ${tomlString(state.mcpUrl)}`,
    "tool_timeout_sec = 900",
  ];
  const claude = {
    mcpServers: {
      clawbio: {
        type: "stdio",
        command: "/opt/clawbio/bin/python",
        args: ["/opt/bionemo/runtime/clawbio-mcp.py"],
        cwd: "/workspace/agent/artifacts/clawbio",
      },
      bionemo_models: { type: "http", url: state.mcpUrl },
    },
  };
  if (state.mcp) {
    codex.push('bearer_token_env_var = "BIONEMO_MCP_API_KEY"');
    claude.mcpServers.bionemo_models.headers = { Authorization: "Bearer ${BIONEMO_MCP_API_KEY}" };
  }
  if (state.tavily) {
    codex.push("", "[mcp_servers.tavily_web]", 'url = "https://mcp.tavily.com/mcp/"', 'bearer_token_env_var = "TAVILY_API_KEY"', "tool_timeout_sec = 120");
    claude.mcpServers.tavily_web = { type: "http", url: "https://mcp.tavily.com/mcp/", headers: { Authorization: "Bearer ${TAVILY_API_KEY}" } };
  }
  const home = env.HOME || "/home/node";
  await atomicWrite(path.join(home, ".codex", "config.toml"), `${codex.join("\n")}\n`);
  await atomicWrite(path.join(env.BIONEMO_CLIENT_WORKSPACE || "/workspace/agent", ".mcp.json"), `${JSON.stringify(claude, null, 2)}\n`);
  return state;
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  prepareClients().catch((error) => { process.stderr.write(`BioNeMo client configuration failed: ${error.message}\n`); process.exitCode = 78; });
}
