import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

// These anchors intentionally match the exact OpenClaw image digest pinned in
// Dockerfile. A version drift must fail the image build instead of silently
// dropping the trusted per-run hook context.
const HOOK_IMPORT = 'import { p as wrapToolWithBeforeToolCallHook } from "./agent-tools.before-tool-call-C95DXQXZ.js";';
const MATERIALIZE_IMPORT_ANCHOR = 'import { s as setPluginToolMeta } from "./tools-V54L2wjJ.js";';
const MATERIALIZE_WRAP_ANCHOR = "\t\t}),\n\t\t...catalog.diagnostics && catalog.diagnostics.length > 0";
const MATERIALIZE_WRAP_REPLACEMENT = "\t\t}).map((agentTool) => params.toolHookContext\n\t\t\t? wrapToolWithBeforeToolCallHook(agentTool, params.toolHookContext)\n\t\t\t: agentTool),\n\t\t...catalog.diagnostics && catalog.diagnostics.length > 0";
const SELECTION_CALL_ANCHOR = "\t\t\treservedToolNames: [...tools.map((tool) => tool.name), ...clientTools?.map((tool) => tool.function.name) ?? []]\n\t\t}) : void 0;";
const SELECTION_CALL_REPLACEMENT = "\t\t\treservedToolNames: [...tools.map((tool) => tool.name), ...clientTools?.map((tool) => tool.function.name) ?? []],\n\t\t\ttoolHookContext: {\n\t\t\t\tagentId: sessionAgentId,\n\t\t\t\tconfig: params.config,\n\t\t\t\tsessionKey: params.sessionKey,\n\t\t\t\tsessionId: params.sessionId,\n\t\t\t\trunId: params.runId\n\t\t\t}\n\t\t}) : void 0;";

function replaceExactlyOnce(source, anchor, replacement, label) {
  const first = source.indexOf(anchor);
  if (first < 0 || source.indexOf(anchor, first + anchor.length) >= 0) {
    throw new Error(`Pinned OpenClaw compatibility check failed for ${label}`);
  }
  return `${source.slice(0, first)}${replacement}${source.slice(first + anchor.length)}`;
}

async function findChunk(distRoot, prefix, marker) {
  const names = (await readdir(distRoot)).filter((name) => name.startsWith(prefix) && name.endsWith(".js"));
  const matches = [];
  for (const name of names) {
    const filePath = path.join(distRoot, name);
    const source = await readFile(filePath, "utf8");
    if (source.includes(marker)) matches.push({ filePath, source });
  }
  if (matches.length !== 1) {
    throw new Error(`Expected exactly one pinned OpenClaw ${prefix} chunk, found ${matches.length}`);
  }
  return matches[0];
}

async function atomicRewrite(filePath, source) {
  const temporary = `${filePath}.bionemo-${process.pid}.tmp`;
  await writeFile(temporary, source, { encoding: "utf8", mode: 0o644, flag: "wx" });
  await rename(temporary, filePath);
}

export async function patchOpenClawMcpTurnContext(distRoot) {
  if (!distRoot) throw new Error("OpenClaw dist root is required");
  const materialize = await findChunk(distRoot, "agent-bundle-mcp-materialize-", "async function materializeBundleMcpToolsForRun");
  const selection = await findChunk(distRoot, "selection-", "bundleMcpRuntime = bundleMcpSessionRuntime ? await materializeBundleMcpToolsForRun");

  const fullyPatched = materialize.source.includes(HOOK_IMPORT)
    && materialize.source.includes("wrapToolWithBeforeToolCallHook(agentTool, params.toolHookContext)")
    && selection.source.includes(SELECTION_CALL_REPLACEMENT);
  if (fullyPatched) return { changed: false, materializePath: materialize.filePath, selectionPath: selection.filePath };
  const partiallyPatchedSelection = selection.source.includes(
    `${SELECTION_CALL_ANCHOR.split("\n")[0]},\n\t\t\ttoolHookContext:`,
  );
  if (materialize.source.includes(HOOK_IMPORT) || materialize.source.includes("params.toolHookContext") || partiallyPatchedSelection) {
    throw new Error("Refusing to modify a partially patched OpenClaw runtime");
  }

  let materializeSource = replaceExactlyOnce(
    materialize.source,
    MATERIALIZE_IMPORT_ANCHOR,
    `${MATERIALIZE_IMPORT_ANCHOR}\n${HOOK_IMPORT}`,
    "bundle MCP hook import",
  );
  materializeSource = replaceExactlyOnce(
    materializeSource,
    MATERIALIZE_WRAP_ANCHOR,
    MATERIALIZE_WRAP_REPLACEMENT,
    "bundle MCP tool hook wrapper",
  );
  const selectionSource = replaceExactlyOnce(
    selection.source,
    SELECTION_CALL_ANCHOR,
    SELECTION_CALL_REPLACEMENT,
    "bundle MCP per-turn hook context",
  );

  await atomicRewrite(materialize.filePath, materializeSource);
  await atomicRewrite(selection.filePath, selectionSource);
  return { changed: true, materializePath: materialize.filePath, selectionPath: selection.filePath };
}

async function main() {
  const [distRoot] = process.argv.slice(2);
  const result = await patchOpenClawMcpTurnContext(distRoot);
  process.stdout.write(`BioNeMo OpenClaw MCP turn-context patch: ${result.changed ? "applied" : "already applied"}.\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`BioNeMo OpenClaw compatibility patch failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
