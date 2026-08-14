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
  bionemoSuperLocalCompletionText,
  bionemoSuperShouldFinalizeWithoutTools,
  patchOpenClawSuperFollowup,
} from "../runtime/patch-openclaw-super-followup.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";
const superModel = { provider: "tokenfactory", id: "nvidia/nemotron-3-super-120b-a12b" };
const deepSeekModel = { provider: "tokenfactory", id: "deepseek-ai/DeepSeek-V4-Pro" };

function turn(name, { id = name, isError = false, arguments: args = {}, status = "completed" } = {}) {
  return { messages: [
    { role: "user", content: [{ type: "text", text: "run" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "call-1", name, arguments: name === "tool_call" ? { id, ...args } : args }] },
    { role: "toolResult", toolCallId: "call-1", toolName: name, isError, content: [{ type: "text", text: JSON.stringify({ status, summary: { skill: name } }) }] },
  ] };
}

const tavilyInitial = BIONEMO_SUPER_INITIAL_TURNS.find(({ name }) => name === "tavily_web__tavily_search");

function tavilyTurn() {
  return { messages: [
    { role: "user", content: [{ type: "text", text: tavilyInitial.prompt }] },
    { role: "assistant", content: [{
      type: "toolCall",
      id: "tavily-call-1",
      name: tavilyInitial.name,
      arguments: structuredClone(tavilyInitial.params),
    }] },
    {
      role: "toolResult",
      toolCallId: "tavily-call-1",
      toolName: tavilyInitial.name,
      isError: false,
      content: [{ type: "text", text: "structuredContent:\n{bounded Tavily result}" }],
      details: {
        mcpServer: "tavily_web",
        mcpTool: "tavily_search",
        structuredContent: {
          query: tavilyInitial.params.query,
          results: [
            { title: "RCSB PDB documentation", url: "https://www.rcsb.org/docs/" },
            { title: "UniProt documentation", url: "https://www.uniprot.org/help/" },
          ],
        },
      },
    },
  ] };
}

test("Token Factory Super and DeepSeek finalize after successful atomic wrappers only", () => {
  for (const name of [
    "bionemo_research_drug_demo",
    "bionemo_compare_protein_structures",
    "bionemo_optimize_ligand_complex",
    "bionemo_batch_fold_demo",
    "bionemo_molmim",
    "bionemo_openfold2",
    "bionemo_openfold3",
  ]) {
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

test("host-local completion is limited to exact completed Token Factory Super tool boundaries", () => {
  const completed = turn("bionemo_molmim");
  assert.match(bionemoSuperLocalCompletionText(superModel, completed), /MolMIM optimization returned a terminal result/u);
  const structured = structuredClone(completed);
  structured.messages.at(-1).content = [{ type: "text", text: "not-json" }];
  structured.messages.at(-1).structuredContent = { status: "completed", summary: { skill: "MolMIM" } };
  assert.match(bionemoSuperLocalCompletionText(superModel, structured), /MolMIM optimization returned a terminal result/u);
  assert.equal(bionemoSuperLocalCompletionText(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("bionemo_molmim", { status: "running" })), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("bionemo_molmim", { status: null })), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("bionemo_molmim", { isError: true })), undefined);
  const ambiguous = structuredClone(completed);
  delete ambiguous.messages.at(-1).isError;
  assert.equal(bionemoSuperLocalCompletionText(superModel, ambiguous), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("tavily_search")), undefined);
  const mismatch = structuredClone(completed);
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperLocalCompletionText(superModel, mismatch), undefined);
});

