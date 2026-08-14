import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
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
const deepSeekModel = { provider: "tokenfactory", id: "deepseek-ai/DeepSeek-V4-Pro" };

function turn(name, { id = name, isError = false, arguments: args = {} } = {}) {
  return { messages: [
    { role: "user", content: [{ type: "text", text: "run" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "call-1", name, arguments: name === "tool_call" ? { id, ...args } : args }] },
    { role: "toolResult", toolCallId: "call-1", toolName: name, isError, content: [{ type: "text", text: "done" }] },
  ] };
}

test("Token Factory Super and DeepSeek finalize after successful atomic wrappers only", () => {
  for (const name of ["bionemo_research_drug_demo", "bionemo_compare_protein_structures", "bionemo_optimize_ligand_complex", "bionemo_batch_fold_demo"]) {
    for (const model of [superModel, deepSeekModel]) {
      assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, turn(name)), true);
      assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, turn(name, { isError: true })), false);
      assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, turn("tool_call", { id: `openclaw:bionemo-agent-toolkit:${name}` })), true);
      assert.equal(bionemoSuperCompletedToolTarget(model, turn(name)), name);
      assert.match(bionemoSuperDeterministicFinalText(model, turn(name)), /returned a terminal result/u);
    }
  }
  const errored = structuredClone(turn("bionemo_compare_protein_structures"));
  errored.messages.at(-1).error = { code: "failed" };
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, errored), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, errored), false);
});

