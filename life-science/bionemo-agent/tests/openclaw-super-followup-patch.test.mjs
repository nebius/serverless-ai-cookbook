import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  BIONEMO_SUPER_CATALOG_PROMPT,
  BIONEMO_SUPER_INITIAL_TURNS,
  BIONEMO_SUPER_NOTEBOOK_TURNS,
  bionemoSuperBoundedResultSummary,
  bionemoSuperCompletedToolTarget,
  bionemoSuperDeterministicFinalText,
  bionemoSuperInitialNotebookTool,
  bionemoSuperShouldFinalizeWithoutTools,
  patchOpenClawSuperFollowup,
} from "../runtime/patch-openclaw-super-followup.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";
const superModel = { provider: "tokenfactory", id: "nvidia/nemotron-3-super-120b-a12b" };

function turn(name, { id = name, isError = false, arguments: args = {} } = {}) {
  return { messages: [
    { role: "user", content: [{ type: "text", text: "run" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "call-1", name, arguments: name === "tool_call" ? { id, ...args } : args }] },
    { role: "toolResult", toolCallId: "call-1", toolName: name, isError, content: [{ type: "text", text: "done" }] },
  ] };
}

test("Super finalizes after atomic wrappers and successful catalog lookup only", () => {
  for (const name of ["bionemo_research_drug_demo", "bionemo_compare_protein_structures", "bionemo_optimize_ligand_complex", "bionemo_batch_fold_demo"]) {
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name)), true);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name, { isError: true })), false);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("tool_call", { id: `openclaw:bionemo-agent-toolkit:${name}` })), true);
    assert.equal(bionemoSuperCompletedToolTarget(superModel, turn(name)), name);
    assert.match(bionemoSuperDeterministicFinalText(superModel, turn(name)), /returned a terminal result/u);
  }
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_models__models_list")), true);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_models__models_list", { isError: true })), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("tool_call", { id: "mcp:bundle-mcp:clawbio_models__models_list" })), true);
  const errored = structuredClone(turn("bionemo_compare_protein_structures"));
  errored.messages.at(-1).error = { code: "failed" };
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, errored), false);
});

test("Super initial calls are source-owned only for exact reviewed prompts", () => {
  assert.equal(BIONEMO_SUPER_NOTEBOOK_TURNS.length, 4);
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS.length, 5);
  for (const expected of BIONEMO_SUPER_INITIAL_TURNS) {
    const actual = bionemoSuperInitialNotebookTool(superModel, {
      messages: [{ role: "user", content: [{ type: "text", text: expected.prompt }] }],
    });
    assert.deepEqual(actual, { name: expected.name, params: { ...expected.params } });
  }
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS.at(-1).prompt, BIONEMO_SUPER_CATALOG_PROMPT);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [{ role: "user", content: `${BIONEMO_SUPER_CATALOG_PROMPT} ` }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool({ ...superModel, provider: "nvidia" }, { messages: [{ role: "user", content: BIONEMO_SUPER_CATALOG_PROMPT }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [
    { role: "user", content: BIONEMO_SUPER_CATALOG_PROMPT },
    { role: "toolResult", toolName: "clawbio_models__models_list" },
  ] }), undefined);
});

test("Super fallback includes only a bounded workflow summary", () => {
  const context = turn("bionemo_compare_protein_structures");
  context.messages.at(-1).content = [{ type: "text", text: JSON.stringify({
    summary: { predictions: { openfold2: { confidence: { ptm_score: 0.81 } }, openfold3: { confidence: { ptm_score: 0.87 } } }, note: "safe" },
    artifacts: [{ viewerMarkdown: "access=must-not-appear" }],
  }) }];
  const summary = bionemoSuperBoundedResultSummary(superModel, context);
  assert.match(summary, /ptm_score/u);
  assert.doesNotMatch(summary, /must-not-appear/u);
  assert.match(bionemoSuperDeterministicFinalText(superModel, context), /Returned workflow summary/u);
});

test("Super guard leaves initial, other-model, mismatched, and compute/status chains untouched", () => {
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, { messages: [{ role: "user", content: [] }] }), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...superModel, id: "deepseek-ai/DeepSeek-V4-Pro" }, turn("bionemo_batch_fold_demo")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_openfold2_predict")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_job_status")), false);
  const mismatch = structuredClone(turn("bionemo_batch_fold_demo"));
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, mismatch), false);
});

