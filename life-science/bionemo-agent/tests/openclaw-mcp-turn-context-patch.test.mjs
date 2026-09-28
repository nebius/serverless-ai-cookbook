import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { patchOpenClawMcpTurnContext } from "../runtime/patch-openclaw-mcp-turn-context.mjs";

const MATERIALIZE_FIXTURE = `import { s as setPluginToolMeta } from "./tools-V54L2wjJ.js";
async function materializeBundleMcpToolsForRun(params) {
\treturn {
\t\ttools: buildBundleMcpToolsFromCatalog({
\t\t\tcatalog,
\t\t\treservedToolNames: params.reservedToolNames
\t\t}),
\t\t...catalog.diagnostics && catalog.diagnostics.length > 0 ? { diagnostics: catalog.diagnostics } : {}
\t};
}
`;

const SELECTION_FIXTURE = `bundleMcpRuntime = bundleMcpSessionRuntime ? await materializeBundleMcpToolsForRun({
\t\t\truntime: bundleMcpSessionRuntime,
\t\t\treservedToolNames: [...tools.map((tool) => tool.name), ...clientTools?.map((tool) => tool.function.name) ?? []]
\t\t}) : void 0;
`;

test("pinned OpenClaw bundle-MCP tools receive the active run hook context", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-openclaw-patch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const materializePath = path.join(root, "agent-bundle-mcp-materialize-fixture.js");
  const selectionPath = path.join(root, "selection-fixture.js");
  await writeFile(materializePath, MATERIALIZE_FIXTURE);
  await writeFile(selectionPath, SELECTION_FIXTURE);

  const first = await patchOpenClawMcpTurnContext(root);
  assert.equal(first.changed, true);
  const materialize = await readFile(materializePath, "utf8");
  const selection = await readFile(selectionPath, "utf8");
  assert.match(materialize, /wrapToolWithBeforeToolCallHook\(agentTool, params\.toolHookContext\)/u);
  assert.match(materialize, /agent-tools\.before-tool-call-C95DXQXZ\.js/u);
  assert.match(selection, /toolHookContext:/u);
  assert.match(selection, /sessionKey: params\.sessionKey/u);
  assert.match(selection, /runId: params\.runId/u);

  const second = await patchOpenClawMcpTurnContext(root);
  assert.equal(second.changed, false, "the build patch must be idempotent");
});

test("OpenClaw compatibility patch fails closed when the pinned shape changes", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-openclaw-patch-drift-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(
    path.join(root, "agent-bundle-mcp-materialize-drift.js"),
    MATERIALIZE_FIXTURE.replace("...catalog.diagnostics", "...changedCatalog.diagnostics"),
  );
  await writeFile(path.join(root, "selection-drift.js"), SELECTION_FIXTURE);
  await assert.rejects(() => patchOpenClawMcpTurnContext(root), /compatibility check failed/u);
});