test("host-local Tavily completion requires the exact source-owned turn and trusted result provenance", () => {
  const completed = tavilyTurn();
  assert.equal(bionemoSuperCompletedToolTarget(superModel, completed), tavilyInitial.name);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, completed), true);
  const final = bionemoSuperLocalCompletionText(superModel, completed);
  assert.match(final, /RCSB PDB/u);
  assert.match(final, /UniProt/u);
  assert.match(final, /Source claims:/u);
  assert.match(final, /Source-owned comparison/iu);
  assert.match(final, /source titles and canonical URLs appended below/iu);

  const rejected = [];
  const wrongPrompt = structuredClone(completed);
  wrongPrompt.messages[0].content[0].text += " ";
  rejected.push(wrongPrompt);
  const wrongArgs = structuredClone(completed);
  wrongArgs.messages[1].content[0].arguments.max_results = 4;
  rejected.push(wrongArgs);
  const extraArg = structuredClone(completed);
  extraArg.messages[1].content[0].arguments.topic = "general";
  rejected.push(extraArg);
  const mismatchedCall = structuredClone(completed);
  mismatchedCall.messages[2].toolCallId = "other-call";
  rejected.push(mismatchedCall);
  const duplicateCall = structuredClone(completed);
  duplicateCall.messages[1].content.push(structuredClone(duplicateCall.messages[1].content[0]));
  rejected.push(duplicateCall);
  const earlierTool = structuredClone(completed);
  earlierTool.messages.splice(1, 0,
    { role: "assistant", content: [{ type: "toolCall", id: "earlier-call", name: "bionemo_models_list", arguments: {} }] },
    { role: "toolResult", toolCallId: "earlier-call", toolName: "bionemo_models_list", isError: false, content: [] },
  );
  rejected.push(earlierTool);
  const ambiguousSuccess = structuredClone(completed);
  delete ambiguousSuccess.messages[2].isError;
  rejected.push(ambiguousSuccess);
  const errored = structuredClone(completed);
  errored.messages[2].isError = true;
  rejected.push(errored);
  const reportedError = structuredClone(completed);
  reportedError.messages[2].error = { code: "rate_limited" };
  rejected.push(reportedError);
  const wrongServer = structuredClone(completed);
  wrongServer.messages[2].details.mcpServer = "other";
  rejected.push(wrongServer);
  const topLevelStructured = structuredClone(completed);
  topLevelStructured.messages[2].structuredContent = topLevelStructured.messages[2].details.structuredContent;
  rejected.push(topLevelStructured);
  const emptyResults = structuredClone(completed);
  emptyResults.messages[2].details.structuredContent.results = [];
  rejected.push(emptyResults);
  const unsafeUrl = structuredClone(completed);
  unsafeUrl.messages[2].details.structuredContent.results[0].url = "file:///tmp/result";
  rejected.push(unsafeUrl);
  const unrequestedDomain = structuredClone(completed);
  unrequestedDomain.messages[2].details.structuredContent.results[0].url = "https://evil.example/";
  rejected.push(unrequestedDomain);
  const insecureDomain = structuredClone(completed);
  insecureDomain.messages[2].details.structuredContent.results[0].url = "http://www.rcsb.org/docs/";
  rejected.push(insecureDomain);
  const controlTitle = structuredClone(completed);
  controlTitle.messages[2].details.structuredContent.results[0].title = "RCSB\nPDB";
  rejected.push(controlTitle);
  for (const boundary of rejected) {
    assert.equal(bionemoSuperCompletedToolTarget(superModel, boundary), undefined);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, boundary), false);
    assert.equal(bionemoSuperLocalCompletionText(superModel, boundary), undefined);
  }
  assert.equal(bionemoSuperCompletedToolTarget(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperLocalCompletionText(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperCompletedToolTarget({ ...superModel, provider: "nvidia" }, completed), undefined);
});