test("Super initial calls are source-owned only for exact reviewed prompts", () => {
  assert.equal(BIONEMO_SUPER_NOTEBOOK_TURNS.length, 4);
  assert.deepEqual(BIONEMO_SUPER_INITIAL_TURNS, BIONEMO_SUPER_NOTEBOOK_TURNS);
  for (const expected of BIONEMO_SUPER_INITIAL_TURNS) {
    const actual = bionemoSuperInitialNotebookTool(superModel, {
      messages: [{ role: "user", content: [{ type: "text", text: expected.prompt }] }],
    });
    assert.deepEqual(actual, { name: expected.name, params: { ...expected.params } });
  }
  const [first] = BIONEMO_SUPER_NOTEBOOK_TURNS;
  assert.equal(bionemoSuperInitialNotebookTool(deepSeekModel, { messages: [{ role: "user", content: first.prompt }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [{ role: "user", content: `${first.prompt} ` }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool({ ...superModel, provider: "nvidia" }, { messages: [{ role: "user", content: first.prompt }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [{ role: "user", content: "List all available BioNeMo models." }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [
    { role: "user", content: first.prompt },
    { role: "toolResult", toolName: first.name },
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

test("post-success guard leaves initial, unrelated tools/models, errors, and mismatched chains untouched", () => {
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, { messages: [{ role: "user", content: [] }] }), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...superModel, id: "meta/llama-3.3-70b-instruct" }, turn("bionemo_batch_fold_demo")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...deepSeekModel, provider: "nvidia" }, turn("bionemo_batch_fold_demo")), false);
  for (const name of ["openfold2_predict", "job_status", "clawbio__run_skill", "clawbio_run_skill", "tavily_search", "web_search"]) {
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name)), false);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, turn(name)), false);
  }
  const mismatch = structuredClone(turn("bionemo_batch_fold_demo"));
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, mismatch), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, mismatch), false);
  const multipleCalls = structuredClone(turn("bionemo_batch_fold_demo"));
  multipleCalls.messages.at(-2).content.push({ type: "toolCall", id: "call-2", name: "bionemo_batch_fold_demo", arguments: {} });
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, multipleCalls), false);
  const notImmediate = structuredClone(turn("bionemo_batch_fold_demo"));
  notImmediate.messages.splice(-1, 0, { role: "assistant", content: [{ type: "text", text: "intervening" }] });
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, notImmediate), false);
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
  assert.match(source, /openclaw\.bionemo\.super-followup\.v4/u);
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
    "export { processOpenAICompletionsStream as __bionemoProcessOpenAICompletionsStream, bionemoSuperDeterministicFinalText as __bionemoSuperDeterministicFinalText, bionemoSuperShouldFinalizeWithoutTools as __bionemoSuperShouldFinalizeWithoutTools, ",
  );
  assert.notEqual(testingSource, source);
  await writeFile(path.join(distRoot, file), testingSource);
  const expectedInitial = BIONEMO_SUPER_NOTEBOOK_TURNS[1];
  const integrationScript = `
    import assert from "node:assert/strict";
    const patched = await import("file:///app/dist/${file}?test=" + Date.now());
    const model = ${JSON.stringify({ ...superModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 262_144, maxTokens: 8_192, compat: { maxTokensField: "max_tokens", requiresStringContent: true } })};
    const deepSeekModel = ${JSON.stringify({ ...deepSeekModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 1_048_576, maxTokens: 8_192 })};
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

    const successfulBoundary = ${JSON.stringify(turn("bionemo_batch_fold_demo"))};
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, successfulBoundary), true);
    const sourceOwnedFinal = patched.__bionemoSuperDeterministicFinalText(deepSeekModel, successfulBoundary);
    assert.match(sourceOwnedFinal, /five-protein OpenFold2 workflow returned a terminal result/u);
    const repeatedProviderChunks = () => (async function* providerChunks() {
      for (let index = 0; index < 3; index += 1) {
        yield { id: \`response-deepseek-\${index}\`, choices: [{ index: 0, delta: {
          content: "<tool_call><function=bionemo_batch_fold_demo><parameter=repeat>true</parameter></function></tool_call>",
          tool_calls: [{ index: 0, id: \`provider-repeat-\${index}\`, type: "function", function: {
            name: index === 1 ? "tool_call" : "bionemo_batch_fold_demo",
            arguments: index === 1 ? JSON.stringify({ id: "openclaw:bionemo-agent-toolkit:bionemo_batch_fold_demo" }) : "{}",
          } }],
        }, finish_reason: "tool_calls" }] };
      }
    }());
    const deepSeekFinalOutput = output();
    deepSeekFinalOutput.model = deepSeekModel.id;
    const deepSeekFinalEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(repeatedProviderChunks(), deepSeekFinalOutput, deepSeekModel, { push: (event) => deepSeekFinalEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperFinalText: sourceOwnedFinal });
    assert.equal(deepSeekFinalOutput.stopReason, "stop");
    assert.deepEqual(deepSeekFinalOutput.content, [{ type: "text", text: sourceOwnedFinal }]);
    assert.equal(JSON.stringify(deepSeekFinalOutput).includes("provider-repeat"), false);
    assert.equal(JSON.stringify(deepSeekFinalOutput).includes("<tool_call>"), false);
    assert.equal(deepSeekFinalEvents.some(({ type }) => type.startsWith("toolcall_")), false);
    const persisted = [...successfulBoundary.messages, deepSeekFinalOutput];
    assert.equal(persisted.filter((message) => message.role === "toolResult" && message.toolName === "bionemo_batch_fold_demo").length, 1);
    assert.equal(persisted.flatMap((message) => Array.isArray(message.content) ? message.content : []).filter((block) => block?.type === "toolCall" && block.name === "bionemo_batch_fold_demo").length, 1);

    const erroredBoundary = ${JSON.stringify(turn("bionemo_batch_fold_demo", { isError: true }))};
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, erroredBoundary), false);
    assert.equal(patched.__bionemoSuperDeterministicFinalText(deepSeekModel, erroredBoundary), undefined);
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, ${JSON.stringify(turn("tavily_search"))}), false);
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(${JSON.stringify({ ...deepSeekModel, id: "other/model" })}, successfulBoundary), false);
    const passThroughOutput = output();
    passThroughOutput.model = deepSeekModel.id;
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), passThroughOutput, deepSeekModel, { push: () => {} }, { emitReasoning: false, bionemoSuperFinalText: patched.__bionemoSuperDeterministicFinalText(deepSeekModel, erroredBoundary) });
    assert.equal(passThroughOutput.content.some(({ type }) => type === "toolCall"), true);
  `;
  await execFileAsync("docker", [
    "run", "--rm", "--network", "none", "--entrypoint", "node",
    "--mount", `type=bind,src=${path.join(distRoot, file)},dst=/app/dist/${file},readonly`,
    PINNED_IMAGE, "--input-type=module", "-e", integrationScript,
  ]);
});
