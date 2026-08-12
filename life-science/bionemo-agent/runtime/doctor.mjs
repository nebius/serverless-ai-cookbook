import { spawnSync } from "node:child_process";
import { capabilities } from "./runtime-config.mjs";

function version(command, args = ["--version"]) {
  const result = spawnSync(command, args, { encoding: "utf8", env: { ...process.env, NO_COLOR: "1" } });
  return result.status === 0 ? (result.stdout || result.stderr).trim().split("\n")[0] : "not installed";
}

async function skillCount(root) {
  const result = spawnSync("find", [root, "-mindepth", "2", "-maxdepth", "2", "-name", "SKILL.md"], { encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim().split("\n").filter(Boolean).length : 0;
}

const state = capabilities(process.env);
const report = {
  status: state.reasoning && state.modelBackend !== "unavailable" ? "ready" : "setup_required",
  agents: { openclaw: version("node", ["/app/openclaw.mjs", "--version"]), codex: version("codex"), claude: version("claude") },
  skills: { codex: await skillCount("/etc/codex/skills"), claude: await skillCount("/home/node/.claude/skills") },
  configured: { reasoning: state.reasoning, reasoningProvider: state.reasoningProvider, modelBackend: state.modelBackend, nvidia: state.nvidia, nebius: state.nebius, mcp: state.mcp, tavily: state.tavily },
  mcpUrl: state.mcpUrl,
  credentialsStoredInImage: false,
};
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