test("Super initial calls are source-owned only for exact reviewed prompts", () => {
  assert.equal(BIONEMO_SUPER_NOTEBOOK_TURNS.length, 4);
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS.length, 6);
  assert.deepEqual(BIONEMO_SUPER_INITIAL_TURNS.slice(0, 4), BIONEMO_SUPER_NOTEBOOK_TURNS);
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS[4].name, "bionemo_molmim");
  assert.deepEqual(BIONEMO_SUPER_INITIAL_TURNS[4].params, {
    smi: "COC1=C(C=C2C(=C1)N=CN=C2NC3=CC(=C(C=C3)F)Cl)OCCCN4CCOCC4",
    algorithm: "CMA-ES",
    num_molecules: 2,
    num_iterations: 2,
    property_name: "QED",
    particles: 2,
    minimize: false,
    min_similarity: 0.7,
    radius: 1,
    ack_research_only: true,
    ack_no_safety_or_therapeutic_claims: true,
  });
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS[5], tavilyInitial);
  assert.deepEqual(tavilyInitial.params, {
    query: "RCSB PDB UniProt protein structure research contributions",
    include_domains: ["rcsb.org", "uniprot.org"],
    search_depth: "basic",
    max_results: 5,
    include_raw_content: false,
    include_images: false,
  });
  for (const expected of BIONEMO_SUPER_INITIAL_TURNS) {
    const actual = bionemoSuperInitialNotebookTool(superModel, {
      messages: [{ role: "user", content: [{ type: "text", text: expected.prompt }] }],
    });
    assert.deepEqual(actual, { name: expected.name, params: { ...expected.params } });
    assert.deepEqual(
      bionemoSuperInitialNotebookTool(superModel, { prompt: expected.prompt, messages: [] }),
      { name: expected.name, params: { ...expected.params } },
    );
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
  assert.equal(bionemoSuperInitialNotebookTool(superModel, {
    prompt: first.prompt,
    messages: [{ role: "user", content: "Continue from the previous tool call." }],
  }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, {
    prompt: first.prompt,
    messages: [{ role: "toolResult", toolName: first.name }],
  }), undefined);
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
  assert.match(source, /openclaw\.bionemo\.super-followup\.v9/u);
  const callback = source.indexOf("if (nextParams !== void 0) params = nextParams;");
  const codeMode = source.indexOf("if (options?.openclawCodeModeToolSurface === true)", callback);
  const guard = source.indexOf("if (bionemoSuperFinalText)");
  const request = source.indexOf("client.chat.completions.create(params");
  assert.ok(callback >= 0 && callback < codeMode && codeMode < guard && guard < request);
  assert.match(source, /delete params\.tools;\s*params\.tool_choice = "none";/su);
  assert.match(source, /const bionemoSuperLocalFinalText = bionemoSuperLocalCompletionText\(model, context\)/u);
  assert.match(source, /const client = bionemoSuperLocalFinalText \? undefined : createOpenAICompletionsClient/u);
  assert.match(source, /const bionemoSuperLocalResponse = bionemoSuperLocalFinalText \|\| bionemoSuperInitialTool\?\.name === "tavily_web__tavily_search"/u);
  assert.match(source, /const responseStream = bionemoSuperLocalResponse\s*\? \(async function\* bionemoSuperCompletedStream\(\) \{\s*yield \{ id: "bionemo-local-completion", choices:/su);
  assert.match(source, /bionemoSuperFinalText,/u);
  assert.match(source, /if \(!bionemoSuperFinalText && !bionemoSuperInitialTool && choiceDelta\.tool_calls/u);
  assert.match(source, /if \(choiceDelta\.content && !bionemoSuperFinalText && !bionemoSuperInitialTool\)/u);
  assert.match(source, /appendTextDelta\(bionemoSuperFinalText\)/u);
  assert.match(source, /params\.tool_choice = \{ type: "function", function: \{ name: bionemoSuperInitialTool\.name \} \}/u);
  await execFileAsync(process.execPath, ["--check", path.join(distRoot, file)]);

  let testingSource = source.replace(
    "export { ",
    "export { createOpenAICompletionsTransportStreamFn as __bionemoCreateOpenAICompletionsTransportStreamFn, processOpenAICompletionsStream as __bionemoProcessOpenAICompletionsStream, bionemoSuperDeterministicFinalText as __bionemoSuperDeterministicFinalText, bionemoSuperLocalCompletionText as __bionemoSuperLocalCompletionText, bionemoSuperShouldFinalizeWithoutTools as __bionemoSuperShouldFinalizeWithoutTools, ",
  );
  assert.notEqual(testingSource, source);
  testingSource = testingSource.replaceAll(
    "fetch: buildGuardedModelFetch(model),",
    "fetch: globalThis.__bionemoTestFetch ?? buildGuardedModelFetch(model),",
  );
  assert.match(testingSource, /globalThis\.__bionemoTestFetch \?\? buildGuardedModelFetch/u);
  await writeFile(path.join(distRoot, file), testingSource);
  const expectedInitial = BIONEMO_SUPER_NOTEBOOK_TURNS[1];
  const expectedTavilyInitial = tavilyInitial;
  const integrationScript = `
    import assert from "node:assert/strict";
    const patched = await import("file:///app/dist/${file}?test=" + Date.now());
    const model = ${JSON.stringify({ ...superModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 262_144, maxTokens: 8_192, compat: { maxTokensField: "max_tokens", requiresStringContent: true } })};
    const deepSeekModel = ${JSON.stringify({ ...deepSeekModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 1_048_576, maxTokens: 8_192 })};
    const expectedInitial = ${JSON.stringify({ name: expectedInitial.name, params: { ...expectedInitial.params } })};
    const expectedTavilyInitial = ${JSON.stringify({ name: expectedTavilyInitial.name, params: { ...expectedTavilyInitial.params } })};
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
    const wrongTavilyOutput = output();
    const wrongTavilyEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), wrongTavilyOutput, model, { push: (event) => wrongTavilyEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperInitialTool: expectedTavilyInitial });
    assert.equal(wrongTavilyOutput.stopReason, "toolUse");
    assert.deepEqual(wrongTavilyOutput.content, [{
      type: "toolCall",
      id: wrongTavilyOutput.content[0].id,
      name: "tavily_web__tavily_search",
      arguments: expectedTavilyInitial.params,
      partialArgs: JSON.stringify(expectedTavilyInitial.params),
    }]);
    assert.deepEqual(wrongTavilyEvents.filter(({ type }) => type === "toolcall_start").map(({ partial }) => partial.content.at(-1).name), [expectedTavilyInitial.name]);
    const noToolChunks = () => (async function* providerChunks() {
      yield { id: "response-no-tool", choices: [{ index: 0, delta: { content: "I will not call a tool." }, finish_reason: "stop" }] };
    }());
    const missingTavilyOutput = output();
    await patched.__bionemoProcessOpenAICompletionsStream(noToolChunks(), missingTavilyOutput, model, { push: () => {} }, { emitReasoning: false, bionemoSuperInitialTool: expectedTavilyInitial });
    assert.equal(missingTavilyOutput.stopReason, "toolUse");
    assert.deepEqual(missingTavilyOutput.content.filter(({ type }) => type === "toolCall").map(({ name, arguments: args }) => ({ name, args })), [{ name: expectedTavilyInitial.name, args: expectedTavilyInitial.params }]);
    assert.equal(missingTavilyOutput.content.some(({ type }) => type === "text"), false);
    const finalOutput = output();
    const finalEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), finalOutput, model, { push: (event) => finalEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperFinalText: "Deterministic completed result." });
    assert.equal(finalOutput.stopReason, "stop");
    assert.equal(finalOutput.content.some(({ type }) => type === "toolCall"), false);
    assert.equal(finalOutput.content.filter(({ type }) => type === "text").map(({ text }) => text).join(""), "Deterministic completed result.");
    assert.equal(JSON.stringify(finalOutput).includes("<tool_call>"), false);
    assert.equal(finalEvents.some(({ type }) => type.startsWith("toolcall_")), false);

    const successfulBoundary = ${JSON.stringify(turn("bionemo_batch_fold_demo"))};
    const successfulTavilyBoundary = ${JSON.stringify(tavilyTurn())};
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, successfulBoundary), true);
    const sourceOwnedFinal = patched.__bionemoSuperDeterministicFinalText(deepSeekModel, successfulBoundary);
    assert.match(sourceOwnedFinal, /five-protein OpenFold2 workflow returned a terminal result/u);
    const superLocalFinal = patched.__bionemoSuperLocalCompletionText(model, successfulBoundary);
    assert.match(superLocalFinal, /five-protein OpenFold2 workflow returned a terminal result/u);
    assert.equal(patched.__bionemoSuperLocalCompletionText(deepSeekModel, successfulBoundary), undefined);

    const collectEvents = async (eventStream) => {
      const events = [];
      for await (const event of eventStream) events.push(event);
      return events;
    };
    const within = async (promise, timeoutMs) => {
      let timer;
      try {
        return await Promise.race([
          promise,
          new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("transport did not finish locally")), timeoutMs); }),
        ]);
      } finally {
        clearTimeout(timer);
      }
    };
    const transport = patched.__bionemoCreateOpenAICompletionsTransportStreamFn();
    let providerFetchCalls = 0;
    globalThis.__bionemoTestFetch = async () => {
      providerFetchCalls += 1;
      return await new Promise(() => {});
    };
    const exactTavilyInitialContext = { prompt: ${JSON.stringify(tavilyInitial.prompt)}, messages: [] };
    const initialTavilyEvents = await within(collectEvents(transport(model, exactTavilyInitialContext, {
      apiKey: "test-key",
      emitReasoning: false,
      signal: AbortSignal.timeout(500),
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: expectedTavilyInitial.name, description: "bounded test", parameters: { type: "object" } } }] };
      },
    })), 750);
    assert.equal(providerFetchCalls, 0, "exact source-owned Tavily initial turn must not start a zero-byte provider request");
    assert.equal(initialTavilyEvents.some(({ type }) => type === "error"), false, JSON.stringify(initialTavilyEvents));
    assert.equal(initialTavilyEvents.at(0).type, "start");
    assert.equal(initialTavilyEvents.at(-1).type, "done");
    assert.equal(initialTavilyEvents.at(-1).message.stopReason, "toolUse");
    assert.deepEqual(initialTavilyEvents.at(-1).message.content.filter(({ type }) => type === "toolCall").map(({ name, arguments: args }) => ({ name, args })), [{ name: expectedTavilyInitial.name, args: expectedTavilyInitial.params }]);
    const localEvents = await within(collectEvents(transport(model, successfulBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
    assert.equal(providerFetchCalls, 0, "completed Super boundary must not start the zero-byte provider follow-up");
    assert.equal(localEvents.some(({ type }) => type === "error"), false, JSON.stringify(localEvents));
    assert.equal(localEvents.at(0).type, "start");
    assert.equal(localEvents.at(-1).type, "done");
    assert.equal(localEvents.some(({ type }) => type === "text_start"), true);
    assert.equal(localEvents.some(({ type }) => type === "text_delta"), true);
    assert.deepEqual(localEvents.at(-1).message.content, [{ type: "text", text: superLocalFinal }]);
    assert.equal(localEvents.at(-1).message.stopReason, "stop");

    const tavilyLocalFinal = patched.__bionemoSuperLocalCompletionText(model, successfulTavilyBoundary);
    assert.match(tavilyLocalFinal, /RCSB PDB/u);
    assert.match(tavilyLocalFinal, /UniProt/u);
    const tavilyLocalEvents = await within(collectEvents(transport(model, successfulTavilyBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
    assert.equal(providerFetchCalls, 0, "exact successful Tavily boundary must not start a zero-byte provider follow-up");
    assert.equal(tavilyLocalEvents.some(({ type }) => type === "error"), false, JSON.stringify(tavilyLocalEvents));
    assert.equal(tavilyLocalEvents.at(0).type, "start");
    assert.equal(tavilyLocalEvents.at(-1).type, "done");
    assert.equal(tavilyLocalEvents.some(({ type }) => type === "text_start"), true);
    assert.equal(tavilyLocalEvents.some(({ type }) => type === "text_delta"), true);
    assert.deepEqual(tavilyLocalEvents.at(-1).message.content, [{ type: "text", text: tavilyLocalFinal }]);
    assert.equal(tavilyLocalEvents.at(-1).message.stopReason, "stop");

    const providerBody = 'data: {"id":"normal-response","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Provider normal path."},"finish_reason":"stop"}]}\\n\\ndata: [DONE]\\n\\n';
    globalThis.__bionemoTestFetch = async () => {
      providerFetchCalls += 1;
      return new Response(providerBody, { status: 200, headers: { "content-type": "text/event-stream" } });
    };
    const replayContext = { prompt: ${JSON.stringify(tavilyInitial.prompt)}, messages: [{ role: "user", content: "Continue from the previous tool call." }] };
    const replayEvents = await within(collectEvents(transport(model, replayContext, {
      apiKey: "test-key",
      emitReasoning: false,
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: expectedTavilyInitial.name, description: "bounded test", parameters: { type: "object" } } }] };
      },
    })), 2_000);
    assert.equal(providerFetchCalls, 1, "a replay user message must retain the provider transport");
    assert.equal(replayEvents.at(-1).type, "done");
    assert.deepEqual(replayEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const compactSurfaceEvents = await within(collectEvents(transport(model, exactTavilyInitialContext, {
      apiKey: "test-key",
      emitReasoning: false,
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: "tool_call", description: "compact catalog", parameters: { type: "object" } } }] };
      },
    })), 2_000);
    assert.equal(providerFetchCalls, 2, "an unavailable direct Tavily tool must retain the provider transport");
    assert.equal(compactSurfaceEvents.at(-1).type, "done");
    assert.deepEqual(compactSurfaceEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const malformedTavilyBoundary = structuredClone(successfulTavilyBoundary);
    malformedTavilyBoundary.messages.at(-1).details.mcpServer = "untrusted-server";
    assert.equal(patched.__bionemoSuperLocalCompletionText(model, malformedTavilyBoundary), undefined);
    const malformedTavilyEvents = await within(collectEvents(transport(model, malformedTavilyBoundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, 3, "malformed Tavily provenance retains the provider transport");
    assert.equal(malformedTavilyEvents.at(-1).type, "done");
    assert.deepEqual(malformedTavilyEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const erroredBoundaryForTransport = ${JSON.stringify(turn("bionemo_batch_fold_demo", { isError: true }))};
    const erroredEvents = await within(collectEvents(transport(model, erroredBoundaryForTransport, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, 4, "errored Super boundary retains the provider transport");
    assert.equal(erroredEvents.at(-1).type, "done");
    assert.deepEqual(erroredEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const deepSeekEvents = await within(collectEvents(transport(deepSeekModel, successfulBoundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, 5, "other models retain the provider transport");
    assert.equal(deepSeekEvents.at(-1).type, "done");
    assert.deepEqual(deepSeekEvents.at(-1).message.content, [{ type: "text", text: sourceOwnedFinal }]);

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
