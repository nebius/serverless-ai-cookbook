import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
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
let clawbio = { validation: "missing" };
try {
  const manifest = JSON.parse(await readFile("/opt/clawbio/share/clawbio/image-manifest.json", "utf8"));
  const codexInstalled = await skillCount("/etc/codex/skills");
  const claudeInstalled = await skillCount("/root/.claude/skills");
  clawbio = {
    packaged: manifest.distributedSkillCount,
    cataloged: manifest.distributedCatalogCount,
    sourceCommit: manifest.sourceCommit,
    excludedProprietary: manifest.excludedSkills.length,
    codexInstalled,
    claudeInstalled,
    validation: manifest.distributedSkillCount === 95 && manifest.distributedCatalogCount === 95 && codexInstalled === 127 && claudeInstalled === 127 ? "ok" : "mismatch",
  };
} catch {
  // A concise missing/mismatch result is safer than exposing arbitrary file contents.
}
const report = {
  status: state.reasoning && state.modelBackend !== "unavailable" ? "ready" : "setup_required",
  agents: { openclaw: version("node", ["/app/openclaw.mjs", "--version"]), codex: version("codex"), claude: version("claude") },
  skills: { codex: await skillCount("/etc/codex/skills"), claude: await skillCount("/root/.claude/skills"), clawbio },
  ownerAdmin: {
    root: typeof process.getuid === "function" && process.getuid() === 0,
    shell: version("bash"),
    python: version("python3"),
    pip: version("pip"),
    npm: version("npm"),
    uv: version("uv"),
  },
  configured: { reasoning: state.reasoning, reasoningProvider: state.reasoningProvider, modelBackend: state.modelBackend, nvidia: state.nvidia, nebius: state.nebius, openai: state.openai, anthropic: state.anthropic, mcp: state.mcp, tavily: state.tavily },
  mcpUrl: state.mcpUrl,
  credentialsStoredInImage: false,
};
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