test("pinned transport patch is hash-gated, idempotent, and runs after payload callbacks", { timeout: 120_000 }, async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-super-followup-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const { stdout } = await execFileAsync("docker", ["create", PINNED_IMAGE]);
  const container = stdout.trim();
  t.after(() => execFileAsync("docker", ["rm", "-f", container]).catch(() => {}));
  await execFileAsync("docker", ["cp", `${container}:/app/dist`, path.join(root, "dist")]);
  await execFileAsync("docker", ["rm", container]);
  const distRoot = path.join(root, "dist");
  assert.equal((await patchOpenClawSuperFollowup(distRoot)).changed, true);
  assert.equal((await patchOpenClawSuperFollowup(distRoot)).changed, false);
  const names = (await import("node:fs/promises")).readdir(distRoot);
  const file = (await names).find((name) => name.startsWith("openai-transport-stream-") && name.endsWith(".js"));
  const source = await readFile(path.join(distRoot, file), "utf8");
  assert.match(source, /openclaw\.bionemo\.super-followup\.v3/u);
  const callback = source.indexOf("if (nextParams !== void 0) params = nextParams;");
  const codeMode = source.indexOf("if (options?.openclawCodeModeToolSurface === true)", callback);
  const guard = source.indexOf("if (bionemoSuperShouldFinalizeWithoutTools(model, context))");
  const request = source.indexOf("client.chat.completions.create(params");
  assert.ok(callback >= 0 && callback < codeMode && codeMode < guard && guard < request);
  assert.match(source, /delete params\.tools;\s*params\.tool_choice = "none";/su);
  assert.match(source, /bionemoSuperFinalText: bionemoSuperDeterministicFinalText\(model, context\)/u);
  assert.match(source, /if \(!bionemoSuperFinalText && !bionemoSuperInitialTool && choiceDelta\.tool_calls/u);
  assert.match(source, /if \(choiceDelta\.content && !bionemoSuperFinalText && !bionemoSuperInitialTool\)/u);
  assert.match(source, /appendTextDelta\(bionemoSuperFinalText\)/u);
  assert.match(source, /params\.tool_choice = \{ type: "function", function: \{ name: bionemoSuperInitialTool\.name \} \}/u);
  await execFileAsync(process.execPath, ["--check", path.join(distRoot, file)]);

  const testingSource = source.replace(
    "export { ",
    "export { processOpenAICompletionsStream as __bionemoProcessOpenAICompletionsStream, ",
  );
  assert.notEqual(testingSource, source);
  await writeFile(path.join(distRoot, file), testingSource);
  const expectedInitial = BIONEMO_SUPER_NOTEBOOK_TURNS[1];
  const integrationScript = `
    import assert from "node:assert/strict";
    const patched = await import("file:///app/dist/${file}?test=" + Date.now());
    const model = ${JSON.stringify({ ...superModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 262_144, maxTokens: 8_192, compat: { maxTokensField: "max_tokens", requiresStringContent: true } })};
    const expectedInitial = ${JSON.stringify({ name: expectedInitial.name, params: { ...expectedInitial.params } })};
    const output = () => ({ role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } }, stopReason: "stop", timestamp: Date.now() });
    const chunks = () => (async function* providerChunks() { yield { id: "response-1", choices: [{ index: 0, delta: { content: "<tool_call><function=read><parameter=path>artifact.pdb</parameter></function></tool_call>", tool_calls: [{ index: 0, id: "provider-call", type: "function", function: { name: "babel", arguments: "{}" } }] }, finish_reason: "tool_calls" }] }; }());
    const initialOutput = output();
    const initialEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), initialOutput, model, { push: (event) => initialEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperInitialTool: expectedInitial });
    assert.equal(initialOutput.stopReason, "toolUse");
    assert.deepEqual(initialOutput.content.filter(({ type }) => type === "toolCall").map(({ name, arguments: args }) => ({ name, args })), [{ name: expectedInitial.name, args: expectedInitial.params }]);
    assert.equal(initialOutput.content.some(({ type }) => type === "text"), false);
    assert.deepEqual(initialEvents.filter(({ type }) => type === "toolcall_start").map(({ partial }) => partial.content.at(-1).name), [expectedInitial.name]);
    assert.equal(initialEvents.filter(({ type }) => type === "toolcall_delta").length, 1);
    const finalOutput = output();
    const finalEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), finalOutput, model, { push: (event) => finalEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperFinalText: "Deterministic completed result." });
    assert.equal(finalOutput.stopReason, "stop");
    assert.equal(finalOutput.content.some(({ type }) => type === "toolCall"), false);
    assert.equal(finalOutput.content.filter(({ type }) => type === "text").map(({ text }) => text).join(""), "Deterministic completed result.");
    assert.equal(JSON.stringify(finalOutput).includes("<tool_call>"), false);
    assert.equal(finalEvents.some(({ type }) => type.startsWith("toolcall_")), false);
  `;
  await execFileAsync("docker", [
    "run", "--rm", "--network", "none", "--entrypoint", "node",
    "--mount", `type=bind,src=${path.join(distRoot, file)},dst=/app/dist/${file},readonly`,
    PINNED_IMAGE, "--input-type=module", "-e", integrationScript,
  ]);
});
